import json

from app.ai.errors import AITransientError
from app.models.enums import Category, Priority
from tests.conftest import create_ticket
from tests.dataset import FIRST_AUTHOR, SECOND_AUTHOR, SECOND_BOOK


def with_classification(provider, category, priority):
    provider.classification = provider.classification.model_copy(update={"category": category, "priority": priority})


async def test_admin_can_open_any_ticket(client, author_headers, other_headers, admin_headers):
    a = await create_ticket(client, author_headers)
    b = await create_ticket(client, other_headers, book_id=SECOND_BOOK["book_id"])
    for t in (a, b):
        r = await client.get(f"/api/v1/admin/tickets/{t['ticket_id']}", headers=admin_headers)
        assert r.status_code == 200


async def test_queue_filters_and_urgency_sorting(client, author_headers, other_headers, admin_headers, provider):
    with_classification(provider, Category.GENERAL, Priority.LOW)
    low = await create_ticket(client, author_headers, book_id=None, subject="Bio", description="Please update my author bio today.")
    with_classification(provider, Category.PRINTING, Priority.MEDIUM)
    high = await create_ticket(client, other_headers, book_id=SECOND_BOOK["book_id"], subject="Defect",
                               description="My author copies contain missing pages and torn covers.")

    queue = (await client.get("/api/v1/admin/tickets", headers=admin_headers)).json()
    assert [t["ticket_id"] for t in queue["items"]] == [high["ticket_id"], low["ticket_id"]]  # HIGH before LOW
    assert queue["total"] == 2

    def ids(resp):
        return [t["ticket_id"] for t in resp.json()["items"]]

    assert ids(await client.get("/api/v1/admin/tickets?category=Printing %26 Quality", headers=admin_headers)) == [high["ticket_id"]]
    assert ids(await client.get("/api/v1/admin/tickets?priority=LOW", headers=admin_headers)) == [low["ticket_id"]]
    assert ids(await client.get(f"/api/v1/admin/tickets?author={SECOND_AUTHOR['author_id']}", headers=admin_headers)) == [high["ticket_id"]]
    assert ids(await client.get(f"/api/v1/admin/tickets?author={FIRST_AUTHOR['name'].split()[0].lower()}", headers=admin_headers)) == [low["ticket_id"]]
    assert ids(await client.get(f"/api/v1/admin/tickets?book={SECOND_BOOK['book_id']}", headers=admin_headers)) == [high["ticket_id"]]
    assert ids(await client.get("/api/v1/admin/tickets?assignment=unassigned", headers=admin_headers)) != []
    assert ids(await client.get("/api/v1/admin/tickets?assignment=me", headers=admin_headers)) == []
    assert ids(await client.get("/api/v1/admin/tickets?q=bio", headers=admin_headers)) == [low["ticket_id"]]
    assert ids(await client.get("/api/v1/admin/tickets?date_from=2999-01-01", headers=admin_headers)) == []
    assert (await client.get("/api/v1/admin/tickets?priority=BOGUS", headers=admin_headers)).status_code == 422


async def test_resolved_tickets_sink_below_unresolved(client, author_headers, admin_headers, provider):
    with_classification(provider, Category.ISBN, Priority.CRITICAL)
    first = await create_ticket(client, author_headers, description="The ISBN is wrong and legal action may follow.")
    with_classification(provider, Category.GENERAL, Priority.LOW)
    second = await create_ticket(client, author_headers, book_id=None, subject="Hello", description="Just a general question for you.")
    await client.patch(f"/api/v1/admin/tickets/{first['ticket_id']}", headers=admin_headers, json={"status": "RESOLVED"})
    queue = (await client.get("/api/v1/admin/tickets", headers=admin_headers)).json()["items"]
    assert [t["ticket_id"] for t in queue] == [second["ticket_id"], first["ticket_id"]]


