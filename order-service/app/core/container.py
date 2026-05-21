from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.unit_of_work_factory import UnitOfWorkFactory
from app.repositories.orders_repository import OrdersRepository
from app.repositories.saga_reservation_repository import SagaReservationRepository
from app.services.order_service import OrderService
from app.services.order_validator import OrderValidator
from app.services.payment_service import PaymentService


class Container(containers.DeclarativeContainer):
    """DI-контейнер для управления зависимостями"""

    db = providers.Dependency(instance_of=AsyncSession)

    orders_repository = providers.Factory(
        OrdersRepository,
        db=db
    )

    saga_reservation_repository = providers.Factory(
        SagaReservationRepository,
        db=db
    )

    uow_factory = providers.Factory(
        UnitOfWorkFactory,
        session=db
    )

    order_validator = providers.Singleton(OrderValidator)
    payment_service = providers.Singleton(PaymentService)

    order_service = providers.Factory(
        OrderService,
        orders_repository=orders_repository,
        order_validator=order_validator,
        payment_service=payment_service,
        uow_factory=uow_factory
    )

