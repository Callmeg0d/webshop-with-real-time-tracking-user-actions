import pytest
from datetime import date

from app.constants import OrderStatus
from app.domain.entities.orders import OrderItem
from app.services.order_service import OrderService
from app.schemas.orders import SCartItemForOrder



class TestOrderServiceCreateOrder:
    """Юнит-тесты для метода create_order OrderService"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_validator(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_payment_service(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow(self, mocker):
        uow = mocker.AsyncMock()
        uow.__aenter__ = mocker.AsyncMock(return_value=uow)
        uow.__aexit__ = mocker.AsyncMock(return_value=None)
        return uow
    
    @pytest.fixture
    def mock_uow_factory(self, mock_uow, mocker):
        factory = mocker.Mock()
        factory.create = mocker.Mock(return_value=mock_uow)
        return factory
    
    @pytest.fixture
    def order_service(
        self,
        mock_repository,
        mock_validator,
        mock_payment_service,
        mock_uow_factory
    ):
        return OrderService(
            orders_repository=mock_repository,
            order_validator=mock_validator,
            payment_service=mock_payment_service,
            uow_factory=mock_uow_factory
        )
    
    @pytest.mark.asyncio
    async def test_create_order_success(
        self,
        order_service: OrderService,
        mock_repository,
        mock_validator,
        mock_uow,
        mock_uow_factory,
        mocker
    ):
        """Тест успешного создания заказа"""
        user_id = 1
        
        mocker.patch(
            'app.services.order_service.get_cart_items',
            return_value=[
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 1}
            ]
        )
        mocker.patch(
            'app.services.order_service.get_cart_total',
            return_value=3500
        )
        mocker.patch(
            'app.services.order_service.get_user_delivery_address',
            return_value="Test Address"
        )
        mocker.patch(
            'app.services.order_service.publish_order_created',
            new=mocker.AsyncMock(return_value=None),
        )
        mocker.patch(
            'app.services.order_service.publish_order_processing_started',
            new=mocker.AsyncMock(return_value=None),
        )
        
        created_order = OrderItem(
            order_id=1,
            user_id=user_id,
            created_at=date.today(),
            status=OrderStatus.PENDING,
            delivery_address="Test Address",
            order_items=[{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}],
            total_cost=3500
        )
        
        mock_repository.create_order = mocker.AsyncMock(return_value=created_order)
        
        result = await order_service.create_order(user_id)
        
        assert isinstance(result, OrderItem)
        assert result.order_id == 1
        assert result.user_id == user_id
        assert result.total_cost == 3500
        assert result.status == OrderStatus.PENDING
        
        mock_validator.validate_order.assert_called_once()
        mock_repository.create_order.assert_called_once()
        mock_uow_factory.create.assert_called_once()
        mock_uow.__aenter__.assert_called_once()
        mock_uow.__aexit__.assert_called_once()


class TestOrderServiceGetUserOrders:
    """Юнит-тесты для метода get_user_orders OrderService"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_validator(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_payment_service(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow_factory(self, mocker):
        return mocker.Mock()
    
    @pytest.fixture
    def order_service(
        self,
        mock_repository,
        mock_validator,
        mock_payment_service,
        mock_uow_factory
    ):
        return OrderService(
            orders_repository=mock_repository,
            order_validator=mock_validator,
            payment_service=mock_payment_service,
            uow_factory=mock_uow_factory
        )
    
    @pytest.mark.asyncio
    async def test_get_user_orders_success(
        self,
        order_service: OrderService,
        mock_repository,
        mocker
    ):
        """Тест успешного получения заказов пользователя"""
        user_id = 1
        
        orders = [
            OrderItem(
                order_id=1,
                user_id=user_id,
                created_at=date.today(),
                status=OrderStatus.CONFIRMED,
                delivery_address="Address 1",
                order_items=[{"product_id": 1, "quantity": 2}],
                total_cost=2000
            ),
            OrderItem(
                order_id=2,
                user_id=user_id,
                created_at=date.today(),
                status=OrderStatus.PENDING,
                delivery_address="Address 2",
                order_items=[{"product_id": 2, "quantity": 1}],
                total_cost=1500
            )
        ]
        
        mock_repository.get_by_user_id = mocker.AsyncMock(return_value=orders)
        mocker.patch(
            'app.services.order_service.get_product',
            return_value={"image": 123}
        )
        
        result = await order_service.get_user_orders(user_id)
        
        assert len(result) == 2
        assert result[0].id in [1, 2]
        assert result[1].id in [1, 2]
        
        mock_repository.get_by_user_id.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_get_user_orders_empty(
        self,
        order_service: OrderService,
        mock_repository,
        mocker
    ):
        """Тест получения заказов при пустой БД"""
        user_id = 1
        
        mock_repository.get_by_user_id = mocker.AsyncMock(return_value=[])
        
        result = await order_service.get_user_orders(user_id)
        
        assert result == []
        mock_repository.get_by_user_id.assert_called_once_with(user_id)


