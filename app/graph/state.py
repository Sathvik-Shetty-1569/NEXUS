"""
NexusState - the shared state object passed between every node in the
NEXUS interview-prep LangGraph.

Design rule of thumb:
    - "snapshot" fields (current_*) get overwritten every loop -> plain type
    - "ledger" fields (history, weak_areas) must accumulate -> Annotated + operator.add
"""

from typing import TypedDict, Annotated, Literal
from operator import add


class Turn(TypedDict):
    """A single structured Q&A turn, stored in conversation_history."""
    question_number: int
    question: str
    answer: str
    score: int              # 0-10 from the judge node
    feedback: str
    is_weak: bool
    topic_tag: str           # sub-topic within the broader interview topic


class NexusState(TypedDict):
    # ---- interview setup (set once at /start_interview) ----
    topic: str                          # e.g. "System Design", "Python DSA"
    difficulty: Literal["easy", "medium", "hard"]
    max_questions: int

    # ---- per-turn scratch space (overwritten every loop) ----
    current_question: str
    current_answer: str
    current_score: int
    current_feedback: str
    current_topic_tag: str

    # ---- loop control ----
    question_number: int
    is_complete: bool

    # ---- ledgers (accumulate across the whole interview) ----
    conversation_history: Annotated[list[Turn], add]
    weak_areas: Annotated[list[str], add]

    # ---- RAG context for the current question ----
    retrieved_context: str

    # ---- final output ----
    final_report: str
