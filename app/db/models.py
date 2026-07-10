import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)

    # Null if the account was created via Google -- a user could later add a
    # password too, but we don't force it.
    hashed_password = Column(String, nullable=True)

    # Null if the account was created via email+password. Google's stable
    # per-account identifier ("sub" claim), NOT the email, since email can
    # change on Google's side.
    google_sub = Column(String, unique=True, nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    interviews = relationship("Interview", back_populates="user")


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)

    # thread_id is the LangGraph checkpoint key -- this table is what lets us
    # check "does this thread belong to this user" before letting them
    # submit_answer/get_report on it.
    thread_id = Column(String, unique=True, nullable=False, index=True)

    topic = Column(String, nullable=False)
    difficulty = Column(String, nullable=False)
    is_complete = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="interviews")


class CorpusChunk(Base):
    """
    Mirror of everything upserted into Pinecone, used for local BM25 lexical
    search (see app/rag/corpus_store.py). Lives in Postgres rather than a
    local JSON file specifically because most PaaS free tiers (Render
    included) don't give you a persistent disk -- a local file would get
    wiped on every restart/redeploy.
    """
    __tablename__ = "corpus_chunks"

    id = Column(String, primary_key=True)  # matches the chunk id from seed_data.py
    topic = Column(String, nullable=False, index=True)
    text = Column(String, nullable=False)
