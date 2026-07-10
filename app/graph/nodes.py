"""
NEXUS graph nodes.

Flow per loop:
    retrieve_context -> generate_question -> await_answer (interrupt)
        -> judge_answer -> route: loop back OR generate_report
"""

from langgraph.types import interrupt

from app.graph.state import NexusState, Turn
from app.models.groq_client import call_groq_structured
from app.models.schemas import QuestionOutput, JudgeOutput, ReportOutput
from app.rag.retriever import retrieve_context


def retrieve_context_node(state: NexusState) -> dict:
    """Pulls relevant prep material from Pinecone for this topic."""
    query = f"{state['topic']} {state['difficulty']} interview question"
    context = retrieve_context(topic=state["topic"], query=query, top_k=3)
    return {"retrieved_context": context}


def generate_question_node(state: NexusState) -> dict:
    """Groq generates the next interview question, grounded in RAG context."""
    system_prompt = (
        "You are NEXUS, a rigorous but fair technical interviewer conducting "
        "a text-based mock interview -- the candidate types a short written "
        "answer, they cannot draw diagrams or write extensive code.\n\n"
        "Generate ONE interview question at a time. Do not repeat previous "
        "questions.\n\n"
        "Critical scope constraint: ask a SPECIFIC, FOCUSED question "
        "answerable in 2-5 sentences of plain text -- not an open-ended "
        "prompt that would need a whiteboard, a diagram, or 30+ minutes to "
        "properly answer.\n"
        "- For System Design topics specifically: do NOT ask 'design a "
        "system that does X with requirements A, B, C' (that's a full "
        "whiteboard exercise). Instead ask about ONE specific decision, "
        "component, or tradeoff -- e.g. 'how would you shard this "
        "database?', 'why choose a message queue over direct calls here?', "
        "'what's the tradeoff between strong and eventual consistency for "
        "this use case?'\n"
        "- For coding/DSA topics: ask about approach, complexity, or "
        "reasoning rather than requiring full working code to be typed out.\n"
        "- Prefer questions that test understanding of ONE concept deeply "
        "over broad multi-part scenarios stacking several requirements."
    )

    previous_qs = "\n".join(
        f"- {t['question']}" for t in state.get("conversation_history", [])
    )

    user_prompt = f"""
Topic: {state['topic']}
Difficulty: {state['difficulty']}
Question number: {state['question_number'] + 1} of {state['max_questions']}

Relevant prep material (optional grounding, use only if helpful):
{state.get('retrieved_context', '(none)')}

Previously asked questions (do not repeat these):
{previous_qs or '(none yet)'}

Generate the next interview question.
"""

    result: QuestionOutput = call_groq_structured(system_prompt, user_prompt, QuestionOutput)

    return {
        "current_question": result.question,
        "current_topic_tag": result.topic_tag,
    }


def await_answer_node(state: NexusState) -> dict:
    """
    Human-in-the-loop pause point. Execution stops here until the API layer
    calls graph.invoke(Command(resume=<answer>), config=...) with the
    candidate's answer.
    """
    answer = interrupt(
        {
            "question": state["current_question"],
            "question_number": state["question_number"] + 1,
        }
    )
    return {"current_answer": answer}


def judge_answer_node(state: NexusState) -> dict:
    """Groq scores the answer and produces feedback."""
    system_prompt = (
        "You are a strict but constructive technical interview judge. "
        "Score fairly out of 10. Be specific in feedback -- reference what "
        "was missing or done well."
    )

    user_prompt = f"""
Topic: {state['topic']}
Question: {state['current_question']}
Candidate's answer: {state['current_answer']}

Reference material (for grounding your judgment, not to be quoted verbatim):
{state.get('retrieved_context', '(none)')}

Evaluate the answer.
"""

    result: JudgeOutput = call_groq_structured(system_prompt, user_prompt, JudgeOutput)

    new_turn: Turn = {
        "question_number": state["question_number"] + 1,
        "question": state["current_question"],
        "answer": state["current_answer"],
        "score": result.score,
        "feedback": result.feedback,
        "is_weak": result.is_weak,
        "topic_tag": state["current_topic_tag"],
    }

    update = {
        "conversation_history": [new_turn],
        "current_score": result.score,
        "current_feedback": result.feedback,
        "question_number": state["question_number"] + 1,
    }

    if result.is_weak:
        update["weak_areas"] = [state["current_topic_tag"]]

    return update


def route_after_judge(state: NexusState) -> str:
    """Supervisor-style router: keep looping or wrap up."""
    if state["question_number"] >= state["max_questions"]:
        return "generate_report"
    return "retrieve_context"


def generate_report_node(state: NexusState) -> dict:
    """Groq synthesizes the full interview into a final report."""
    system_prompt = (
        "You are NEXUS, summarizing a completed mock interview into a "
        "clear, encouraging but honest performance report."
    )

    transcript = "\n\n".join(
        f"Q{t['question_number']} ({t['topic_tag']}, score {t['score']}/10): "
        f"{t['question']}\nAnswer: {t['answer']}\nFeedback: {t['feedback']}"
        for t in state["conversation_history"]
    )

    user_prompt = f"""
Full interview transcript:
{transcript}

Flagged weak areas: {state.get('weak_areas', [])}

Generate the final report.
"""

    result: ReportOutput = call_groq_structured(system_prompt, user_prompt, ReportOutput)

    report_text = (
        f"## Interview Report: {state['topic']} ({state['difficulty']})\n\n"
        f"{result.summary}\n\n"
        f"**Strengths:**\n" + "\n".join(f"- {s}" for s in result.strengths) + "\n\n"
        f"**Weak Areas:**\n" + "\n".join(f"- {w}" for w in result.weak_areas) + "\n\n"
        f"**Study Plan:**\n" + "\n".join(f"- {s}" for s in result.study_plan)
    )

    return {"final_report": report_text, "is_complete": True}
