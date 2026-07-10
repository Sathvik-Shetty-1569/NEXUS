from psycopg_pool import ConnectionPool
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from app.config import DATABASE_URL
from app.graph.state import NexusState
from app.graph.nodes import (
    retrieve_context_node,
    generate_question_node,
    await_answer_node,
    judge_answer_node,
    route_after_judge,
    generate_report_node,
)


def build_nexus_graph():
    graph = StateGraph(NexusState)

    graph.add_node("retrieve_context", retrieve_context_node)
    graph.add_node("generate_question", generate_question_node)
    graph.add_node("await_answer", await_answer_node)
    graph.add_node("judge_answer", judge_answer_node)
    graph.add_node("generate_report", generate_report_node)

    graph.add_edge(START, "retrieve_context")
    graph.add_edge("retrieve_context", "generate_question")
    graph.add_edge("generate_question", "await_answer")
    graph.add_edge("await_answer", "judge_answer")

    graph.add_conditional_edges(
        "judge_answer",
        route_after_judge,
        {
            "retrieve_context": "retrieve_context",
            "generate_report": "generate_report",
        },
    )

    graph.add_edge("generate_report", END)

    # Connection pool, not a single connection: managed Postgres providers
    # (Render, Railway, Supabase) close idle connections after a while --
    # a pool reconnects automatically instead of requiring an app restart.
    # min_size=1 keeps this cheap for a 5-10 user deployment.
    pool = ConnectionPool(
        conninfo=DATABASE_URL,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()  # idempotent -- creates checkpoint tables if missing

    return graph.compile(checkpointer=checkpointer)


nexus_graph = build_nexus_graph()
