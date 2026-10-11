from tests.conftest import AUTHOR_PASSWORD, login
from tests.dataset import (
    AUTHORS,
    FIRST_AUTHOR,
    IN_PRODUCTION_BOOK,
    SECOND_BOOK,
    author_of,
)


async def test_valid_login_returns_token_and_profile(client):
    r = await client.post("/api/v1/auth/login", json={"email": FIRST_AUTHOR["email"], "password": AUTHOR_PASSWORD})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["user"]["role"] == "AUTHOR" and body["user"]["author"]["author_id"] == FIRST_AUTHOR["author_id"]


async def test_invalid_password_and_unknown_email_look_identical(client):
    bad_pw = await client.post("/api/v1/auth/login", json={"email": FIRST_AUTHOR["email"], "password": "nope"})
    unknown = await client.post("/api/v1/auth/login", json={"email": "ghost@example.com", "password": "nope"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json()
    assert bad_pw.json()["error"]["code"] == "INVALID_CREDENTIALS"


async def test_me_requires_auth_and_rejects_garbage_token(client, author_headers):
    assert (await client.get("/api/v1/auth/me")).status_code == 401
    assert (await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage"})).status_code == 401
    me = await client.get("/api/v1/auth/me", headers=author_headers)
    assert me.status_code == 200 and me.json()["email"] == FIRST_AUTHOR["email"]


async def test_validation_errors_use_consistent_schema(client):
    r = await client.post("/api/v1/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_author_only_sees_own_books(client, author_headers):
    r = await client.get("/api/v1/books", headers=author_headers)
    assert r.status_code == 200
    assert {b["book_id"] for b in r.json()} == {b["book_id"] for b in FIRST_AUTHOR["books"]}


async def test_other_authors_book_is_not_found(client, author_headers):
    r = await client.get(f"/api/v1/books/{SECOND_BOOK['book_id']}", headers=author_headers)  # another author's book
    assert r.status_code == 404 and r.json()["error"]["code"] == "BOOK_NOT_FOUND"


async def test_in_production_book_keeps_nulls_through_the_api(client):
    owner = author_of(IN_PRODUCTION_BOOK)
    headers = await login(client, owner["email"], AUTHOR_PASSWORD)
    book = (await client.get(f"/api/v1/books/{IN_PRODUCTION_BOOK['book_id']}", headers=headers)).json()
    assert book["publication_date"] is None and book["mrp"] is None
    assert book["author_royalty_per_copy"] is None and book["last_royalty_payout_date"] is None
    assert book["print_partner"] is None and book["available_on"] == []
    assert book["total_royalty_earned"] == 0 and book["total_copies_sold"] == 0


async def test_author_dashboard_totals_match_source(client, author_headers):
    d = (await client.get("/api/v1/author/dashboard", headers=author_headers)).json()
    books = FIRST_AUTHOR["books"]
    assert d["total_books"] == len(books)
    assert d["total_royalty_earned"] == sum(b["total_royalty_earned"] for b in books)
    assert d["total_royalty_paid"] == sum(b["royalty_paid"] for b in books)
    assert d["total_royalty_pending"] == sum(b["royalty_pending"] for b in books)
    assert {s["status"] for s in d["book_status_overview"]} == {b["status"] for b in books}


async def test_admin_cannot_use_author_endpoints(client, admin_headers):
    assert (await client.get("/api/v1/books", headers=admin_headers)).status_code == 403


async def test_author_cannot_use_admin_endpoints(client, author_headers):
    for path in ("/api/v1/admin/tickets", "/api/v1/admin/dashboard", "/api/v1/ai/status"):
        r = await client.get(path, headers=author_headers)
        assert r.status_code == 403, path
        assert r.json()["error"]["code"] == "ADMIN_ONLY"


async def test_admin_endpoints_require_authentication(client):
    assert (await client.get("/api/v1/admin/tickets")).status_code == 401
    assert (await client.get("/api/v1/admin/dashboard")).status_code == 401


async def test_login_helper_for_each_seeded_author(client):
    # every author in the dataset gets a working demo account
    for author in AUTHORS:
        assert "Authorization" in await login(client, author["email"], AUTHOR_PASSWORD)


async def test_repeated_failed_logins_are_rate_limited_per_account(client):
    bad = {"email": FIRST_AUTHOR["email"], "password": "wrong"}
    for _ in range(5):
        assert (await client.post("/api/v1/auth/login", json=bad)).status_code == 401
    blocked = await client.post("/api/v1/auth/login", json={**bad, "password": "Author@123"})
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert blocked.json()["error"]["details"]["retry_after_seconds"] > 0
    # a different account is unaffected
    ok = await client.post("/api/v1/auth/login", json={"email": AUTHORS[1]["email"], "password": "Author@123"})
    assert ok.status_code == 200
