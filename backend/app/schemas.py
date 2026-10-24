import datetime as _dt
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from .br_format import format_document, format_phone, format_state_registration
from .uploads import thumb_name


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Monthly goal in R$: optional, non-negative, finite, fits NUMERIC(12,2).
Goal = Annotated[float | None, Field(ge=0, le=9_999_999_999, allow_inf_nan=False)]


# ---------- Auth / users ----------
class LoginIn(BaseModel):
    email: str
    password: str


class UserBase(ORM):
    name: str
    email: str
    role: str = "seller"
    active: bool = True
    avatar_url: str | None = None
    theme: str = "light"
    annual_goal: Goal = None
    price_table: Literal["wholesale", "retail", "both"] = "wholesale"


class UserIn(UserBase):
    password: str | None = None
    # None = keep the current one (an older cached app doesn't send it)
    price_table: Literal["wholesale", "retail", "both"] | None = None


class UserOut(UserBase):
    id: int
    quick_quantity: bool = True  # personal preference, set in Meu perfil (not by the admin's user form)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ForgotPasswordIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


class ProfileIn(BaseModel):
    """Self-service profile update — changing the email or setting a new password requires the current password."""
    name: str = Field(min_length=2)
    email: str
    current_password: str | None = None
    new_password: str | None = None
    theme: str | None = None
    quick_quantity: bool | None = None  # None = keep (an older cached app doesn't send it)


# ---------- Customers ----------
class CustomerIn(ORM):
    """Everything but the notes is required to register a customer."""
    name: str = Field(min_length=2)
    document: str = Field(min_length=1)
    phone: str = Field(min_length=1)
    email: str = Field(min_length=1)
    city: str = Field(min_length=1)
    state: str = Field(min_length=2, max_length=2)
    address: str = Field(min_length=1)
    state_registration: str = Field(min_length=1)  # IE number, or "ISENTO"
    notes: str | None = None
    owner_id: int | None = None  # seller this customer belongs to; only admins can set/change it

    # stored already formatted, whatever the client sent (imports, old app versions)
    @field_validator("document")
    @classmethod
    def _format_document(cls, v):
        return format_document(v)

    @field_validator("phone")
    @classmethod
    def _format_phone(cls, v):
        return format_phone(v)

    @field_validator("state_registration")
    @classmethod
    def _state_registration(cls, v, info):
        if v is None:  # only reachable on CustomerOut: older records may lack it
            return v
        if not v.strip():
            raise ValueError("Informe a inscrição estadual ou marque Isento.")
        return format_state_registration(v, info.data.get("state"))  # state is declared above, so already in data


class CustomerOut(CustomerIn):
    id: int
    # older records may lack these; new ones always have them (see CustomerIn)
    document: str | None = None
    state_registration: str | None = None
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    state: str | None = None
    address: str | None = None
    owner_name: str | None = None
    created_at: datetime | None = None
    lat: float | None = None
    lng: float | None = None


# ---------- Colors / products ----------
class ColorIn(ORM):
    name: str = Field(min_length=1)
    hex: str = Field(default="#cccccc", pattern=r"^#[0-9a-fA-F]{6}$")
    hex2: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class ColorOut(ColorIn):
    id: int


class ProductIn(BaseModel):
    reference: str = Field(min_length=1)
    description: str = Field(min_length=1)
    collection: str | None = None
    price: float = Field(ge=0)
    sizes: list[str] = ["U", "P", "M", "G", "GG"]
    active: bool = True
    color_ids: list[int] = []
    seller_ids: list[int] | None = None  # users (sellers or admins) who may sell it; empty = everyone; None = keep


class ProductOut(ORM):
    id: int
    reference: str
    description: str
    collection: str | None
    price: float
    sizes: list[str]
    active: bool
    image_url: str | None
    colors: list[ColorOut]
    seller_ids: list[int]

    @computed_field
    @property
    def thumb_url(self) -> str | None:
        """Small version of the photo for lists; image_url is the full-size one (zoom)."""
        return f"/uploads/products/{thumb_name(self.image_url)}" if self.image_url else None

    @field_validator("sizes", mode="before")
    @classmethod
    def split(cls, v):
        return [t for t in v.split(",") if t] if isinstance(v, str) else v


# ---------- Orders ----------
class OrderItemIn(BaseModel):
    product_id: int
    color_id: int
    size: str
    quantity: int = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0)


class OrderIn(BaseModel):
    customer_id: int
    date: _dt.date | None = None
    delivery_date: _dt.date
    status: str = "quote"
    payment_method: str = Field(min_length=1)
    payment_terms: str = Field(min_length=1)
    price_table: Literal["wholesale", "retail"] | None = None  # None = the seller's default
    discount: float = Field(default=0, ge=0)
    notes: str | None = None
    items: list[OrderItemIn] = Field(min_length=1)


class StatusIn(BaseModel):
    status: str


# ---------- App settings ----------
class AppSettingsIn(BaseModel):
    allow_price_override: bool
    max_discount_percent: float = Field(ge=0, le=100)
    retail_markup_percent: float = Field(default=50, ge=0, le=1000)
    annual_goal: Goal = None


class AppSettingsOut(ORM):
    """What every logged-in user may read (the order form needs these rules)."""
    allow_price_override: bool
    max_discount_percent: float
    retail_markup_percent: float


class AppSettingsAdminOut(AppSettingsOut):
    annual_goal: float | None = None


# ---------- Finance ----------
Money = Annotated[float, Field(gt=0, le=9_999_999_999, allow_inf_nan=False)]


class EntryUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Money
    due_date: _dt.date
    payment_method: str | None = Field(default=None, max_length=40)
    notes: str | None = None
    supplier: str | None = Field(default=None, max_length=160)
    category: str | None = None


class EntryIn(EntryUpdate):
    kind: Literal["receivable", "payable"]
    order_id: int | None = None
    repeat_months: int = Field(default=1, ge=1, le=60)


class PayIn(BaseModel):
    paid_at: _dt.date | None = None  # default: today
    paid_amount: Money | None = None  # default: the entry's amount
    payment_method: str | None = Field(default=None, max_length=40)


class SplitIn(BaseModel):
    amount: Money
    due_date: _dt.date
