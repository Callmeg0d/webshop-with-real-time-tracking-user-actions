from app.messaging.broker import broker


async def publish_balance_reserved(order_id: int) -> None:
    """Публикует событие успешной резервации баланса."""
    await broker.publish(
        message={"order_id": order_id},
        topic="balance_reserved",
    )


async def publish_balance_reservation_failed(order_id: int, reason: str) -> None:
    """Публикует событие неудачной резервации баланса."""
    await broker.publish(
        message={"order_id": order_id, "reason": reason},
        topic="balance_reservation_failed",
    )
