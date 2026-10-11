from app.ai.errors import AIPermanentError, AITransientError
from app.models.enums import Category, Priority
from tests.conftest import create_ticket
from tests.dataset import FIRST_BOOK, SECOND_BOOK


async def test_create_ticket_for_book_runs_ai_and_is_listed(client, author_headers, admin_headers, provider):
    provider.classification = provider.classification.model_copy(
        update={"category": Category.ISBN, "priority": Priority.MEDIUM}
    )
    created = await create_ticket(client, author_headers, subject="ISBN mismatch",
                                  description="The ISBN on Amazon is different from the one printed in my book.")
    assert created["ticket_id"].startswith("TKT-") and created["status"] == "OPEN"
    assert created["book"]["book_id"] == FIRST_BOOK["book_id"]

    listing = (await client.get("/api/v1/tickets", headers=author_headers)).json()
    assert [t["ticket_id"] for t in listing] == [created["ticket_id"]]

    detail = (await client.get(f"/api/v1/admin/tickets/{created['ticket_id']}", headers=admin_headers)).json()
    assert detail["ticket"]["ai_status"] == "COMPLETED"
    assert detail["ticket"]["category"] == "ISBN & Metadata Issues"
    assert detail["ticket"]["priority"] == "HIGH"  # guardrail raised MEDIUM -> HIGH (ISBN error)
    assert detail["ticket"]["priority_source"] == "RULE"
    assert detail["ai_draft"]["draft"].startswith("Hi there")
    assert {k["section"] for k in detail["knowledge_used"]} >= {"isbn_policy", "communication_guidelines"}
    assert [r["operation"] for r in detail["ai_runs"]].count("classify") == 1


async def test_create_general_ticket_without_book(client, author_headers):
    created = await create_ticket(client, author_headers, book_id=None, subject="Update my bio",
                                  description="Please update my author bio on all listings.")
    assert created["book"] is None


async def test_ticket_for_someone_elses_book_is_rejected(client, author_headers):
    r = await client.post("/api/v1/tickets", headers=author_headers,
                          json={"book_id": SECOND_BOOK["book_id"], "subject": "Not mine", "description": "This book is not mine at all."})
    assert r.status_code == 404 and r.json()["error"]["code"] == "BOOK_NOT_FOUND"


async def test_ticket_validation(client, author_headers):
    r = await client.post("/api/v1/tickets", headers=author_headers, json={"book_id": None, "subject": "x", "description": "short"})
    assert r.status_code == 422


async def test_ticket_is_created_even_when_ai_fails(client, author_headers, admin_headers, provider):
    provider.classify_errors = [AITransientError("503", status_code=503)] * 5
    created = await create_ticket(client, author_headers, description="My royalty has not been paid and I am worried.")
    assert created["status"] == "OPEN"  # 201 regardless of AI

    detail = (await client.get(f"/api/v1/admin/tickets/{created['ticket_id']}", headers=admin_headers)).json()
    assert detail["ticket"]["ai_status"] == "FAILED"
    assert detail["ai_draft"] is None
    assert detail["ticket"]["priority_source"] == "RULE"  # deterministic fallback, ticket still triaged
    assert provider.classify_calls == 3  # retried up to AI_MAX_RETRIES then gave up
    assert any(r["status"] == "FAILED" and r["attempts"] == 3 for r in detail["ai_runs"])


async def test_permanent_ai_error_is_not_retried(client, author_headers, provider):
    provider.classify_errors = [AIPermanentError("401 bad key", status_code=401)]
    await create_ticket(client, author_headers)
    assert provider.classify_calls == 1


async def test_transient_error_recovers_on_retry(client, author_headers, admin_headers, provider):
    provider.classify_errors = [AITransientError("429", status_code=429)]
    created = await create_ticket(client, author_headers)
    detail = (await client.get(f"/api/v1/admin/tickets/{created['ticket_id']}", headers=admin_headers)).json()
    assert detail["ticket"]["ai_status"] == "COMPLETED" and provider.classify_calls == 2


async def test_author_cannot_access_another_authors_ticket(client, author_headers, other_headers):
    created = await create_ticket(client, author_headers)
    tid = created["ticket_id"]
    for path in (f"/api/v1/tickets/{tid}", f"/api/v1/tickets/{tid}/messages"):
        r = await client.get(path, headers=other_headers)
        assert r.status_code == 404 and r.json()["error"]["code"] == "TICKET_NOT_FOUND"
    r = await client.post(f"/api/v1/tickets/{tid}/messages", headers=other_headers, json={"message": "hi"})
    assert r.status_code == 404
    assert (await client.get("/api/v1/tickets", headers=other_headers)).json() == []


async def test_conversation_flow_and_status_lifecycle(client, author_headers, admin_headers):
    tid = (await create_ticket(client, author_headers))["ticket_id"]

    sent = await client.post(f"/api/v1/admin/tickets/{tid}/messages", headers=admin_headers, json={"message": "Looking into it."})
    assert sent.status_code == 201 and sent.json()["is_ai_assisted"] is False
    ticket = (await client.get(f"/api/v1/tickets/{tid}", headers=author_headers)).json()
    assert ticket["status"] == "IN_PROGRESS"  # first admin reply moves OPEN -> IN_PROGRESS

    await client.patch(f"/api/v1/admin/tickets/{tid}", headers=admin_headers, json={"status": "RESOLVED"})
    # author replies after resolution => reopened
    reply = await client.post(f"/api/v1/tickets/{tid}/messages", headers=author_headers, json={"message": "Still not fixed."})
    assert reply.status_code == 201
    assert (await client.get(f"/api/v1/tickets/{tid}", headers=author_headers)).json()["status"] == "OPEN"

    messages = (await client.get(f"/api/v1/tickets/{tid}/messages", headers=author_headers)).json()
    assert [m["sender_role"] for m in messages] == ["ADMIN", "AUTHOR"]
    assert "is_ai_assisted" not in messages[0]  # AI metadata is never shown to authors

    await client.patch(f"/api/v1/admin/tickets/{tid}", headers=admin_headers, json={"status": "CLOSED"})
    closed = await client.post(f"/api/v1/tickets/{tid}/messages", headers=author_headers, json={"message": "More"})
    assert closed.status_code == 409 and closed.json()["error"]["code"] == "TICKET_CLOSED"
