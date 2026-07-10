from typing import Literal
from pydantic import BaseModel


class StartInterviewRequest(BaseModel):
    topic: str
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    max_questions: int = 5


class StartInterviewResponse(BaseModel):
    thread_id: str
    question_number: int
    question: str


class SubmitAnswerRequest(BaseModel):
    thread_id: str
    answer: str


class SubmitAnswerResponse(BaseModel):
    is_complete: bool
    question_number: int | None = None
    question: str | None = None
    last_score: int | None = None
    last_feedback: str | None = None


class ReportResponse(BaseModel):
    thread_id: str
    is_complete: bool
    report: str | None = None


class InterviewSummary(BaseModel):
    thread_id: str
    topic: str
    difficulty: str
    is_complete: bool
    created_at: str
