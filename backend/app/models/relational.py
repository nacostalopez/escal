import uuid

from sqlalchemy import Column, String, Numeric, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    stores = relationship("Store", back_populates="account", cascade="all, delete-orphan")
    users = relationship("User", back_populates="account", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"))
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="users")


class Store(Base):
    __tablename__ = "stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    currency = Column(String(3), default="USD")
    timezone = Column(String(50), default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="stores")
    credentials = relationship("StoreCredential", back_populates="store", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="store", cascade="all, delete-orphan")


class StoreCredential(Base):
    __tablename__ = "store_credentials"
    __table_args__ = (UniqueConstraint("store_id", "provider", name="uq_store_provider"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"))
    provider = Column(String(50), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String)
    expires_at = Column(DateTime(timezone=True))

    store = relationship("Store", back_populates="credentials")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("store_id", "external_id", name="uq_store_external_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"))
    external_id = Column(String(255), nullable=False)
    sku = Column(String(100))
    title = Column(String(255), nullable=False)
    cogs = Column(Numeric(12, 4), default=0.0)
    shipping_cost = Column(Numeric(12, 4), default=0.0)

    store = relationship("Store", back_populates="products")
