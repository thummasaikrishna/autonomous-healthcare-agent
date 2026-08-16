import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base
from app.research.citation import Citation


@pytest.fixture
def db_module(tmp_path, monkeypatch):
    """Provide a memory module wired to an isolated temporary SQLite file."""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    import app.database.database as database_module
    import app.database.memory as memory_module

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "SessionLocal", session_factory)

    return memory_module


def test_create_and_get_session(db_module):
    session_id = db_module.create_session("Test Session")
    session = db_module.get_session(session_id)
    assert session is not None
    assert session["title"] == "Test Session"


def test_save_message_and_retrieve(db_module):
    session_id = db_module.create_session()
    db_module.add_message(session_id, "user", "What does research say about aspirin?")
    db_module.add_message(session_id, "assistant", "Here is a summary...")

    messages = db_module.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"


def test_save_sources_and_persistence(db_module):
    session_id = db_module.create_session()
    citation = Citation(
        source_type="pubmed",
        title="Aspirin and cardiovascular outcomes",
        identifier="123456",
        url="https://pubmed.ncbi.nlm.nih.gov/123456/",
        metadata={"journal": "Cardiology Today", "publication_date": "2022"},
    )
    query_id = db_module.save_query_with_sources(session_id, "aspirin cardiovascular research", [citation])
    assert query_id is not None

    history = db_module.get_query_history(session_id)
    assert len(history) == 1
    assert history[0]["query"] == "aspirin cardiovascular research"
    assert len(history[0]["sources"]) == 1
    assert history[0]["sources"][0]["identifier"] == "123456"


def test_list_sessions_ordering(db_module):
    first = db_module.create_session("First")
    second = db_module.create_session("Second")

    sessions = db_module.list_sessions()
    ids = [s["id"] for s in sessions]
    assert first in ids
    assert second in ids


def test_search_sessions_by_title_and_message(db_module):
    aspirin = db_module.create_session("Aspirin outcomes")
    fasting = db_module.create_session("Intermittent fasting")
    db_module.add_message(fasting, "user", "What about metabolic markers?")

    by_title = db_module.search_sessions("aspirin")
    assert [s["id"] for s in by_title] == [aspirin]

    by_message = db_module.search_sessions("metabolic")
    assert [s["id"] for s in by_message] == [fasting]

    assert db_module.search_sessions("") == db_module.list_sessions()


def test_delete_session_removes_messages_and_sources(db_module):
    session_id = db_module.create_session("To delete")
    db_module.add_message(session_id, "user", "Question about statins")
    citation = Citation(
        source_type="pubmed",
        title="Statin trial",
        identifier="999",
        url="https://pubmed.ncbi.nlm.nih.gov/999/",
        metadata={},
    )
    db_module.save_query_with_sources(session_id, "statins", [citation])

    assert db_module.delete_session(session_id) is True
    assert db_module.get_session(session_id) is None
    assert db_module.get_messages(session_id) == []
    assert db_module.get_query_history(session_id) == []
    assert db_module.delete_session(session_id) is False


def test_list_and_delete_individual_question_turn(db_module):
    session_id = db_module.create_session("Mixed session")
    db_module.add_message(session_id, "user", "Question A about aspirin")
    db_module.add_message(session_id, "assistant", "Answer A")
    citation = Citation(
        source_type="pubmed",
        title="Aspirin paper",
        identifier="111",
        url="https://pubmed.ncbi.nlm.nih.gov/111/",
        metadata={},
    )
    db_module.save_query_with_sources(session_id, "Question A about aspirin", [citation])

    db_module.add_message(session_id, "user", "Question B about fasting")
    db_module.add_message(session_id, "assistant", "Answer B")

    questions = db_module.list_all_questions()
    assert len(questions) == 2
    assert questions[0]["question"] == "Question B about fasting"

    aspirin_only = db_module.list_all_questions("aspirin")
    assert len(aspirin_only) == 1
    assert aspirin_only[0]["question"] == "Question A about aspirin"

    assert db_module.delete_question_turn(aspirin_only[0]["message_id"]) is True

    remaining_messages = db_module.get_messages(session_id)
    assert [m["content"] for m in remaining_messages] == [
        "Question B about fasting",
        "Answer B",
    ]
    assert db_module.get_query_history(session_id) == []
    assert db_module.get_session(session_id) is not None