async def test_override_category_and_priority_are_marked_manual_and_survive_ai_retry(client, author_headers, admin_headers, provider):
    with_classification(provider, Category.GENERAL, Priority.LOW)
    tid = (await create_ticket(client, author_headers))["ticket_id"]

    r = await client.patch(f"/api/v1/admin/tickets/{tid}", headers=admin_headers,
                           json={"category": "Royalty & Payments", "priority": "CRITICAL"})
    assert r.status_code == 200
    body = r.json()
    assert body["category"] == "Royalty & Payments" and body["category_source"] == "MANUAL"
    assert body["priority"] == "CRITICAL" and body["priority_source"] == "MANUAL"

    retry = await client.post(f"/api/v1/admin/tickets/{tid}/ai-retry", headers=admin_headers)
    assert retry.status_code == 202
    after = (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()["ticket"]
    assert after["category"] == "Royalty & Payments" and after["priority"] == "CRITICAL"  # AI did not clobber overrides
    assert after["ai_status"] == "COMPLETED"


async def test_assign_to_self_and_status_update(client, author_headers, admin_headers):
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    r = await client.post(f"/api/v1/admin/tickets/{tid}/assign", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["assigned_admin_email"] == "admin@bookleaf.com" and r.json()["status"] == "IN_PROGRESS"
    mine = (await client.get("/api/v1/admin/tickets?assignment=me", headers=admin_headers)).json()
    assert mine["total"] == 1
    assert (await client.patch(f"/api/v1/admin/tickets/{tid}", headers=admin_headers, json={"status": "RESOLVED"})).json()["status"] == "RESOLVED"


async def test_internal_notes_are_never_visible_to_authors(client, author_headers, admin_headers):
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    secret = "INTERNAL-ONLY: author seems upset, loop in finance"
    note = await client.post(f"/api/v1/admin/tickets/{tid}/notes", headers=admin_headers, json={"note": secret})
    assert note.status_code == 201
    await client.post(f"/api/v1/admin/tickets/{tid}/messages", headers=admin_headers, json={"message": "Public reply"})

    admin_view = (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()
    assert admin_view["internal_notes"][0]["note"] == secret

    for path in (f"/api/v1/tickets/{tid}", f"/api/v1/tickets/{tid}/messages", "/api/v1/tickets", "/api/v1/author/dashboard"):
        text = json.dumps((await client.get(path, headers=author_headers)).json())
        assert "INTERNAL-ONLY" not in text and "internal_notes" not in text, path


async def test_send_response_records_ai_assistance_and_marks_draft_sent(client, author_headers, admin_headers):
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    detail = (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()
    draft_id = detail["ai_draft"]["id"]

    sent = await client.post(f"/api/v1/admin/tickets/{tid}/messages", headers=admin_headers,
                             json={"message": "Edited version of the draft.", "ai_draft_id": draft_id})
    assert sent.status_code == 201 and sent.json()["is_ai_assisted"] is True
    messages = (await client.get(f"/api/v1/tickets/{tid}/messages", headers=author_headers)).json()
    assert messages[0]["message"] == "Edited version of the draft."


async def test_draft_from_another_ticket_is_rejected(client, author_headers, other_headers, admin_headers):
    a = (await create_ticket(client, author_headers))["ticket_id"]
    b = (await create_ticket(client, other_headers, book_id=SECOND_BOOK["book_id"]))["ticket_id"]
    foreign = (await client.get(f"/api/v1/admin/tickets/{a}", headers=admin_headers)).json()["ai_draft"]["id"]
    r = await client.post(f"/api/v1/admin/tickets/{b}/messages", headers=admin_headers, json={"message": "x", "ai_draft_id": foreign})
    assert r.status_code == 400 and r.json()["error"]["code"] == "INVALID_DRAFT"


async def test_ai_draft_is_never_auto_sent(client, author_headers):
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    assert (await client.get(f"/api/v1/tickets/{tid}/messages", headers=author_headers)).json() == []


async def test_regenerate_draft_and_manual_fallback_when_ai_down(client, author_headers, admin_headers, provider):
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    provider.draft_text = "A brand new draft."
    r = await client.post(f"/api/v1/admin/tickets/{tid}/ai-draft", headers=admin_headers)
    assert r.status_code == 200 and r.json()["draft"] == "A brand new draft."
    assert (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()["ai_draft"]["draft"] == "A brand new draft."

    provider.draft_errors = [AITransientError("503", status_code=503)] * 3
    down = await client.post(f"/api/v1/admin/tickets/{tid}/ai-draft", headers=admin_headers)
    assert down.status_code == 503
    assert "respond manually" in down.json()["error"]["message"]
    # the admin can still respond manually
    assert (await client.post(f"/api/v1/admin/tickets/{tid}/messages", headers=admin_headers, json={"message": "Manual."})).status_code == 201


async def test_retry_ai_after_failure_recovers(client, author_headers, admin_headers, provider):
    provider.classify_errors = [AITransientError("503", status_code=503)] * 3
    tid = (await create_ticket(client, author_headers))["ticket_id"]
    assert (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()["ticket"]["ai_status"] == "FAILED"
    assert (await client.post(f"/api/v1/admin/tickets/{tid}/ai-retry", headers=admin_headers)).status_code == 202
    assert (await client.get(f"/api/v1/admin/tickets/{tid}", headers=admin_headers)).json()["ticket"]["ai_status"] == "COMPLETED"


async def test_admin_dashboard_counts(client, author_headers, admin_headers, provider):
    with_classification(provider, Category.ISBN, Priority.CRITICAL)
    await create_ticket(client, author_headers, description="The ISBN is wrong and I will contact my lawyer today.")
    with_classification(provider, Category.GENERAL, Priority.LOW)
    await create_ticket(client, author_headers, book_id=None, subject="Hello", description="A simple general question for you.")
    d = (await client.get("/api/v1/admin/dashboard", headers=admin_headers)).json()
    assert d["open_tickets"] == 2 and d["unresolved_tickets"] == 2
    assert d["critical_tickets"] == 1 and d["unassigned_tickets"] == 2
    assert {c["category"] for c in d["by_category"]} == {"ISBN & Metadata Issues", "General Inquiry"}
    assert d["recent_activity"]


async def test_ai_status_endpoint(client, admin_headers):
    s = (await client.get("/api/v1/ai/status", headers=admin_headers)).json()
    assert s["knowledge_chunks"] == 7 and s["knowledge_chunks_embedded"] == 0
