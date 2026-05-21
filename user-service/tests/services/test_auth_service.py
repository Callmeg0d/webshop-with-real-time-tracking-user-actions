import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt as jose_jwt, JWTError


from app.config import settings
from app.domain.entities.users import UserItem
from app.exceptions import UserAlreadyExistsException, IncorrectEmailOrPasswordException, TokenExpiredException
from app.schemas.users import SUserAuth
from app.core.security import get_password_hash
from app.services.auth_service import AuthService




class TestAuthServiceRegisterUser:
    """Юнит-тесты для метода register_user AuthService"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
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
    def mock_db(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def auth_service(self, mock_repository, mock_uow_factory, mock_db):
        from app.services.auth_service import AuthService
        return AuthService(
            user_repository=mock_repository,
            uow_factory=mock_uow_factory,
            db=mock_db
        )
    
    @pytest.mark.asyncio
    async def test_register_user_success(
        self,
        auth_service,
        mock_repository,
        mock_uow,
        mock_uow_factory,
        mocker
    ):
        """Тест успешной регистрации пользователя"""
        user_data = SUserAuth(email="test@example.com", password="password123")
        
        created_user = UserItem(
            email="test@example.com",
            hashed_password="hashed_password",
            balance=0,
            id=1
        )
        
        mock_repository.get_user_by_email = mocker.AsyncMock(return_value=None)
        mock_repository.create_user = mocker.AsyncMock(return_value=created_user)
        
        result = await auth_service.register_user(user_data)
        
        assert isinstance(result, UserItem)
        assert result.id == 1
        assert result.email == "test@example.com"
        
        mock_repository.get_user_by_email.assert_called_once_with(user_data.email)
        mock_repository.create_user.assert_called_once()
        mock_uow_factory.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_user_already_exists(
        self,
        auth_service,
        mock_repository,
        mock_uow,
        mock_uow_factory,
        mocker
    ):
        """Тест регистрации с существующим email"""
        user_data = SUserAuth(email="test@example.com", password="password123")
        
        existing_user = UserItem(
            email="test@example.com",
            hashed_password="hash",
            id=1
        )
        
        mock_repository.get_user_by_email = mocker.AsyncMock(return_value=existing_user)
        
        with pytest.raises(UserAlreadyExistsException):
            await auth_service.register_user(user_data)
        
        mock_repository.get_user_by_email.assert_called_once_with(user_data.email)
        mock_repository.create_user.assert_not_called()


class TestAuthServiceLoginUser:
    """Юнит-тесты для метода login_user"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow_factory(self, mocker):
        return mocker.Mock()
    
    @pytest.fixture
    def mock_db(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def auth_service(self, mock_repository, mock_uow_factory, mock_db):
        return AuthService(
            user_repository=mock_repository,
            uow_factory=mock_uow_factory,
            db=mock_db
        )
    
    @pytest.mark.asyncio
    async def test_login_user_success(
        self,
        auth_service,
        mock_db,
        mocker
    ):
        """Тест успешного входа пользователя"""
        user_data = SUserAuth(email="test@example.com", password="password123")
        
        user = UserItem(
            email="test@example.com",
            hashed_password=get_password_hash("password123"),
            id=1
        )
        
        # Мокаем authenticate_user
        mocker.patch.object(
            auth_service_module,
            'authenticate_user',
            return_value=user
        )
        
        result = await auth_service.login_user(user_data)
        
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert isinstance(result.access_token, str)
        assert isinstance(result.refresh_token, str)
        
        # Проверяем, что токены валидны
        access_payload = jose_jwt.decode(
            result.access_token,
            settings.SECRET_KEY,
            settings.ALGORITHM
        )
        assert access_payload["sub"] == str(user.id)
    
    @pytest.mark.asyncio
    async def test_login_user_wrong_password(
        self,
        auth_service,
        mock_db,
        mocker
    ):
        """Тест входа с неверным паролем"""
        user_data = SUserAuth(email="test@example.com", password="wrongpassword")
        
        # Мокаем authenticate_user чтобы возвращал None
        mocker.patch.object(
            auth_service_module,
            'authenticate_user',
            return_value=None
        )
        
        with pytest.raises(IncorrectEmailOrPasswordException):
            await auth_service.login_user(user_data)


class TestAuthServiceRefreshTokens:
    """Юнит-тесты для метода refresh_tokens"""
    
    @pytest.fixture
    def mock_repository(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def mock_uow_factory(self, mocker):
        return mocker.Mock()
    
    @pytest.fixture
    def mock_db(self, mocker):
        return mocker.AsyncMock()
    
    @pytest.fixture
    def auth_service(self, mock_repository, mock_uow_factory, mock_db):

        return AuthService(
            user_repository=mock_repository,
            uow_factory=mock_uow_factory,
            db=mock_db
        )
    
    @pytest.mark.asyncio
    async def test_refresh_tokens_success(
        self,
        auth_service,
        mock_repository,
        mocker
    ):
        """Тест успешного обновления токенов"""
        user = UserItem(
            email="test@example.com",
            hashed_password="hash",
            id=1
        )
        
        # Создаем валидный refresh token
        expire_time = datetime.now(tz=timezone.utc) + timedelta(days=7)
        refresh_token = jose_jwt.encode(
            {
                "sub": str(user.id),
                "exp": expire_time.timestamp()
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        mock_repository.get_user_by_id = mocker.AsyncMock(return_value=user)
        
        result = await auth_service.refresh_tokens(refresh_token)
        
        assert result.access_token is not None
        assert result.refresh_token is not None
        
        # Проверяем новый access token
        access_payload = jose_jwt.decode(
            result.access_token,
            settings.SECRET_KEY,
            settings.ALGORITHM
        )
        assert access_payload["sub"] == str(user.id)
        
        # Если токен еще не скоро истечет, refresh_token должен остаться тем же
        assert result.refresh_token == refresh_token
    
    @pytest.mark.asyncio
    async def test_refresh_tokens_expired(
        self,
        auth_service
    ):
        """Тест обновления истекшего токена"""
        # Создаем истекший токен
        expire_time = datetime.now(tz=timezone.utc) - timedelta(days=1)
        expired_token = jose_jwt.encode(
            {
                "sub": "1",
                "exp": expire_time.timestamp()
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        # jose_jwt.decode выбрасывает ExpiredSignatureError при истекшем токене,
        # который ловится как JWTError в auth_service
        with pytest.raises(JWTError):
            await auth_service.refresh_tokens(expired_token)
    
    @pytest.mark.asyncio
    async def test_refresh_tokens_invalid(
        self,
        auth_service
    ):
        """Тест обновления с невалидным токеном"""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(JWTError):
            await auth_service.refresh_tokens(invalid_token)
    
    @pytest.mark.asyncio
    async def test_refresh_tokens_user_not_found(
        self,
        auth_service,
        mock_repository,
        mocker
    ):
        """Тест обновления токена для несуществующего пользователя"""
        # Создаем валидный токен для несуществующего пользователя
        expire_time = datetime.now(tz=timezone.utc) + timedelta(days=7)
        token = jose_jwt.encode(
            {
                "sub": "99999",
                "exp": expire_time.timestamp()
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        mock_repository.get_user_by_id = mocker.AsyncMock(return_value=None)
        
        with pytest.raises(JWTError):
            await auth_service.refresh_tokens(token)
    
    @pytest.mark.asyncio
    async def test_refresh_tokens_refresh_token_soon_expires(
        self,
        auth_service,
        mock_repository,
        mocker
    ):
        """Тест обновления токенов когда refresh token скоро истечет"""
        user = UserItem(
            email="test@example.com",
            hashed_password="hash",
            id=1
        )
        
        # Создаем refresh token который скоро истечет (менее 2 минут)
        expire_time = datetime.now(tz=timezone.utc) + timedelta(minutes=1)
        refresh_token = jose_jwt.encode(
            {
                "sub": str(user.id),
                "exp": expire_time.timestamp()
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        
        mock_repository.get_user_by_id = mocker.AsyncMock(return_value=user)
        
        result = await auth_service.refresh_tokens(refresh_token)
        
        assert result.access_token is not None
        assert result.refresh_token is not None
        # Refresh token должен быть обновлен
        assert result.refresh_token != refresh_token
        
        # Проверяем новый refresh token
        refresh_payload = jose_jwt.decode(
            result.refresh_token,
            settings.SECRET_KEY,
            settings.ALGORITHM
        )
        assert refresh_payload["sub"] == str(user.id)
