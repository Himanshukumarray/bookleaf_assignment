"""Seeded database must equal the official BookLeaf JSON, field by field (nulls stay null)."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select

from app.db.seed import seed_knowledge_base, seed_operational_data
from app.models import Author, Book, BookAvailability, KnowledgeChunk, User
from app.models.enums import Role
from tests.conftest import AUTHOR_PASSWORD, login
from tests.dataset import AUTHORS, BOOKS


def _d(value):
    return date.fromisoformat(value) if value else None


def _m(value):
    return None if value is None else Decimal(str(value))


async def count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_counts_and_official_ids_exist_exactly_once(session_factory):
    async with session_factory() as s:
        assert await count(s, User) == len(AUTHORS) + 1  # one per author + the admin
        assert await count(s, Author) == len(AUTHORS) == 10
        assert await count(s, Book) == len(BOOKS) == 18
        assert await count(s, KnowledgeChunk) == 7
        author_ids = sorted((await s.execute(select(Author.external_author_id))).scalars())
        book_ids = sorted((await s.execute(select(Book.external_book_id))).scalars())
    assert author_ids == [f"AUTH{i:03d}" for i in range(1, 11)]
    assert book_ids == [f"BK{i:03d}" for i in range(1, 19)]


async def test_every_author_and_book_field_matches_the_source(session_factory):
    async with session_factory() as s:
        for src in AUTHORS:
            author = (await s.execute(select(Author).where(Author.external_author_id == src["author_id"]))).scalar_one()
            assert (author.name, author.email, author.phone, author.city) == (src["name"], src["email"], src["phone"], src["city"])
            assert author.joined_date == _d(src["joined_date"])
            user = await s.get(User, author.user_id)
            assert user.email == src["email"].lower() and user.role is Role.AUTHOR

            for b in src["books"]:
                book = (await s.execute(select(Book).where(Book.external_book_id == b["book_id"]))).scalar_one()
                assert book.author_id == author.id, f"{b['book_id']} belongs to the wrong author"
                assert (book.title, book.isbn, book.genre, book.status, book.print_partner) == (
                    b["title"], b["isbn"], b["genre"], b["status"], b["print_partner"])
                assert book.publication_date == _d(b["publication_date"])
                assert book.last_royalty_payout_date == _d(b["last_royalty_payout_date"])
                assert book.mrp == _m(b["mrp"]) and book.author_royalty_per_copy == _m(b["author_royalty_per_copy"])
                assert book.total_copies_sold == b["total_copies_sold"]
                assert book.total_royalty_earned == _m(b["total_royalty_earned"])
                assert book.royalty_paid == _m(b["royalty_paid"])
                assert book.royalty_pending == _m(b["royalty_pending"])
                platforms = (await s.execute(select(BookAvailability.platform).where(BookAvailability.book_id == book.id).order_by(BookAvailability.id))).scalars()
                assert list(platforms) == b["available_on"]  # exact source order


async def test_null_source_values_remain_null_in_the_database(session_factory):
    nullable = ("publication_date", "mrp", "author_royalty_per_copy", "last_royalty_payout_date", "print_partner")
    async with session_factory() as s:
        for b in BOOKS:
            book = (await s.execute(select(Book).where(Book.external_book_id == b["book_id"]))).scalar_one()
            for field in nullable:
                if b[field] is None:
                    assert getattr(book, field) is None, f"{b['book_id']}.{field} was given a fake default"
    assert any(b[f] is None for b in BOOKS for f in nullable), "dataset no longer exercises null handling"


async def test_reseeding_is_idempotent(session_factory):
    async with session_factory() as s:
        await seed_operational_data(s)
        await seed_knowledge_base(s, embed=False)
        await s.commit()
    async with session_factory() as s:
        assert (await count(s, User), await count(s, Author), await count(s, Book), await count(s, KnowledgeChunk)) == (11, 10, 18, 7)
        assert await count(s, BookAvailability) == sum(len(b["available_on"]) for b in BOOKS)


async def test_every_author_logs_in_with_their_exact_dataset_email_and_sees_only_their_books(client):
    for src in AUTHORS:
        headers = await login(client, src["email"], AUTHOR_PASSWORD)
        me = (await client.get("/api/v1/auth/me", headers=headers)).json()
        assert me["author"]["author_id"] == src["author_id"]
        books = (await client.get("/api/v1/books", headers=headers)).json()
        assert sorted(b["book_id"] for b in books) == sorted(b["book_id"] for b in src["books"])
        for api_book, source in zip(sorted(books, key=lambda x: x["book_id"]), sorted(src["books"], key=lambda x: x["book_id"])):
            for key in ("title", "isbn", "genre", "status", "mrp", "author_royalty_per_copy", "total_copies_sold",
                        "total_royalty_earned", "royalty_paid", "royalty_pending", "publication_date",
                        "last_royalty_payout_date", "print_partner"):
                assert api_book[key] == source[key], f"{source['book_id']}.{key}"
            assert api_book["available_on"] == source["available_on"]  # exact source order
