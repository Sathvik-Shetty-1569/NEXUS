import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "nexus-interview-kb")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")

# --- Persistence ---
# Postgres backs users, interview history, the LangGraph checkpointer, AND
# the BM25 corpus mirror -- deliberately one database for all durable
# state, so there's nothing on local disk that a redeploy could wipe.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/nexus"
)

# --- Auth (JWT-based sessions, email+password and Google OAuth) ---
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24h

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"
)
# Where to send the browser after a successful Google login
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8000")

# --- Rate limiting (protects Groq spend) ---
GROQ_RATE_LIMIT_CALLS = int(os.getenv("GROQ_RATE_LIMIT_CALLS", "20"))
GROQ_RATE_LIMIT_PERIOD_SECONDS = float(os.getenv("GROQ_RATE_LIMIT_PERIOD_SECONDS", "60"))

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY missing. Copy .env.example to .env and fill it in.")

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY missing. Generate one with: "
        "python -c \"import secrets; print(secrets.token_urlsafe(32))\" "
        "and put it in .env."
    )
