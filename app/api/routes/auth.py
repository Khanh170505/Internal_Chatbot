from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import UserRole
from app.schemas.api import LoginRequest, LoginResponse
from app.services.auth import create_or_get_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = create_or_get_user(db, email=payload.email, name=payload.name, role=UserRole(payload.role))
    return LoginResponse(token=user.id, user_id=user.id, email=user.email, role=user.role.value)
