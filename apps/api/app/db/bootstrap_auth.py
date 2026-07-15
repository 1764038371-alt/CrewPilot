from __future__ import annotations

import asyncio

from sqlalchemy import delete, select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.modules.auth.models import User, UserSession
from app.modules.auth.service import hash_password

DEFAULT_USER_EMAILS = (
    "admin@example.com",
    "manager@example.com",
    "viewer@example.com",
)


async def main() -> None:
    password_hash = hash_password(settings.crewpilot_login_password)
    async with AsyncSessionLocal() as session:
        users = list(await session.scalars(select(User)))
        admin_email = settings.crewpilot_admin_email.lower().strip()
        if admin_email:
            primary_user = next((user for user in users if user.email == admin_email), None)
            if primary_user is None:
                primary_user = next(
                    (user for user in users if user.email == "manager@example.com"),
                    None,
                )
            if primary_user is None:
                raise RuntimeError("CrewPilot primary user is missing")

            updated = False
            if primary_user.email != admin_email:
                primary_user.email = admin_email
                updated = True
            if primary_user.display_name != settings.crewpilot_admin_display_name:
                primary_user.display_name = settings.crewpilot_admin_display_name
                updated = True
            if primary_user.role != "admin":
                primary_user.role = "admin"
                updated = True
            if not primary_user.is_active:
                primary_user.is_active = True
                updated = True
            if primary_user.password_hash != password_hash:
                primary_user.password_hash = password_hash
                updated = True
            for user in users:
                if user.id != primary_user.id and user.is_active:
                    user.is_active = False
                    updated = True
            if updated:
                await session.execute(delete(UserSession))
                await session.commit()
                print("CrewPilot owner account synchronized; existing sessions revoked.")
            else:
                print("CrewPilot owner account already synchronized.")
            return

        default_users = [user for user in users if user.email in DEFAULT_USER_EMAILS]
        updated = False
        for user in default_users:
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
