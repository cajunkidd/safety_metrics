from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ROLE_ADMIN, User


class AuthRedirect(Exception):
    """Raised when an unauthenticated user hits a protected route."""


class SetupRequired(Exception):
    """Raised when the application has no users yet."""


# bcrypt only uses the first 72 bytes of the password; truncate to avoid
# unexpected errors on newer bcrypt versions.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not hashed:
        return False
    try:
        payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(payload, hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> Optional[User]:
    # If no users exist anywhere, every non-setup request should bounce to /setup.
    if not request.url.path.startswith("/setup") and db.query(User).first() is None:
        raise SetupRequired()

    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get(User, user_id)


def require_user(user: Optional[User] = Depends(get_current_user)) -> User:
    if user is None:
        raise AuthRedirect()
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return user
