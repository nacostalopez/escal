from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import DashboardLayout, User
from app.schemas.dashboard import DEFAULT_WIDGETS, DashboardLayoutIn, DashboardLayoutOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/layout", response_model=DashboardLayoutOut)
def get_layout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Per-user, not per-account or per-store — each teammate arranges their
    own view. No saved row yet means the default (every widget, True ROAS
    as hero), matching the dashboard's original fixed layout."""
    row = db.get(DashboardLayout, current_user.id)
    return DashboardLayoutOut(widgets=row.widgets if row else DEFAULT_WIDGETS)


@router.put("/layout", response_model=DashboardLayoutOut)
def set_layout(
    payload: DashboardLayoutIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Replaces the whole layout — simplest contract for a frontend that
    always sends the full widget list after any add/remove/reorder/hero
    change. Any role (including viewer) may customize their own dashboard;
    this doesn't touch shared data, just a personal display preference."""
    widgets_json = [w.model_dump() for w in payload.widgets]
    row = db.get(DashboardLayout, current_user.id)
    if row:
        row.widgets = widgets_json
    else:
        row = DashboardLayout(user_id=current_user.id, widgets=widgets_json)
        db.add(row)
    db.commit()

    return DashboardLayoutOut(widgets=payload.widgets)
