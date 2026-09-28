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


async def _client_with_resume_type(
    client: AsyncClient, db_session: AsyncSession, *, email: str, with_key: bool = True
) -> tuple[dict, str, str]:
    """(headers, profile_id, resume_type_id) for a new client with one profile + resume type."""
    await create_user(db_session, email=email, role=Role.CLIENT)
    headers = await login_headers(client, email=email)
    if with_key:
        await client.put(
            "/api/v1/integrations/openai",
            headers=headers,
            json={"api_key": "sk-testkey1234", "model": "gpt-4o-mini"},
        )
    profile = await client.post("/api/v1/profiles", headers=headers, json={"name": "Jane Doe"})
    assert profile.status_code == 201, profile.text
    resp = await client.post(
        "/api/v1/resume-types",
        headers=headers,
        json={"profile_id": profile.json()["id"], "name": "Python Backend"},
    )
    assert resp.status_code == 201, resp.text
    return headers, profile.json()["id"], resp.json()["id"]


def _summary_mock() -> AsyncMock:
    return AsyncMock(
        return_value=ResumeSummary(
            summary="Senior backend engineer, 8 years, Python/Django APIs on AWS.",
            key_skills=["Python", "Django", "PostgreSQL", "AWS"],
        )
    )


def _upload(client: AsyncClient, headers: dict, resume_type_id: str, name: str, data: bytes, mime):
    return client.post(
        f"/api/v1/resume-types/{resume_type_id}/resume",
        headers=headers,
        files={"file": (name, data, mime)},
    )


async def test_resume_types_belong_to_a_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id, rt_id = await _client_with_resume_type(
        client, db_session, email="rtlist@example.com"
    )
    other = await client.post("/api/v1/profiles", headers=headers, json={"name": "Someone Else"})
    await client.post(
        "/api/v1/resume-types",
        headers=headers,
        json={"profile_id": other.json()["id"], "name": "Go"},
    )

    mine = await client.get(
        "/api/v1/resume-types", headers=headers, params={"profile_id": profile_id}
    )
    assert [r["id"] for r in mine.json()] == [rt_id]
    assert mine.json()[0]["profile_id"] == profile_id
    everything = await client.get("/api/v1/resume-types", headers=headers)
    assert {r["name"] for r in everything.json()} == {"Python Backend", "Go"}


async def test_cannot_add_resume_type_to_another_clients_profile(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _, profile_id, _ = await _client_with_resume_type(
        client, db_session, email="rtowner@example.com"
    )
    await create_user(db_session, email="rtstranger@example.com", role=Role.CLIENT)
    stranger = await login_headers(client, email="rtstranger@example.com")

    resp = await client.post(
        "/api/v1/resume-types",
        headers=stranger,
        json={"profile_id": profile_id, "name": "Hijack"},
    )
    assert resp.status_code == 404


async def test_bidder_sees_only_assigned_profiles_resume_types(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, profile_id, rt_id = await _client_with_resume_type(
        client, db_session, email="rtbidowner@example.com"
    )
    other = await client.post("/api/v1/profiles", headers=headers, json={"name": "Other"})
    await client.post(
        "/api/v1/resume-types",
        headers=headers,
        json={"profile_id": other.json()["id"], "name": "Go"},
    )
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(
        db_session,
        email="rtbidder@example.com",
        role=Role.BIDDER,
        client_id=me["id"],
        assigned_profile_id=profile_id,
    )
    bidder = await login_headers(client, email="rtbidder@example.com")

    resp = await client.get("/api/v1/resume-types", headers=bidder)
    assert [r["id"] for r in resp.json()] == [rt_id]
    create = await client.post(
        "/api/v1/resume-types", headers=bidder, json={"profile_id": profile_id, "name": "X"}
    )
    assert create.status_code == 403


async def test_upload_docx_resume_stores_only_summary(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, _, rt_id = await _client_with_resume_type(
        client, db_session, email="docxupload@example.com"
    )
    summarize = _summary_mock()
    with patch("app.resume_types.service.summarize_resume", new=summarize):
        resp = await _upload(
            client, headers, rt_id, "jane.docx", _docx_bytes(RESUME_TEXT), DOCX_MIME
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
    headers, _, rt_id = await _client_with_resume_type(
        client, db_session, email="pdfupload@example.com"
    )
    summarize = _summary_mock()
    with patch("app.resume_types.service.summarize_resume", new=summarize):
        resp = await _upload(
            client, headers, rt_id, "jane.pdf", _pdf_bytes(RESUME_TEXT), "application/pdf"
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["resume_filename"] == "jane.pdf"
    assert "Django REST APIs" in summarize.call_args.kwargs["resume_text"]


async def test_upload_rejects_unsupported_file_type(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, _, rt_id = await _client_with_resume_type(
        client, db_session, email="txtupload@example.com"
    )
    summarize = _summary_mock()
    with patch("app.resume_types.service.summarize_resume", new=summarize):
        resp = await _upload(client, headers, rt_id, "cv.txt", RESUME_TEXT.encode(), "text/plain")

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "unsupported_file"
    summarize.assert_not_called()


async def test_upload_rejects_file_without_readable_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers, _, rt_id = await _client_with_resume_type(
        client, db_session, email="emptyupload@example.com"
    )
    resp = await _upload(client, headers, rt_id, "empty.docx", _docx_bytes(""), DOCX_MIME)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "resume_unreadable"


async def test_upload_requires_openai_key(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, _, rt_id = await _client_with_resume_type(
        client, db_session, email="nokeyupload@example.com", with_key=False
    )
    resp = await _upload(client, headers, rt_id, "jane.docx", _docx_bytes(RESUME_TEXT), DOCX_MIME)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "no_api_key"


async def test_only_owning_client_can_upload(client: AsyncClient, db_session: AsyncSession) -> None:
    headers, profile_id, rt_id = await _client_with_resume_type(
        client, db_session, email="uploadowner@example.com"
    )
    me = (await client.get("/api/v1/auth/me", headers=headers)).json()
    await create_user(db_session, email="uploadstranger@example.com", role=Role.CLIENT)
    await create_user(
        db_session,
        email="uploadbidder@example.com",
        role=Role.BIDDER,
        client_id=me["id"],
        assigned_profile_id=profile_id,
    )
    data = _docx_bytes(RESUME_TEXT)

    stranger = await _upload(
        client,
        await login_headers(client, email="uploadstranger@example.com"),
        rt_id,
        "jane.docx",
        data,
        DOCX_MIME,
    )
    bidder = await _upload(
        client,
        await login_headers(client, email="uploadbidder@example.com"),
        rt_id,
        "jane.docx",
        data,
        DOCX_MIME,
    )
    assert stranger.status_code == 404
    assert bidder.status_code == 403
