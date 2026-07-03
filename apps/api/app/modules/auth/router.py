from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.modules.auth.dependencies import CurrentUserDep
from app.modules.auth.schemas import AuthResponse, LoginRequest, UserRead
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response, session: SessionDep) -> AuthResponse:
    return await AuthService(session).login(payload.email, payload.password, response)


@router.post("/logout")
async def logout(request: Request, response: Response, session: SessionDep) -> dict[str, str]:
    return await AuthService(session).logout(request, response)


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUserDep) -> UserRead:
    return UserRead.model_validate(user)