class TestOrderServiceConfirmOrder:
    """Юнит-тесты для метода confirm_order OrderService"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_validator(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_payment_service(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow(self, mocker):
        uow = mocker.AsyncMock()
        uow.__aenter__ = mocker.AsyncMock(return_value=uow)
        uow.__aexit__ = mocker.AsyncMock(return_value=None)
        return uow
    
    @pytest.fixture
    def mock_uow_factory(self, mock_uow, mocker):
        factory = mocker.Mock()
        factory.create = mocker.Mock(return_value=mock_uow)
        return factory
    
    @pytest.fixture
    def order_service(
        self,
        mock_repository,
        mock_validator,
        mock_payment_service,
        mock_uow_factory
    ):
        return OrderService(
            orders_repository=mock_repository,
            order_validator=mock_validator,
            payment_service=mock_payment_service,
            uow_factory=mock_uow_factory
        )
    
    @pytest.mark.asyncio
    async def test_confirm_order_success(
        self,
        order_service: OrderService,
        mock_repository,
        mock_uow,
        mock_uow_factory,
        mocker
    ):
        """Тест успешного подтверждения заказа"""
        order_id = 1
        user_id = 1
        
        pending_order = OrderItem(
            order_id=order_id,
            user_id=user_id,
            created_at=date.today(),
            status=OrderStatus.PENDING,
            delivery_address="Test Address",
            order_items=[{"product_id": 1, "quantity": 2}],
            total_cost=2000
        )
        
        confirmed_order = OrderItem(
            order_id=order_id,
            user_id=user_id,
            created_at=date.today(),
            status=OrderStatus.CONFIRMED,
            delivery_address="Test Address",
            order_items=[{"product_id": 1, "quantity": 2}],
            total_cost=2000
        )
        
        mock_repository.get_order_by_id = mocker.AsyncMock(
            side_effect=[pending_order, confirmed_order]
        )
        mock_repository.update_order_status = mocker.AsyncMock(return_value=None)
        mocker.patch(
            'app.services.order_service.publish_order_confirmed',
            return_value=None
        )
        
        await order_service.confirm_order(order_id)
        
        mock_repository.get_order_by_id.assert_called()
        mock_repository.update_order_status.assert_called_once_with(order_id, OrderStatus.CONFIRMED)
        mock_uow_factory.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_confirm_order_already_confirmed(
        self,
        order_service: OrderService,
        mock_repository,
        mocker
    ):
        """Тест подтверждения уже подтвержденного заказа (идемпотентность)"""
        order_id = 1
        
        confirmed_order = OrderItem(
            order_id=order_id,
            user_id=1,
            created_at=date.today(),
            status=OrderStatus.CONFIRMED,
            delivery_address="Test Address",
            order_items=[{"product_id": 1, "quantity": 2}],
            total_cost=2000
        )
        
        mock_repository.get_order_by_id = mocker.AsyncMock(return_value=confirmed_order)
        
        await order_service.confirm_order(order_id)
        
        # Не должно быть вызова update_order_status
        mock_repository.update_order_status.assert_not_called()


class TestOrderServiceFailOrder:
    """Юнит-тесты для метода fail_order OrderService"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_validator(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_payment_service(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow(self, mocker):
        uow = mocker.AsyncMock()
        uow.__aenter__ = mocker.AsyncMock(return_value=uow)
        uow.__aexit__ = mocker.AsyncMock(return_value=None)
        return uow
    
    @pytest.fixture
    def mock_uow_factory(self, mock_uow, mocker):
        factory = mocker.Mock()
        factory.create = mocker.Mock(return_value=mock_uow)
        return factory
    
    @pytest.fixture
    def order_service(
        self,
        mock_repository,
        mock_validator,
        mock_payment_service,
        mock_uow_factory
    ):
        return OrderService(
            orders_repository=mock_repository,
            order_validator=mock_validator,
            payment_service=mock_payment_service,
            uow_factory=mock_uow_factory
        )
    
    @pytest.mark.asyncio
    async def test_fail_order_success(
        self,
        order_service: OrderService,
        mock_repository,
        mock_uow,
        mock_uow_factory,
        mocker
    ):
        """Тест успешной отмены заказа"""
        order_id = 1
        user_id = 1
        reason = "Insufficient stock"
        
        pending_order = OrderItem(
            order_id=order_id,
            user_id=user_id,
            created_at=date.today(),
            status=OrderStatus.PENDING,
            delivery_address="Test Address",
            order_items=[
                {"product_id": 1, "quantity": 2},
                {"product_id": 2, "quantity": 1}
            ],
            total_cost=3500
        )
        
        mock_repository.get_order_by_id = mocker.AsyncMock(return_value=pending_order)
        mock_repository.update_order_status = mocker.AsyncMock(return_value=None)
        mocker.patch(
            'app.services.order_service.publish_stock_increase',
            return_value=None
        )
        mocker.patch(
            'app.services.order_service.publish_balance_increase',
            return_value=None
        )
        
        await order_service.fail_order(order_id, reason)
        
        mock_repository.update_order_status.assert_called_once_with(order_id, OrderStatus.FAILED)
        mock_uow_factory.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_fail_order_already_failed(
        self,
        order_service: OrderService,
        mock_repository,
        mocker
    ):
        """Тест отмены уже отмененного заказа (идемпотентность)"""
        order_id = 1
        
        failed_order = OrderItem(
            order_id=order_id,
            user_id=1,
            created_at=date.today(),
            status=OrderStatus.FAILED,
            delivery_address="Test Address",
            order_items=[{"product_id": 1, "quantity": 2}],
            total_cost=2000
        )
        
        mock_repository.get_order_by_id = mocker.AsyncMock(return_value=failed_order)
        
        await order_service.fail_order(order_id, "Test reason")
        
        # Не должно быть вызова update_order_status
        mock_repository.update_order_status.assert_not_called()
