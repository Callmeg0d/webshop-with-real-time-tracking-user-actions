from datetime import datetime

from shared import get_logger

from app.constants import OrderStatus
from app.domain.entities.orders import OrderItem
from app.domain.interfaces.orders_repo import IOrdersRepository
from app.domain.interfaces.unit_of_work import IUnitOfWorkFactory
from app.schemas.orders import SCartItemForOrder, SUserOrder, SOrderItemWithImage
from app.services.cart_client import get_cart_items, get_cart_total
from app.services.product_client import get_product
from app.services.order_validator import OrderValidator
from app.services.payment_service import PaymentService
from app.services.user_client import get_user_delivery_address
from app.messaging.publisher import (
    publish_order_created,
    publish_order_processing_started,
    publish_order_confirmed,
    publish_stock_increase,
    publish_balance_increase,
)


logger = get_logger(__name__)

class OrderService:
    def __init__(
        self,
        orders_repository: IOrdersRepository,
        order_validator: OrderValidator,
        payment_service: PaymentService,
        uow_factory: IUnitOfWorkFactory
    ):
        self.orders_repository = orders_repository
        self.validator = order_validator
        self.payment = payment_service
        self.uow_factory = uow_factory

    async def create_order(self, user_id: int) -> OrderItem:
        logger.info(f"Creating order for user {user_id}")
        try:
            async with self.uow_factory.create():
                # Получаем корзину из cart-service
                cart_items_raw = await get_cart_items(user_id)
                total_cost = await get_cart_total(user_id)
                logger.debug(f"Cart retrieved: {len(cart_items_raw)} items, total cost: {total_cost}")
                
                # Преобразуем в SCartItemForOrder для валидатора
                cart_items = [
                    SCartItemForOrder(product_id=item["product_id"], quantity=item["quantity"])
                    for item in cart_items_raw
                ]

                await self.validator.validate_order(user_id, cart_items, total_cost)
                logger.debug(f"Order validation passed for user {user_id}")

                # Создаем заказ со статусом Pending
                order_data = await self._prepare_order_data(user_id, cart_items, total_cost)
                order = await self.orders_repository.create_order(order_data)
                logger.info(f"Order {order.order_id} created successfully")

            order_created_payload = {
                "order_id": order.order_id,
                "user_id": order.user_id,
                "created_at": (
                    order.created_at.isoformat()
                    if hasattr(order.created_at, "isoformat")
                    else str(order.created_at)
                ),
                "status": order.status,
                "delivery_address": order.delivery_address,
                "order_items": order.order_items,
                "total_cost": order.total_cost,
            }
            await publish_order_created(order_created_payload)
            logger.info(f"Order created event published for analytics, order {order.order_id}")

            # Публикуем событие начала обработки заказа (Saga)
            await publish_order_processing_started({
                "order_id": order.order_id,
                "user_id": user_id,
                "order_items": order.order_items,
                "total_cost": order.total_cost
            })
            logger.info(f"Order processing started event published for order {order.order_id}")
            
            return order
        except Exception as e:
            logger.error(f"Error creating order for user {user_id}: {e}", exc_info=True)
            raise

    async def confirm_order(self, order_id: int) -> None:
        """
        Подтверждает заказ после успешной резервации всех ресурсов.
        
        Args:
            order_id: ID заказа
        """
        logger.info(f"Confirming order {order_id}")
        try:
            # Идемпотентность: проверяем статус перед подтверждением
            order = await self.orders_repository.get_order_by_id(order_id)
            if not order or order.status != OrderStatus.PENDING:
                logger.debug(f"Order {order_id} cannot be confirmed (status: {order.status if order else 'not found'})")
                return
            
            async with self.uow_factory.create():
                await self.orders_repository.update_order_status(order_id, OrderStatus.CONFIRMED)
            
            # Получаем заказ для публикации события
            order = await self.orders_repository.get_order_by_id(order_id)
            if order:
                order_dict = {
                    "order_id": order.order_id,
                    "user_id": order.user_id,
                    "created_at": order.created_at.isoformat() if hasattr(order.created_at, 'isoformat') else str(order.created_at),
                    "status": order.status,
                    "delivery_address": order.delivery_address,
                    "order_items": order.order_items,
                    "total_cost": order.total_cost
                }
                await publish_order_confirmed(order_dict)
                logger.info(f"Order {order_id} confirmed successfully")
        except Exception as e:
            logger.error(f"Error confirming order {order_id}: {e}", exc_info=True)
            raise

    async def fail_order(self, order_id: int, reason: str) -> None:
        """
        Отменяет заказ и запускает компенсацию.
        
        Args:
            order_id: ID заказа
            reason: Причина отмены
        """
        logger.warning(f"Failing order {order_id}, reason: {reason}")
        try:
            # Идемпотентность: проверяем статус перед отменой
            order = await self.orders_repository.get_order_by_id(order_id)
            if not order or order.status != OrderStatus.PENDING:
                logger.debug(f"Order {order_id} cannot be failed (status: {order.status if order else 'not found'})")
                return
            
            async with self.uow_factory.create():
                await self.orders_repository.update_order_status(order_id, OrderStatus.FAILED)
            
            # Компенсирующие действия - возврат ресурсов
            if order:
                logger.info(f"Starting compensation for order {order_id}")
                for item in order.order_items:
                    await publish_stock_increase(order_id, item["product_id"], item["quantity"])
                    logger.debug(f"Stock increase event published for product {item['product_id']}, quantity {item['quantity']}")
                
                await publish_balance_increase(order_id, order.user_id, order.total_cost)
                logger.info(f"Balance increase event published for user {order.user_id}, amount {order.total_cost}")
                logger.info(f"Order {order_id} failed successfully, compensation actions triggered")
        except Exception as e:
            logger.error(f"Error failing order {order_id}: {e}", exc_info=True)
            raise

    async def _prepare_order_data(
        self,
        user_id: int,
        cart_items: list[SCartItemForOrder],
        total_cost: int
    ) -> OrderItem:

        delivery_address = await get_user_delivery_address(user_id)
        order_items = [
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in cart_items
        ]

        return OrderItem(
            user_id=user_id,
            created_at=datetime.now().date(),
            status=OrderStatus.PENDING,
            delivery_address=delivery_address or "",
            order_items=order_items,
            total_cost=total_cost
        )

    async def get_user_orders(self, user_id: int) -> list[SUserOrder]:
        logger.debug(f"Fetching orders for user {user_id}")
        try:
            orders = await self.orders_repository.get_by_user_id(user_id)
            logger.debug(f"Found {len(orders)} orders for user {user_id}")
            result = []
            
            for order in orders:
                if not order.order_items:
                    logger.debug(f"Skipping order {order.order_id} - no items")
                    continue

                order_items_with_images = []
                for item in order.order_items:
                    product_id = item.get("product_id")
                    product_image_url = None
                    
                    if product_id:
                        try:
                            product = await get_product(int(product_id))
                            if product and product.get("image") is not None:
                                product_image_url = f"/static/images/{product['image']}.webp"
                        except Exception as e:
                            logger.warning(f"Failed to get product {product_id} for order {order.order_id}: {e}")
                    
                    order_items_with_images.append(SOrderItemWithImage(
                        product_id=item["product_id"],
                        quantity=item["quantity"],
                        product_image_url=product_image_url
                    ))

                result.append(SUserOrder(
                    id=order.order_id,
                    created_at=order.created_at,
                    status=order.status,
                    delivery_address=order.delivery_address,
                    order_items=order_items_with_images,
                    total_cost=order.total_cost
                ))

            logger.debug(f"Returning {len(result)} orders for user {user_id}")
            return result
        except Exception as e:
            logger.error(f"Error fetching orders for user {user_id}: {e}", exc_info=True)
            raise

