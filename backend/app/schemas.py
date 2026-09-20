import datetime as _dt
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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


class UserIn(UserBase):
    password: str | None = None


class UserOut(UserBase):
    id: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class ProfileIn(BaseModel):
    """Self-service profile update — changing the email or setting a new password requires the current password."""
    name: str = Field(min_length=2)
    email: str
    current_password: str | None = None
    new_password: str | None = None
    theme: str | None = None


# ---------- Customers ----------
class CustomerIn(ORM):
    name: str = Field(min_length=2)
    document: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    address: str | None = None
    notes: str | None = None
    owner_id: int | None = None  # seller this customer belongs to; only admins can set/change it


class CustomerOut(CustomerIn):
    id: int
    document: str | None = None  # older records may not have one; new ones always do (see CustomerIn)
    owner_name: str | None = None
    created_at: datetime | None = None


# ---------- Colors / products ----------
class ColorIn(ORM):
    name: str = Field(min_length=1)
    hex: str = Field(default="#cccccc", pattern=r"^#[0-9a-fA-F]{6}$")


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
    discount: float = Field(default=0, ge=0)
    notes: str | None = None
    items: list[OrderItemIn] = Field(min_length=1)


class StatusIn(BaseModel):
    status: str
