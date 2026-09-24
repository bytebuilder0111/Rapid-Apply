import io
from unittest.mock import AsyncMock, patch

from docx import Document
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.schemas import ResumeSummary
from app.models import Role

from .conftest import create_user, login_headers

RESUME_TEXT = (
    "Jane Doe. Senior Backend Engineer with 8 years of experience building Python and "
    "Django REST APIs, PostgreSQL data models, Celery workers and AWS deployments for "
    "fintech and e-commerce platforms."
)
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf_bytes(text: str) -> bytes:
    """A minimal single-page text PDF, written by hand so tests need no PDF-writing library."""
    stream = f"BT /F1 10 Tf 20 800 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 2000 842] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % i + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for off in offsets:
        out.write(b"%010d 00000 n \n" % off)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    )
    return out.getvalue()


async def _client_with_key_and_resume_type(
    client: AsyncClient, db_session: AsyncSession, *, email: str, with_key: bool = True
) -> tuple[dict, str]:
    await create_user(db_session, email=email, role=Role.CLIENT)
    headers = await login_headers(client, email=email)
    if with_key:
        await client.put(
            "/api/v1/integrations/openai",
            headers=headers,
            json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
        )
    resp = await client.post("/api/v1/profiles", headers=headers, json={"name": "Python Backend"})
    assert resp.status_code == 201, resp.text
    return headers, resp.json()["id"]


def _summary_mock() -> AsyncMock:
    return AsyncMock(
        return_value=ResumeSummary(
            summary="Senior backend engineer, 8 years, Python/Django APIs on AWS.",
            key_skills=["Python", "Django", "PostgreSQL", "AWS"],
        )
    )


async def test_upload_docx_resume_stores_only_summary(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="docxupload@example.com"
    )

    summarize = _summary_mock()
    with patch("app.profiles.service.summarize_resume", new=summarize):
        resp = await client.post(
            f"/api/v1/profiles/{profile_id}/resume",
            headers=headers,
            files={"file": ("jane.docx", _docx_bytes(RESUME_TEXT), DOCX_MIME)},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["resume_filename"] == "jane.docx"
    assert body["resume_summary"] == "Senior backend engineer, 8 years, Python/Django APIs on AWS."
    assert body["skills"] == ["Python", "Django", "PostgreSQL", "AWS"]
    assert body["resume_uploaded_at"] is not None
    assert "Celery workers" in summarize.call_args.kwargs["resume_text"]
    assert summarize.call_args.kwargs["model"] == "gpt-4o-mini"


async def test_upload_pdf_resume(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="pdfupload@example.com"
    )

    summarize = _summary_mock()
    with patch("app.profiles.service.summarize_resume", new=summarize):
        resp = await client.post(
            f"/api/v1/profiles/{profile_id}/resume",
            headers=headers,
            files={"file": ("jane.pdf", _pdf_bytes(RESUME_TEXT), "application/pdf")},
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["resume_filename"] == "jane.pdf"
    assert "Django REST APIs" in summarize.call_args.kwargs["resume_text"]


async def test_upload_rejects_unsupported_file_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="txtupload@example.com"
    )

    summarize = _summary_mock()
    with patch("app.profiles.service.summarize_resume", new=summarize):
        resp = await client.post(
            f"/api/v1/profiles/{profile_id}/resume",
            headers=headers,
            files={"file": ("resume.txt", RESUME_TEXT.encode(), "text/plain")},
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_file"
    summarize.assert_not_called()


async def test_upload_rejects_file_without_readable_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="emptyupload@example.com"
    )

    resp = await client.post(
        f"/api/v1/profiles/{profile_id}/resume",
        headers=headers,
        files={"file": ("empty.docx", _docx_bytes(""), DOCX_MIME)},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "resume_unreadable"


async def test_upload_requires_openai_key(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="nokeyupload@example.com", with_key=False
    )

    resp = await client.post(
        f"/api/v1/profiles/{profile_id}/resume",
        headers=headers,
        files={"file": ("jane.docx", _docx_bytes(RESUME_TEXT), DOCX_MIME)},
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_api_key"


async def test_only_owning_client_can_upload(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id = await _client_with_key_and_resume_type(
        client, db_session, email="uploadowner@example.com"
    )
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(db_session, email="uploadstranger@example.com", role=Role.CLIENT)
    await create_user(
        db_session, email="uploadbidder@example.com", role=Role.BIDDER, client_id=me["id"]
    )
    file = {"file": ("jane.docx", _docx_bytes(RESUME_TEXT), DOCX_MIME)}

    stranger = await client.post(
        f"/api/v1/profiles/{profile_id}/resume",
        headers=await login_headers(client, email="uploadstranger@example.com"),
        files=file,
    )
    bidder = await client.post(
        f"/api/v1/profiles/{profile_id}/resume",
        headers=await login_headers(client, email="uploadbidder@example.com"),
        files=file,
    )

    assert stranger.status_code == 404
    assert bidder.status_code == 403


async def test_client_cannot_see_another_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="owner@example.com", role=Role.CLIENT)
    await create_user(db_session, email="stranger@example.com", role=Role.CLIENT)

    owner_headers = await login_headers(client, email="owner@example.com")
    stranger_headers = await login_headers(client, email="stranger@example.com")

    create_resp = await client.post(
        "/api/v1/profiles", headers=owner_headers, json={"name": "Java/Spring"}
    )
    assert create_resp.status_code == 201
    profile_id = create_resp.json()["id"]

    owner_list = await client.get("/api/v1/profiles", headers=owner_headers)
    assert [p["id"] for p in owner_list.json()] == [profile_id]

    stranger_list = await client.get("/api/v1/profiles", headers=stranger_headers)
    assert stranger_list.json() == []

    stranger_get = await client.get(f"/api/v1/profiles/{profile_id}", headers=stranger_headers)
    assert stranger_get.status_code == 404

    stranger_update = await client.patch(
        f"/api/v1/profiles/{profile_id}", headers=stranger_headers, json={"name": "Hijacked"}
    )
    assert stranger_update.status_code == 404

    stranger_delete = await client.delete(
        f"/api/v1/profiles/{profile_id}", headers=stranger_headers
    )
    assert stranger_delete.status_code == 404


async def test_bidder_sees_only_their_clients_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    owner = await create_user(db_session, email="owner2@example.com", role=Role.CLIENT)
    await create_user(db_session, email="owner3@example.com", role=Role.CLIENT)
    await create_user(
        db_session,
        email="bidder-scope@example.com",
        role=Role.BIDDER,
        client_id=owner.id,
    )

    owner_headers = await login_headers(client, email="owner2@example.com")
    other_headers = await login_headers(client, email="owner3@example.com")
    bidder_headers = await login_headers(client, email="bidder-scope@example.com")

    await client.post("/api/v1/profiles", headers=owner_headers, json={"name": "PHP/Laravel"})
    await client.post("/api/v1/profiles", headers=other_headers, json={"name": "Ruby/Rails"})

    bidder_list = await client.get("/api/v1/profiles", headers=bidder_headers)
    assert bidder_list.status_code == 200
    names = {p["name"] for p in bidder_list.json()}
    assert names == {"PHP/Laravel"}

    bidder_create = await client.post(
        "/api/v1/profiles", headers=bidder_headers, json={"name": "Should Fail"}
    )
    assert bidder_create.status_code == 403


async def test_admin_requires_client_id_to_list_profiles(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_user(db_session, email="admin-profiles@example.com", role=Role.ADMIN)
    headers = await login_headers(client, email="admin-profiles@example.com")

    resp = await client.get("/api/v1/profiles", headers=headers)

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "client_id_required"
