from datetime import datetime, timedelta, timezone

from jose import jwt as jose_jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from shared import get_logger

from app.config import settings
from app.core.security import get_password_hash, authenticate_user, create_access_token, create_refresh_token
from app.domain.entities.users import UserItem
from app.domain.interfaces.users_repo import IUsersRepository
from app.domain.interfaces.unit_of_work import IUnitOfWorkFactory
from app.exceptions import UserAlreadyExistsException, IncorrectEmailOrPasswordException, TokenExpiredException
from app.schemas.users import SUserAuth, STokenResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self,
                 user_repository: IUsersRepository,
                 uow_factory: IUnitOfWorkFactory,
                 db: AsyncSession):
        """
        Сервис аутентификации для регистрации, входа и обновления токенов пользователей

        Args:
            user_repository: Репозиторий для работы с пользователями в БД
            uow_factory: Фабрика для создания UnitOfWork
            db: Асинхронная сессия базы данных (для authenticate_user)
        """
        self.db = db
        self.user_repository = user_repository
        self.uow_factory = uow_factory

    async def register_user(self, user_data: SUserAuth) -> UserItem:
        """
        Регистрирует нового пользователя в системе

        Args:
            user_data: Данные для регистрации

        Returns:
            UserItem: Доменная сущность зарегистрированного пользователя

        Raises:
            UserAlreadyExistsException: Если пользователь с таким email уже существует
        """
        logger.info(f"Registering new user with email: {user_data.email}")
        try:
            # Проверяем существование пользователя
            async with self.uow_factory.create():
                existing_user = await self.user_repository.get_user_by_email(user_data.email)
                if existing_user:
                    logger.warning(f"User with email {user_data.email} already exists")
                    raise UserAlreadyExistsException

                # Создаем пользователя с хешированным паролем
                hashed_password = get_password_hash(user_data.password)
                user = await self.user_repository.create_user(
                    UserItem(
                        email=user_data.email,
                        hashed_password=hashed_password,
                        balance=0,
                    )
                )
                logger.info(f"User created successfully, user_id: {user.id}")

            return user
        except UserAlreadyExistsException:
            raise
        except Exception as e:
            logger.error(f"Error registering user {user_data.email}: {e}", exc_info=True)
            raise

    async def login_user(self, user_data: SUserAuth) -> STokenResponse:
        """
        Аутентифицирует пользователя и возвращает токены доступа

        Args:
            user_data: Данные для входа (email и пароль)

        Returns:
            Схема с access_token и refresh_token

        Raises:
            IncorrectEmailOrPasswordException: Если неверный email или пароль
        """
        logger.info(f"Login attempt for email: {user_data.email}")
        try:
            # Аутентифицируем пользователя
            user = await authenticate_user(user_data.email, user_data.password, self.db)
            if not user:
                logger.warning(f"Failed login attempt for email: {user_data.email}")
                raise IncorrectEmailOrPasswordException

            # Создаем токены
            access_token = create_access_token({"sub": str(user.id)})
            refresh_token = create_refresh_token({"sub": str(user.id)})
            logger.info(f"User {user.id} logged in successfully")

            return STokenResponse(
                access_token=access_token,
                refresh_token=refresh_token
            )
        except IncorrectEmailOrPasswordException:
            raise
        except Exception as e:
            logger.error(f"Error during login for {user_data.email}: {e}", exc_info=True)
            raise

    async def refresh_tokens(self, token: str) -> STokenResponse:
        """
        Обновляет access token и при необходимости refresh token

        Args:
            token: Refresh token для верификации

        Returns:
            Схема с новым access_token и refresh_token (если нужно обновить)

        Raises:
            TokenExpiredException: Если refresh token истек
            JWTError: Если токен невалиден или пользователь не найден
        """
        logger.debug("Refreshing tokens")
        try:
            # Декодируем токен
            try:
                payload = jose_jwt.decode(token, settings.SECRET_KEY, settings.ALGORITHM)
            except JWTError as e:
                logger.warning(f"Invalid refresh token: {e}")
                raise JWTError

            # Проверяем срок действия refresh токена
            expire = payload.get("exp")
            if not expire or int(expire) < datetime.now(tz=timezone.utc).timestamp():
                logger.warning("Refresh token expired")
                raise TokenExpiredException

            # Проверяем наличие user_id
            user_id = payload.get("sub")
            if not isinstance(user_id, str) or user_id == "None":
                logger.warning("Invalid user_id in refresh token")
                raise JWTError

            # Ищем пользователя
            user = await self.user_repository.get_user_by_id(int(user_id))
            if not user:
                logger.warning(f"User {user_id} not found for token refresh")
                raise JWTError

            # Создаём новый access token
            new_access_token = jose_jwt.encode(
                {"sub": str(user.id), "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=30)},
                settings.SECRET_KEY,
                algorithm=settings.ALGORITHM,
            )

            # Проверяем, нужно ли обновить refresh token (если скоро истечет)
            refresh_expire_time = datetime.fromtimestamp(expire, tz=timezone.utc)
            if refresh_expire_time - datetime.now(tz=timezone.utc) < timedelta(minutes=2):
                new_refresh_token = jose_jwt.encode(
                    {"sub": str(user.id), "exp": datetime.now(tz=timezone.utc) + timedelta(days=7)},
                    settings.SECRET_KEY,
                    algorithm=settings.ALGORITHM,
                )
                logger.debug(f"Both tokens refreshed for user {user.id}")
            else:
                new_refresh_token = token  # Оставляем старый refresh_token
                logger.debug(f"Access token refreshed for user {user.id}")

            return STokenResponse(
                access_token=new_access_token,
                refresh_token=new_refresh_token
            )
        except (TokenExpiredException, JWTError):
            raise
        except Exception as e:
            logger.error(f"Error refreshing tokens: {e}", exc_info=True)
            raise

