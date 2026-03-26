from fastapi import Depends, Request

from app.models.user import User
from app.services.auth import get_current_user
from app.services.rate_limit import rate_limiter


def enforce_rate_limit(request: Request, user: User = Depends(get_current_user)) -> User:
    key = f"{user.id}:{request.url.path}"
    rate_limiter.check(key)
    return user
