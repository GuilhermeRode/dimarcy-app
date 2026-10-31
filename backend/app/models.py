import datetime as _dt
from datetime import date, datetime

from sqlalchemy import (Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric,
                        String, Table, Text, UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

ORDER_STATUSES = ["quote", "confirmed", "in_production", "shipped", "delivered", "canceled"]
SALE_STATUSES = ["confirmed", "in_production", "shipped", "delivered"]  # count as revenue
LATE_STATUSES = ["confirmed", "in_production"]  # past delivery_date in these = late
SIZE_ORDER = ["U", "PP", "P", "M", "G", "GG", "XG", "XGG", "EG", "EGG"]  # same list as frontend/src/format.js


def size_key(size: str):
    """Sort key: known sizes in SIZE_ORDER, then numbers (36, 38...), then anything else alphabetically."""
    s = size.strip().upper()
    if s in SIZE_ORDER:
        return (0, SIZE_ORDER.index(s), "")
    return (1, int(s), "") if s.isdigit() else (2, 0, s)


PRICE_TABLES = ["wholesale", "retail"]  # wholesale = registered price; retail = + AppSettings.retail_markup_percent
ENTRY_KINDS = ["receivable", "payable"]
# Business content, so in Portuguese; a payable's category must be one of these
PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"]
LEAD_STATUSES = ["pending", "contacted", "new", "converted", "discarded"]
# pending: no contact yet · contacted: the admin talked to the store (Primeiro contato) · both admin only
# until released to the seller (new)
DISCARD_REASONS = ["closed", "not_target", "competitor", "not_recommended", "no_answer", "other"]
CONTACT_CHANNELS = ["whatsapp", "call", "visit", "email"]
NO_ANSWER = "Não respondeu"  # the note of a "Não respondeu" attempt: not a conversation with the store

ACTIVE_DAYS = 60  # lead scoring: a customer who bought this recently makes the city a proven market


def customer_status(last_purchase: date | None) -> str:
    """Active: any purchase, in the app or in the history. Inactive: none."""
    return "active" if last_purchase else "inactive"

product_color = Table(
    "product_color",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("color_id", ForeignKey("colors.id", ondelete="CASCADE"), primary_key=True),
)

# Sellers a product is restricted to; no rows = available to every seller
product_seller = Table(
    "product_seller",
    Base.metadata,
    Column("product_id", ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="seller")  # admin | seller
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    avatar_url: Mapped[str | None] = mapped_column(String(300))
    theme: Mapped[str] = mapped_column(String(10), default="light")  # light | dark — personal UI preference
    annual_goal: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)  # NULL/0 = no goal
    price_table: Mapped[str] = mapped_column(String(10), default="wholesale",
                                             server_default="wholesale")  # wholesale | retail | both
    quick_quantity: Mapped[bool] = mapped_column(Boolean, default=True)  # +1/+2 taps in the order grid (Meu perfil)
    reset_token_hash: Mapped[str | None] = mapped_column(String(64))  # sha256 hex of the forgot-password token
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    document: Mapped[str | None] = mapped_column(String(20))  # CPF/CNPJ
    state_registration: Mapped[str | None] = mapped_column(String(30))  # inscrição estadual (IE)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(160))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(250))
    lat: Mapped[float | None] = mapped_column(nullable=True)  # geocoded from city/state, best-effort
    lng: Mapped[float | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
    price_table: Mapped[str] = mapped_column(String(10), default="wholesale",
                                             server_default="wholesale")  # see PRICE_TABLES; a new order starts on it
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
    hex2: Mapped[str | None] = mapped_column(String(7))  # second tone of a two-color combo (e.g. 09/37)


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
    sellers: Mapped[list[User]] = relationship(secondary=product_seller)

    @property
    def seller_ids(self) -> list[int]:
        return [u.id for u in self.sellers]


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_date_status", "date", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    date: Mapped[_dt.date] = mapped_column(Date, default=_dt.date.today, index=True)
    delivery_date: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="quote", index=True)
    payment_method: Mapped[str | None] = mapped_column(String(40))
    payment_terms: Mapped[str | None] = mapped_column(String(80))
    price_table: Mapped[str] = mapped_column(String(10), default="wholesale",
                                             server_default="wholesale")  # see PRICE_TABLES
    discount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    notify_customer: Mapped[bool] = mapped_column(Boolean, default=True)  # off = no e-mails to the customer
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
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
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


class PastOrder(Base):
    """Purchase history from before the app (spreadsheet import): date and amount only, no items.
    Shown on the customer panel and counts for the last order date and status; kept out of revenue on purpose."""
    __tablename__ = "past_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    date: Mapped[_dt.date] = mapped_column(Date)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))


class City(Base):
    """Geocoding cache keyed by (name, state) — see geocoding.lookup_cached_city."""
    __tablename__ = "cities"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(2))
    lat: Mapped[float] = mapped_column()
    lng: Mapped[float] = mapped_column()


