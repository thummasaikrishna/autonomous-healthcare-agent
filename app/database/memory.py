"""
Memory layer: CRUD operations for sessions, messages, research queries, and
sources. This is the only module that should issue SQLAlchemy queries; the
UI and agent talk to this module instead of touching models directly.
"""

from __future__ import annotations

from app.database.database import get_db_session
from app.database.models import Message, ResearchQuery, Session, Source
from app.research.citation import Citation
from app.utils.logging_config import get_logger
from app.utils.text_utils import new_id

logger = get_logger(__name__)


def create_session(title: str = "New Research Session") -> str:
    session_id = new_id("session_")
    with get_db_session() as db:
        record = Session(id=session_id, title=title)
        db.add(record)
    return session_id


def list_sessions() -> list[dict]:
    with get_db_session() as db:
        records = db.query(Session).order_by(Session.updated_at.desc()).all()
        return [
            {"id": r.id, "title": r.title, "created_at": r.created_at, "updated_at": r.updated_at}
            for r in records
        ]


def search_sessions(query: str) -> list[dict]:
    """
    Return sessions whose title, messages, or research queries match the
    search text. Empty query returns the full session list.
    """
    needle = (query or "").strip().lower()
    if not needle:
        return list_sessions()

    with get_db_session() as db:
        records = db.query(Session).order_by(Session.updated_at.desc()).all()
        matched = []
        for record in records:
            title = (record.title or "").lower()
            if needle in title:
                matched.append(record)
                continue

            message_hit = any(
                needle in (message.content or "").lower() for message in record.messages
            )
            if message_hit:
                matched.append(record)
                continue

            query_hit = any(
                needle in (research_query.query or "").lower()
                for research_query in record.queries
            )
            if query_hit:
                matched.append(record)

        return [
            {"id": r.id, "title": r.title, "created_at": r.created_at, "updated_at": r.updated_at}
            for r in matched
        ]


def delete_session(session_id: str) -> bool:
    """Delete a session and its cascaded messages, queries, and sources."""
    with get_db_session() as db:
        record = db.query(Session).filter(Session.id == session_id).first()
        if not record:
            return False
        db.delete(record)
        return True


def get_session(session_id: str) -> dict | None:
    with get_db_session() as db:
        record = db.query(Session).filter(Session.id == session_id).first()
        if not record:
            return None
        return {"id": record.id, "title": record.title, "created_at": record.created_at}


def rename_session(session_id: str, title: str) -> None:
    with get_db_session() as db:
        record = db.query(Session).filter(Session.id == session_id).first()
        if record:
            record.title = title[:80]


def add_message(session_id: str, role: str, content: str) -> None:
    with get_db_session() as db:
        db.add(Message(session_id=session_id, role=role, content=content))
        session_record = db.query(Session).filter(Session.id == session_id).first()
        if session_record is not None:
            from app.database.models import utcnow

            session_record.updated_at = utcnow()


def get_messages(session_id: str) -> list[dict]:
    with get_db_session() as db:
        records = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        return [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "timestamp": r.timestamp,
            }
            for r in records
        ]


def list_all_questions(search: str = "") -> list[dict]:
    """Return every user question across sessions, newest first."""
    needle = (search or "").strip().lower()
    with get_db_session() as db:
        records = (
            db.query(Message)
            .filter(Message.role == "user")
            .order_by(Message.timestamp.desc())
            .all()
        )
        results = []
        for record in records:
            content = record.content or ""
            if needle and needle not in content.lower():
                continue
            results.append(
                {
                    "message_id": record.id,
                    "session_id": record.session_id,
                    "question": content,
                    "timestamp": record.timestamp,
                }
            )
        return results


def delete_question_turn(user_message_id: int) -> bool:
    """
    Delete one asked question and its related reply + saved sources.
    Does not delete the whole session or other questions.
    """
    with get_db_session() as db:
        user_msg = (
            db.query(Message)
            .filter(Message.id == user_message_id, Message.role == "user")
            .first()
        )
        if not user_msg:
            return False

        session_id = user_msg.session_id
        question_text = user_msg.content

        assistant_msg = (
            db.query(Message)
            .filter(
                Message.session_id == session_id,
                Message.role == "assistant",
                Message.id > user_msg.id,
            )
            .order_by(Message.id.asc())
            .first()
        )
        if assistant_msg is not None:
            intervening_user = (
                db.query(Message)
                .filter(
                    Message.session_id == session_id,
                    Message.role == "user",
                    Message.id > user_msg.id,
                    Message.id < assistant_msg.id,
                )
                .first()
            )
            if intervening_user is not None:
                assistant_msg = None

        matching_queries = (
            db.query(ResearchQuery)
            .filter(
                ResearchQuery.session_id == session_id,
                ResearchQuery.query == question_text,
            )
            .all()
        )
        for query_record in matching_queries:
            db.delete(query_record)

        if assistant_msg is not None:
            db.delete(assistant_msg)
        db.delete(user_msg)
        return True


def save_query_with_sources(session_id: str, query_text: str, citations: list[Citation]) -> int:
    with get_db_session() as db:
        query_record = ResearchQuery(session_id=session_id, query=query_text)
        db.add(query_record)
        db.flush()  # populate query_record.id

        for citation in citations:
            source = Source(
                query_id=query_record.id,
                title=citation.title,
                source_type=citation.source_type,
                identifier=citation.identifier,
                url=citation.url,
            )
            source.set_metadata(citation.metadata)
            db.add(source)

        return query_record.id


def get_query_history(session_id: str) -> list[dict]:
    with get_db_session() as db:
        records = (
            db.query(ResearchQuery)
            .filter(ResearchQuery.session_id == session_id)
            .order_by(ResearchQuery.timestamp.asc())
            .all()
        )
        results = []
        for record in records:
            sources = [
                {
                    "title": s.title,
                    "source_type": s.source_type,
                    "identifier": s.identifier,
                    "url": s.url,
                    "metadata": s.get_metadata(),
                }
                for s in record.sources
            ]
            results.append(
                {
                    "id": record.id,
                    "query": record.query,
                    "timestamp": record.timestamp,
                    "sources": sources,
                }
            )
        return results
