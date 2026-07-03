from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.auth.models import User, UserSession
from app.modules.auth.schemas import AuthResponse, UserRead

SESSION_COOKIE = "crewpilot_session"
SESSION_DAYS = 7


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def login(self, email: str, password: str, response: Response) -> AuthResponse:
        user = await self._get_user_by_email(email.lower().strip())
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="メールアドレスまたはパスワードが正しくありません。",
            )

        token = secrets.token_urlsafe(32)
        expires_at = utc_now() + timedelta(days=SESSION_DAYS)
        self.session.add(
            UserSession(
                user_id=user.id,
                session_token_hash=hash_token(token),
                expires_at=expires_at,
            )
        )
        await self.session.commit()
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            max_age=SESSION_DAYS * 24 * 60 * 60,
            path="/",
            samesite=settings.session_cookie_samesite,
            secure=settings.session_cookie_secure,
        )
        return AuthResponse(user=UserRead.model_validate(user), expires_at=expires_at)

    async def logout(self, request: Request, response: Response) -> dict[str, str]:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            await self.session.execute(
                delete(UserSession).where(UserSession.session_token_hash == hash_token(token))
            )
            await self.session.commit()
        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
            samesite=settings.session_cookie_samesite,
            secure=settings.session_cookie_secure,
        )
        return {"status": "ok"}

    async def current_user(self, request: Request) -> User:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            raise unauthorized()
        result = await self.session.execute(
            select(User, UserSession)
            .join(UserSession, UserSession.user_id == User.id)
            .where(UserSession.session_token_hash == hash_token(token))
        )
        row = result.first()
        if row is None:
            raise unauthorized()
        user, user_session = row
        expires_at = ensure_aware_utc(user_session.expires_at)
        if expires_at < utc_now() or not user.is_active:
            await self.session.delete(user_session)
            await self.session.commit()
            raise unauthorized()
        return user

    async def _get_user_by_email(self, email: str) -> User | None:
        result = await self.session.scalars(select(User).where(User.email == email))
        return result.first()


def hash_password(password: str, salt: str = "crewpilot-demo-salt") -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, salt, expected = password_hash.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    actual = hash_password(password, salt).split("$", 2)[2]
    return secrets.compare_digest(actual, expected)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def unauthorized() -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="ログインが必要です。")


def forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="権限がありません。")
