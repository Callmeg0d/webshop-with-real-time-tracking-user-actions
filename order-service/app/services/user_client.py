import httpx
from app.config import settings
from shared.constants import HttpTimeout, HttpHeaders


async def get_user_delivery_address(user_id: int) -> str | None:
    """
    Получает адрес доставки пользователя из user-service.

    Args:
        user_id: ID пользователя

    Returns:
        Адрес доставки или None

    Raises:
        httpx.HTTPStatusError: Если сервис недоступен
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.USER_SERVICE_URL}/users/me",
            headers={HttpHeaders.X_USER_ID.value: str(user_id)},
            timeout=HttpTimeout.DEFAULT.value
        )
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("delivery_address")


async def get_user_balance(user_id: int) -> int | None:
    """
    Получает баланс пользователя из user-service.

    Args:
        user_id: ID пользователя

    Returns:
        Баланс пользователя или None

    Raises:
        httpx.HTTPStatusError: Если сервис недоступен
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.USER_SERVICE_URL}/users/me",
            headers={HttpHeaders.X_USER_ID.value: str(user_id)},
            timeout=HttpTimeout.DEFAULT.value
        )
        response.raise_for_status()
        user_data = response.json()
        return user_data.get("balance")


async def decrease_user_balance(user_id: int, amount: int) -> None:
    """
    Уменьшает баланс пользователя в user-service.

    Args:
        user_id: ID пользователя
        amount: Сумма для списания

    Raises:
        httpx.HTTPStatusError: Если сервис недоступен
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.USER_SERVICE_URL}/users/balance/decrease",
            headers={HttpHeaders.X_USER_ID.value: str(user_id)},
            json={"amount": amount},
            timeout=HttpTimeout.DEFAULT.value
        )
        response.raise_for_status()

