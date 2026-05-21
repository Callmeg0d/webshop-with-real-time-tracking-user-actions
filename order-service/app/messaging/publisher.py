from app.messaging.broker import broker


async def publish_order_created(order: dict) -> None:
    """Публикует событие создания заказа."""
    await broker.publish(
        message=order,
        topic="order_created",
    )


async def decrease_stock(product_id: int, quantity: int) -> None:
    await broker.publish(
        message={"product_id": product_id, "quantity": quantity},
        topic="stock_decrease_request",
    )


async def decrease_user_balance(user_id: int, amount: int) -> None:
    await broker.publish(
        message={"user_id": user_id, "amount": amount},
        topic="balance_decrease_requests",
    )


async def publish_order_processing_started(event: dict) -> None:
    """Публикует событие начала обработки заказа"""
    await broker.publish(
        message=event,
        topic="order_processing_started",
    )


async def publish_order_confirmed(order: dict) -> None:
    """Публикует событие подтверждения заказа"""
    await broker.publish(
        message=order,
        topic="order_confirmed",
    )


async def publish_stock_increase(order_id: int, product_id: int, quantity: int) -> None:
    """Публикует событие возврата товаров (компенсация)"""
    await broker.publish(
        message={"order_id": order_id, "product_id": product_id, "quantity": quantity},
        topic="stock_increase",
    )


async def publish_balance_increase(order_id: int, user_id: int, amount: int) -> None:
    """Публикует событие возврата баланса (компенсация)"""
    await broker.publish(
        message={"order_id": order_id, "user_id": user_id, "amount": amount},
        topic="balance_increase",
    )