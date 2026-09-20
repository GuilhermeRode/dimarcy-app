import datetime as _dt
from datetime import date, datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, ForeignKey, Integer, Numeric,
                        String, Table, Text, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ORDER_STATUSES = ["quote", "confirmed", "in_production", "shipped", "delivered", "canceled"]
SALE_STATUSES = ["confirmed", "in_production", "shipped", "delivered"]  # count as revenue

product_color = Table(
    "product_color",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("color_id", ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="seller")  # admin | seller
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    document: Mapped[str | None] = mapped_column(String(20))  # CPF/CNPJ
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(250))
    notes: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # seller this customer belongs to
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id])

    @property
    def owner_name(self) -> str | None:
        return self.owner.name if self.owner else None


class Color(Base):
    __tablename__ = "colors"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    hex: Mapped[str] = mapped_column(String(7), default="#cccccc")


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(200))
    collection: Mapped[str | None] = mapped_column(String(80))
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    sizes: Mapped[str] = mapped_column(String(60), default="U,P,M,G,GG")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    image_url: Mapped[str | None] = mapped_column(String(300))
    colors: Mapped[list[Color]] = relationship(secondary=product_color, order_by=Color.name)


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[_dt.date] = mapped_column(Date, default=_dt.date.today, index=True)
    delivery_date: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="quote", index=True)
    payment_method: Mapped[str | None] = mapped_column(String(40))
    payment_terms: Mapped[str | None] = mapped_column(String(80))
    discount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    customer: Mapped[Customer] = relationship(back_populates="orders")
    seller: Mapped[User] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def gross(self) -> float:
        return sum(i.subtotal for i in self.items)

    @property
    def total(self) -> float:
        return round(self.gross - float(self.discount or 0), 2)

    @property
    def pieces(self) -> int:
        return sum(i.quantity for i in self.items)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("colors.id"))
    size: Mapped[str] = mapped_column(String(5))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product] = relationship(lazy="joined")
    color: Mapped[Color] = relationship(lazy="joined")

    @property
    def subtotal(self) -> float:
        return round(float(self.unit_price) * self.quantity, 2)
