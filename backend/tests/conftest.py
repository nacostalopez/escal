import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models.relational import Account, Store, StoreCredential, User
from app.security import encrypt_secret, hash_password

# Use test database (via docker-compose test-db service)
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://test:test@localhost:5433/escal_test",
)


@pytest.fixture(scope="session")
def test_db_engine():
    """Create test database engine and initialize schema."""
    engine = create_engine(TEST_DATABASE_URL, echo=False)
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """Provide a clean database session for each test."""
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(test_db_session):
    """Provide a test client with overridden database dependency."""
    def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_account(test_db_session):
    """Create a test account."""
    account = Account(id=uuid4(), name="Test Account")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    return account


@pytest.fixture
def test_user(test_db_session, test_account):
    """Create a test user."""
    user = User(
        id=uuid4(),
        account_id=test_account.id,
        email="testuser@example.com",
        hashed_password=hash_password("testpassword123"),
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def test_store(test_db_session, test_account):
    """Create a test store."""
    store = Store(
        id=uuid4(),
        account_id=test_account.id,
        name="Test Store",
        platform="shopify",
        currency="USD",
        timezone="UTC",
    )
    test_db_session.add(store)
    test_db_session.commit()
    test_db_session.refresh(store)
    return store


@pytest.fixture
def test_store_credential(test_db_session, test_store):
    """Create a test store credential."""
    credential = StoreCredential(
        id=uuid4(),
        store_id=test_store.id,
        provider="shopify",
        access_token=encrypt_secret("test_access_token_123"),
        refresh_token=encrypt_secret("test_refresh_token_456"),
    )
    test_db_session.add(credential)
    test_db_session.commit()
    test_db_session.refresh(credential)
    return credential


@pytest.fixture
def other_account(test_db_session):
    """Create another account for isolation testing."""
    account = Account(id=uuid4(), name="Other Account")
    test_db_session.add(account)
    test_db_session.commit()
    test_db_session.refresh(account)
    return account


@pytest.fixture
def other_user(test_db_session, other_account):
    """Create a user in a different account."""
    user = User(
        id=uuid4(),
        account_id=other_account.id,
        email="otheruser@example.com",
        hashed_password=hash_password("otherpassword123"),
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


@pytest.fixture
def auth_header(client, test_user):
    """Create an authentication header for test_user."""
    response = client.post(
        "/auth/login",
        json={"email": "testuser@example.com", "password": "testpassword123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
