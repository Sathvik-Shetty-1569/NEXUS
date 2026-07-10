from pydantic import BaseModel, Field


class QuestionOutput(BaseModel):
    question: str = Field(..., description="The interview question to ask the candidate")
    topic_tag: str = Field(..., description="Specific sub-topic this question tests, e.g. 'hashmaps', 'CAP theorem'")


class JudgeOutput(BaseModel):
    score: int = Field(..., ge=0, le=10, description="Score out of 10 for the candidate's answer")
    feedback: str = Field(..., description="2-3 sentences of specific, actionable feedback")
    is_weak: bool = Field(..., description="True if score <= 5, indicating a weak area")


class ReportOutput(BaseModel):
    summary: str = Field(..., description="Overall 3-4 sentence performance summary")
    strengths: list[str] = Field(..., description="List of topics/skills the candidate did well on")
    weak_areas: list[str] = Field(..., description="List of topics that need more practice")
    study_plan: list[str] = Field(..., description="3-5 concrete, actionable next steps for the candidate")
