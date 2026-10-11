"""AI orchestration: the only place that sequences classify -> guardrails -> retrieve -> draft.

Design rules:
* Runs *after* the ticket is committed; nothing here may prevent ticket creation.
* Owns its DB sessions (it runs in a background task after the request session is closed).
* Every model call is recorded in `ai_runs` (success and failure).
* Manual admin overrides always win over AI output.
"""
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.classifier import TicketClassifier
from app.ai.context_builder import ContextBuilder
from app.ai.errors import AIError, AINotConfiguredError
from app.ai.priority import PriorityEngine
from app.ai.providers.base import AIProvider
from app.ai.response_generator import ResponseGenerator
from app.ai.retriever import KnowledgeRetriever
from app.ai.schemas import ProviderResult
from app.core.config import Settings
from app.models.ai_draft import AIDraft
from app.models.ai_run import AIRun
from app.models.enums import AIRunStatus, AIStatus, DecisionSource
from app.models.ticket import Ticket
from app.repositories.ai_repository import AIRepository
from app.repositories.book_repository import BookRepository
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.ticket_repository import TicketRepository
from app.services import notification_service as events
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AIOrchestrator:
    def __init__(
        self,
        *,
        provider: AIProvider | None,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        notifier: NotificationService | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        self._provider = provider
        self._factory = session_factory
        self._settings = settings
        self._notifier = notifier
        self._engine = PriorityEngine()
        self._context = ContextBuilder(history_limit=settings.ai_conversation_history_limit)
        self._sleep = sleep

    # ---- public API ------------------------------------------------------
    async def process_ticket(self, ticket_id: int) -> None:
        """Full pipeline (new ticket or admin retry). Never raises."""
        try:
            await self._pipeline(ticket_id)
        except Exception:  # noqa: BLE001 - background task must never crash the worker
            logger.exception("AI pipeline crashed for ticket id=%s", ticket_id)
            await self._safe_mark_failed(ticket_id, "UNEXPECTED", "Unexpected internal error during AI analysis.")

    async def regenerate_draft(self, ticket_id: int) -> AIDraft:
        """Admin-triggered. Raises AIError so the API can report the failure to the admin."""
        async with self._factory() as session:
            ticket = await TicketRepository(session).get_by_id(ticket_id)
            if ticket is None:
                raise LookupError(ticket_id)
            draft = await self._draft_step(session, ticket)
            await session.commit()
        await self._notify(events.AI_UPDATED, ticket)
        return draft

    # ---- pipeline --------------------------------------------------------
    async def _pipeline(self, ticket_id: int) -> None:
        async with self._factory() as session:
            ticket = await TicketRepository(session).get_by_id(ticket_id)
            if ticket is None:
                return
            ticket.ai_status = AIStatus.PROCESSING
            await session.commit()
            try:
                await self._classify_step(session, ticket)
                await session.commit()
                await self._draft_step(session, ticket)
                ticket.ai_status = AIStatus.COMPLETED
                TicketRepository(session).add_event(ticket.id, "ai.completed", None, ticket.category.value if ticket.category else None, None)
                await session.commit()
            except AIError as exc:
                await session.rollback()
                await self._mark_failed(session, ticket_id, exc.error_type, exc.message)
            ticket_after = await TicketRepository(session).get_by_id(ticket_id)
        if ticket_after is not None:
            await self._notify(events.AI_UPDATED, ticket_after)

    async def _classify_step(self, session: AsyncSession, ticket: Ticket) -> None:
        provider = self._require_provider()
        classifier = TicketClassifier(
            provider,
            max_attempts=self._settings.ai_max_retries,
            base_delay_seconds=self._settings.ai_retry_base_delay_seconds,
            sleep=self._sleep,
        )
        book = ticket.book
        result = await self._tracked(
            session, ticket.id, "classify", classifier.prompt_version,
            lambda: classifier.classify(
                subject=ticket.subject, description=ticket.description, book_hint=ContextBuilder.book_hint(book)
            ),
        )
        # An admin may have overridden values while the model was running: reload the source flags.
        await session.refresh(ticket, attribute_names=["category", "category_source", "priority", "priority_source"])
        cls = result.value

        category = ticket.category if ticket.category_source is DecisionSource.MANUAL else cls.category
        decision = self._engine.resolve(
            model_priority=cls.priority,
            category=category,
            text=f"{ticket.subject}\n{ticket.description}",
            book=book,
            today=date.today(),
        )
        repo = TicketRepository(session)
        if ticket.category_source is not DecisionSource.MANUAL:
            repo.add_event(ticket.id, "category.ai", ticket.category.value if ticket.category else None, cls.category.value, None)
            ticket.category = cls.category
            ticket.category_source = DecisionSource.AI
            ticket.category_confidence = cls.category_confidence
        if ticket.priority_source is not DecisionSource.MANUAL:
            adjusted = decision.priority is not cls.priority
            repo.add_event(ticket.id, "priority.ai", ticket.priority.value, decision.priority.value, None)
            ticket.priority = decision.priority
            ticket.priority_source = DecisionSource.RULE if adjusted else DecisionSource.AI
            ticket.priority_confidence = None if adjusted else cls.priority_confidence
        reasoning = cls.reason
        if decision.applied_rules:
            reasoning += f" Guardrails applied (model suggested {cls.priority.value}): {', '.join(decision.applied_rules)}."
        ticket.ai_reasoning = reasoning
        ticket.needs_human_attention = cls.needs_human_attention

    async def _draft_step(self, session: AsyncSession, ticket: Ticket) -> AIDraft:
        provider = self._require_provider()
        settings = self._settings
        retriever = KnowledgeRetriever(KnowledgeRepository(session), provider, top_k=settings.ai_retrieval_top_k)
        retrieval = await retriever.retrieve(
            query_text=f"{ticket.subject}\n{ticket.description}", category=ticket.category
        )
        if retrieval.embedding_calls:
            session.add(AIRun(
                ticket_id=ticket.id, operation="embed_query", model=provider.embedding_model_name,
                prompt_version="n/a", status=AIRunStatus.SUCCESS.value, latency_ms=retrieval.embedding_latency_ms,
            ))

        tickets = TicketRepository(session)
        author_books = await BookRepository(session).list_for_author(ticket.author_id) if ticket.book is None else None
        account = self._context.build_account_context(
            category=ticket.category, book=ticket.book, author=ticket.author, author_books=author_books
        )
        messages = await tickets.list_messages(ticket.id)
        account_text, knowledge_text = account.render(), retrieval.render()

        generator = ResponseGenerator(
            provider,
            max_attempts=settings.ai_max_retries,
            base_delay_seconds=settings.ai_retry_base_delay_seconds,
            max_output_tokens=settings.ai_max_response_tokens,
            sleep=self._sleep,
        )
        result = await self._tracked(
            session, ticket.id, "draft", generator.prompt_version,
            lambda: generator.generate(
                author_name=ticket.author.name,
                account_context=account_text,
                knowledge_context=knowledge_text,
                subject=ticket.subject,
                description=ticket.description,
                recent_messages=self._context.build_recent_messages(messages),
            ),
        )
        draft = await AIRepository(session).save_draft(AIDraft(
            ticket_id=ticket.id,
            draft=result.value.text,
            model=provider.model_name,
            prompt_version=generator.prompt_version,
            knowledge_chunk_ids=retrieval.chunk_ids,
            grounding_warnings=result.value.grounding.warnings,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            latency_ms=result.latency_ms,
        ))
        return draft

    # ---- helpers ---------------------------------------------------------
    def _require_provider(self) -> AIProvider:
        if self._provider is None:
            raise AINotConfiguredError("AI provider is not configured (set GEMINI_API_KEY).")
        return self._provider

    async def _tracked(
        self, session: AsyncSession, ticket_id: int, operation: str, prompt_version: str,
        call: Callable[[], Awaitable[ProviderResult[T]]],
    ) -> ProviderResult[T]:
        """Run one model operation and persist an `ai_runs` row for the outcome."""
        model = self._require_provider().model_name
        repo = AIRepository(session)
        try:
            result = await call()
        except AIError as exc:
            repo.add_run(AIRun(
                ticket_id=ticket_id, operation=operation, model=model, prompt_version=prompt_version,
                status=AIRunStatus.FAILED.value, attempts=exc.attempts, error_type=exc.error_type,
                error_message=exc.message[:500],
            ))
            await session.commit()
            raise
        repo.add_run(AIRun(
            ticket_id=ticket_id, operation=operation, model=model, prompt_version=prompt_version,
            status=AIRunStatus.SUCCESS.value, latency_ms=result.latency_ms, attempts=result.attempts,
            input_tokens=result.usage.input_tokens, output_tokens=result.usage.output_tokens,
        ))
        return result

    async def _mark_failed(self, session: AsyncSession, ticket_id: int, error_type: str, message: str) -> None:
        """Keep the ticket fully usable: record failure, apply deterministic fallback priority."""
        repo = TicketRepository(session)
        ticket = await repo.get_by_id(ticket_id)
        if ticket is None:
            return
        ticket.ai_status = AIStatus.FAILED
        if ticket.priority_source is DecisionSource.DEFAULT:
            decision = self._engine.baseline(
                category=ticket.category, text=f"{ticket.subject}\n{ticket.description}", book=ticket.book
            )
            ticket.priority = decision.priority
            ticket.priority_source = DecisionSource.RULE
            ticket.priority_confidence = None
        if not ticket.ai_reasoning:
            ticket.ai_reasoning = "AI analysis unavailable; priority estimated from keyword rules."
        repo.add_event(ticket.id, "ai.failed", None, error_type, None)
        await session.commit()
        logger.warning("AI analysis failed for %s: %s (%s)", ticket.display_id, error_type, message)

    async def _safe_mark_failed(self, ticket_id: int, error_type: str, message: str) -> None:
        try:
            async with self._factory() as session:
                await self._mark_failed(session, ticket_id, error_type, message)
        except Exception:  # noqa: BLE001
            logger.exception("Could not record AI failure for ticket id=%s", ticket_id)

    async def _notify(self, event_type: str, ticket: Ticket) -> None:
        if self._notifier is None:
            return
        try:
            await self._notifier.ticket_event(event_type, ticket)
        except Exception:  # noqa: BLE001
            logger.exception("Notification failed")
