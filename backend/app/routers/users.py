from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Lead, SellerCity, User
from ..sales import _city_key
from ..schemas import CityIn, CityOut, UserIn, UserOut
from ..security import MIN_PASSWORD_LENGTH, hash_password, require_admin

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_all(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.name).all()


@router.post("", response_model=UserOut, status_code=201)
def create(data: UserIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "A user with this email already exists.")
    if not data.password or len(data.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(400, f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    u = User(name=data.name, email=email, role=data.role, active=data.active,
              password_hash=hash_password(data.password), annual_goal=data.annual_goal,
              price_table=data.price_table or "wholesale")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.put("/{uid}", response_model=UserOut)
def update(uid: int, data: UserIn, db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    u.name, u.email, u.role, u.active = data.name, data.email.strip().lower(), data.role, data.active
    u.annual_goal = data.annual_goal
    if data.price_table:
        u.price_table = data.price_table
    if data.password:
        if len(data.password) < MIN_PASSWORD_LENGTH:
            raise HTTPException(400, f"The password must be at least {MIN_PASSWORD_LENGTH} characters long.")
        u.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(u)
    return u


def _clean_city(city: str, state: str) -> tuple[str, str]:
    return " ".join(city.split()), state.strip().upper()


@router.get("/cities/options", response_model=list[CityOut])
def city_options(db: Session = Depends(get_db)):
    """Cities to pick from when building a region: customers' spelling first, then the leads'."""
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    rows = db.query(Customer.city, Customer.state).filter(Customer.city.isnot(None)).distinct().all()
    rows += db.query(Lead.city, Lead.state).distinct().all()
    for city, state in rows:
        city, state = _clean_city(city or "", state or "")
        if city:
            seen.setdefault((_city_key(city), state), (city, state))
    return sorted(({"city": c, "state": s} for c, s in seen.values()), key=lambda x: (x["city"], x["state"]))


@router.get("/{uid}/cities", response_model=list[CityOut])
def get_cities(uid: int, db: Session = Depends(get_db)):
    return db.query(SellerCity).filter(SellerCity.user_id == uid).order_by(SellerCity.city).all()


@router.put("/{uid}/cities", response_model=list[CityOut])
def set_cities(uid: int, data: list[CityIn], db: Session = Depends(get_db)):
    """Replaces the seller's region. A city already in another seller's region -> 409."""
    if not db.get(User, uid):
        raise HTTPException(404, "User not found.")
    others = {(sc.city_key, sc.state): sc for sc in db.query(SellerCity).filter(SellerCity.user_id != uid)}
    wanted: dict[tuple[str, str], str] = {}
    for item in data:
        city, state = _clean_city(item.city, item.state)
        if not city:
            raise HTTPException(422, "Informe o nome da cidade.")
        key = (_city_key(city), state)
        if key in others:
            raise HTTPException(409, f"{city} já é da região de {others[key].user.name}.")
        wanted.setdefault(key, city)
    db.query(SellerCity).filter(SellerCity.user_id == uid).delete()
    for (key, state), city in wanted.items():
        db.add(SellerCity(user_id=uid, city=city, state=state, city_key=key))
    try:
        db.commit()
    except IntegrityError:  # another admin saved the same city at the same moment
        db.rollback()
        raise HTTPException(409, "Uma das cidades acabou de ser incluída na região de outro vendedor.")
    return get_cities(uid, db)


@router.get("/{uid}/cities/suggestions")
def city_suggestions(uid: int, db: Session = Depends(get_db)):
    """The seller's customers' cities, each with the name of the other seller who already has it."""
    others = {(sc.city_key, sc.state): sc.user.name
              for sc in db.query(SellerCity).filter(SellerCity.user_id != uid)}
    seen: dict[tuple[str, str], dict] = {}
    for city, state in db.query(Customer.city, Customer.state).filter(
            Customer.owner_id == uid, Customer.city.isnot(None)).distinct():
        city, state = _clean_city(city or "", state or "")
        key = (_city_key(city), state)
        if city and key not in seen:
            seen[key] = {"city": city, "state": state, "taken_by": others.get(key)}
    return sorted(seen.values(), key=lambda x: x["city"])
