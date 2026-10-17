from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import city_owners, lead_out, lead_owner, ranked_leads, visible_lead
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("")
def list_leads(city: str = "", search: str = "", seller_id: int | None = None,
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = ranked_leads(db, user, clock.today_br(), city, search,
                        seller_id if user.role == "admin" else None)
    return {"items": [lead_out(lead, owner) for lead, owner in rows[offset:offset + limit]], "total": len(rows),
            "cities": sorted({lead.city for lead, _ in rows})}  # for the screen's city filter


@router.get("/{lid}")
def get_lead(lid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = visible_lead(db, user, lid)
    return lead_out(lead, lead_owner(city_owners(db), lead))
