import asyncio

from sqlalchemy import func, select

from app.auth.service import hash_password
from app.config import settings
from app.db import SessionLocal
from app.models import Role, User


async def seed() -> None:
    async with SessionLocal() as session:
        username = settings.admin_username
        result = await session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        if result.scalar_one_or_none() is not None:
            print(f"Admin user {username} already exists, skipping.")
            return

        admin = User(
            username=username,
            password_hash=hash_password(settings.admin_password),
            name="Admin",
            role=Role.ADMIN,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"Created admin user {username}.")


if __name__ == "__main__":
    asyncio.run(seed())
