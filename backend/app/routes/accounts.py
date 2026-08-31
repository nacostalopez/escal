from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.models import User
from app.schemas.accounts import AccountOut

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/me", response_model=AccountOut)
def get_my_account(current_user: User = Depends(get_current_user)):
    return current_user.account