class AppSettings(Base):
    """Single-row table of admin-editable rules; see settings_store.get_app_settings."""
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    allow_price_override: Mapped[bool] = mapped_column(Boolean, default=False)
    max_discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    retail_markup_percent: Mapped[float] = mapped_column(Numeric(6, 2), default=50)
    annual_goal: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)  # company goal; NULL/0 = none
    lead_cnaes: Mapped[str] = mapped_column(String(200), default="4781400", server_default="4781400")  # CNAE codes, comma-separated
    last_lead_import_month: Mapped[str | None] = mapped_column(String(7))  # e.g. "2026-10"
    last_lead_import_scope: Mapped[str | None] = mapped_column(String(500))  # e.g. "PR,SC|4781400"
    last_lead_import_at: Mapped[datetime | None] = mapped_column(DateTime)  # naive UTC (the UI appends "Z")
    lead_sizes: Mapped[str] = mapped_column(String(20), default="01,03", server_default="01,03")  # Receita porte codes
    lead_exclude_mei: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_head_office_only: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_require_contact: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_min_age_months: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    lead_states: Mapped[str] = mapped_column(String(30), default="PR,RS,SC", server_default="PR,RS,SC")  # UFs imported
    lead_area_codes: Mapped[str] = mapped_column(String(60), default="", server_default="")  # DDDs imported; "" = all
    lead_weekly_release: Mapped[int] = mapped_column(Integer, default=20, server_default="20")  # suggested releases per seller
    lead_import_started_at: Mapped[datetime | None] = mapped_column(DateTime)  # naive UTC (the UI appends "Z"); set while an import runs
    lead_import_pid: Mapped[int | None] = mapped_column(Integer)  # the running importer's process id
    lead_import_error: Mapped[str | None] = mapped_column(String(300))  # last failure, cleared on success
    catalog_url: Mapped[str | None] = mapped_column(String(200))  # PDF sellers send to stores (/uploads/catalog/...)
    # off = Prospecção is admin-only for now (menu hidden, /leads and lead contacts 403 for sellers)
    leads_for_sellers: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FinancialEntry(Base):
    """A receivable installment or a payable bill — see finance.py for the rules."""
    __tablename__ = "financial_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # see ENTRY_KINDS
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[_dt.date] = mapped_column(Date, index=True)
    paid_at: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)  # NULL = still open
    paid_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    supplier: Mapped[str | None] = mapped_column(String(160))  # payables
    category: Mapped[str | None] = mapped_column(String(40))  # payables, see PAYABLE_CATEGORIES
    installment: Mapped[int | None] = mapped_column(Integer)  # "2" of "2/3"
    installments: Mapped[int | None] = mapped_column(Integer)
    attachment: Mapped[str | None] = mapped_column(String(80))  # file name in private/finance (boleto, receipt)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order | None"] = relationship()


class SellerCity(Base):
    """A city in a seller's region. Two sellers may share a city: both work its leads (see leads.py)."""
    __tablename__ = "seller_cities"
    __table_args__ = (UniqueConstraint("user_id", "city_key", "state", name="uq_seller_cities_user_city"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    city_key: Mapped[str] = mapped_column(String(100))  # sales._city_key(city)
    user: Mapped[User] = relationship()


class Lead(Base):
    """A store from the Receita's open CNPJ data that isn't a customer yet. Its seller is never
    stored: it's whoever has the lead's city in seller_cities (see leads.city_owners)."""
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_area", "state", "city_key", "status"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str | None] = mapped_column(String(14), unique=True)  # leads.normalize_cnpj; None = "a confirmar", the order asks for it
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    city_key: Mapped[str] = mapped_column(String(100))
    opened_at: Mapped[_dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="new", server_default="new")  # see LEAD_STATUSES
    size: Mapped[str] = mapped_column(String(5), default="", server_default="")  # mei | me | epp | large | ""
    discard_reason: Mapped[str | None] = mapped_column(String(30))  # see DISCARD_REASONS
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    seen_at: Mapped[_dt.date] = mapped_column(Date)  # last import that listed this CNPJ
    capital: Mapped[float | None] = mapped_column(Numeric(14, 2))  # capital social (Receita Empresas)
    in_debt: Mapped[bool | None] = mapped_column(Boolean)  # PGFN dívida ativa "em cobrança"; None = not checked
    released_at: Mapped[datetime | None] = mapped_column(DateTime)  # naive UTC, pending -> new
    # ranking, stored so the list can ORDER BY ... LIMIT in SQL (leads.refresh_scores; daily and after imports)
    score: Mapped[int | None] = mapped_column(Integer)  # leads.lead_score
    city_active: Mapped[int | None] = mapped_column(Integer)  # active Di Marcy customers in the city (tie-break)
    edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")  # admin fixed name/contact: the import keeps them
    notes: Mapped[str | None] = mapped_column(Text)  # free text, unlike a contact it isn't an event in the history


class Contact(Base):
    """One touch with a lead or a customer (exactly one of them). The latest contact's
    next_action_date is the pending follow-up — see leads.due_follow_ups."""
    __tablename__ = "contacts"
    __table_args__ = (CheckConstraint("(lead_id IS NULL) <> (customer_id IS NULL)", name="ck_contacts_one_target"), {"sqlite_autoincrement": True})
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))  # see CONTACT_CHANNELS
    notes: Mapped[str | None] = mapped_column(Text)
    next_action_date: Mapped[_dt.date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user: Mapped[User] = relationship()
    lead: Mapped[Lead | None] = relationship()
    customer: Mapped[Customer | None] = relationship()
