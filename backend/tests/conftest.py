import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest_asyncio
from dotenv import dotenv_values, load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

# Must run before any `app.*` import: app.config.Settings() reads DATABASE_URL at
# import time. .env.test points at a separate Neon branch so drop_all/create_all
# below can never touch the real dev/prod database, no matter what's in .env.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_TEST_PATH = _BACKEND_DIR / ".env.test"
if not _ENV_TEST_PATH.exists():
    raise RuntimeError(
        "backend/.env.test is missing. Tests refuse to run without it, since without "
        "it they'd fall back to DATABASE_URL in .env and drop/recreate your real "
        "database. Create backend/.env.test with a DATABASE_URL pointing at a "
        "separate test database (e.g. a Neon branch)."
    )

_test_db_url = dotenv_values(_ENV_TEST_PATH).get("DATABASE_URL")
_main_db_url = dotenv_values(_BACKEND_DIR / ".env").get("DATABASE_URL")
if _test_db_url and _test_db_url == _main_db_url:
    raise RuntimeError(
        "backend/.env.test has the same DATABASE_URL as backend/.env. Refusing to run "
        "tests: they would drop/recreate your real database. Point .env.test at a "
        "separate database (e.g. a different Neon branch)."
    )

load_dotenv(_ENV_TEST_PATH, override=True)

from app.auth.service import hash_password  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.tech_stacks.models import TechStack  # noqa: E402

# create_all (below) builds an empty schema; the real seed data lives in the 0003
# migration, which tests don't run. Mirror it here so profile tests have stacks to use.
SEED_TECH_STACKS = [
    "Python/Django",
    "Node.js/NestJS",
    "Java/Spring",
    "Go",
    ".NET",
    "PHP/Laravel",
    "Ruby/Rails",
]


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _prepare_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        session.add_all([TechStack(name=name) for name in SEED_TECH_STACKS])
        await session.commit()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # A session for the test's own setup/assertions only. The app under test gets
    # its own session per request via the real get_db (same engine) — sharing one
    # AsyncSession between concurrent tasks trips asyncpg's "operation in progress".
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # https, not http: the refresh cookie is Secure, and httpx's cookie jar (like a
    # real browser) won't resend a Secure cookie over a plain http:// request.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


async def create_user(
    db_session: AsyncSession,
    *,
    email: str,
    password: str = "s3cret-pass",
    role: Role = Role.CLIENT,
    is_active: bool = True,
    client_id: uuid.UUID | None = None,
    assigned_profile_id: uuid.UUID | None = None,
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        name="Test User",
        role=role,
        is_active=is_active,
        client_id=client_id,
        assigned_profile_id=assigned_profile_id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def login_headers(client: AsyncClient, *, email: str, password: str = "s3cret-pass") -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
