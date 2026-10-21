import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import extract, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Holiday, HolidayState
from ..schemas import HolidayOut, HolidayPage
from ..security import get_current_user

router = APIRouter(
    prefix="/holidays",
    tags=["holidays"],
    dependencies=[Depends(get_current_user)],
    # every route in this router now requires a valid token
)

DbSession = Annotated[Session, Depends(get_db)]


@router.get("", response_model=HolidayPage)
def list_holidays(
    db: DbSession,
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    primary_type: Annotated[str | None, Query(alias="type", max_length=80)] = None,
    state: Annotated[str | None, Query(pattern="^[A-Za-z]{2}$")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HolidayPage:
    filters = []
    if month is not None:
        filters.append(extract("month", Holiday.date) == month)
    if primary_type:
        filters.append(Holiday.primary_type == primary_type)
    if q:
        filters.append(Holiday.name.icontains(q, autoescape=True))
    if date_from:
        filters.append(Holiday.date >= date_from)
    if date_to:
        filters.append(Holiday.date <= date_to)
    if state:
        # applies to a state if nationwide OR the state is listed
        filters.append(
            or_(
                Holiday.nationwide.is_(True),
                Holiday.state_rows.any(HolidayState.abbrev == state.upper()),
            )
        )

    total = db.scalar(select(func.count()).select_from(Holiday).where(*filters)) or 0
    rows = db.scalars(
        select(Holiday).where(*filters)
        .order_by(Holiday.date, Holiday.name, Holiday.id)   # stable order => stable paging
        .offset(offset).limit(limit)
    ).all()
    return HolidayPage(
        total=total, limit=limit, offset=offset,
        items=[HolidayOut.model_validate(r) for r in rows],
    )


# must be declared BEFORE "/{holiday_id}", or "types" would be parsed as an id
@router.get("/types", response_model=list[str])
def list_types(db: DbSession) -> list[str]:
    return list(db.scalars(select(Holiday.primary_type).distinct().order_by(Holiday.primary_type)))


@router.get("/{holiday_id}", response_model=HolidayOut)
def get_holiday(holiday_id: int, db: DbSession) -> Holiday:
    holiday = db.get(Holiday, holiday_id)
    if holiday is None:
        raise HTTPException(status_code=404, detail="Holiday not found")
    return holiday