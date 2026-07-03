from __future__ import annotations

import asyncio

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.auth.models import User
from app.modules.auth.service import hash_password

DEFAULT_USER_EMAILS = (
    "admin@example.com",
    "manager@example.com",
    "viewer@example.com",
)


async def main() -> None:
    password_hash = hash_password(settings.crewpilot_login_password)
    async with AsyncSessionLocal() as session:
        users = await session.scalars(select(User).where(User.email.in_(DEFAULT_USER_EMAILS)))
        updated = False
        for user in users:
            if user.password_hash != password_hash:
                user.password_hash = password_hash
                updated = True
        if updated:
            await session.commit()
            print("Default CrewPilot login password synchronized.")
        else:
            print("Default CrewPilot login password already synchronized.")


if __name__ == "__main__":
    asyncio.run(main())
