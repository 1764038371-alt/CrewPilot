from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.auth.models import User
from app.modules.auth.service import AuthService, forbidden

SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    return await AuthService(session).current_user(request)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: str):
    async def dependency(user: CurrentUserDep) -> User:
        if user.role == "admin" or user.role in roles:
            return user
        raise forbidden()

    return dependency


ManagerUserDep = Annotated[User, Depends(require_roles("manager"))]
AdminUserDep = Annotated[User, Depends(require_roles("admin"))]
