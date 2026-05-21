import os
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

os.environ["MODE"] = "TEST"

from app.main import app
from app.database import Base
from app.dependencies import get_db
from app.config import settings

pytest_plugins = ["shared.test_utils.conftest"]


_db_initialized = False


@pytest.fixture(scope="session", autouse=True)
async def _setup_test_db():
    """Создает таблицы один раз на сессию тестов"""
    global _db_initialized
    if not _db_initialized:
        engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
        _db_initialized = True


@pytest.fixture(scope="function")
async def test_engine(_setup_test_db):
    """Создает engine для тестовой БД для каждого теста (переиспользует созданные таблицы)"""
    engine = create_async_engine(settings.TEST_DATABASE_URL, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_engine):
    """Создает тестовую сессию БД для каждого теста с транзакционной изоляцией"""
    test_session_maker = async_sessionmaker(
        bind=test_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    
    async with test_session_maker() as session:
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.commit()
        
        yield session

        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.commit()


@pytest.fixture(scope="function")
async def async_client(test_db_session: AsyncSession):
    """Создает AsyncClient для тестирования API"""
    async def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
