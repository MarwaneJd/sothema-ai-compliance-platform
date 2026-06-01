"""Compile the agentic-RAG LangGraph state machine.

The graph is built once per process (compiled at startup) and `invoke`-d per
request. Per-request collaborators (LLM service, retriever, segment repo,
reranker) flow in via a `RunContext` captured by closures in `nodes.py`.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.agentic_rag.nodes import (
    RunContext,
    make_generate_node,
    make_plan_node,
    make_reflect_node,
    make_refine_query_node,
    make_retrieve_node,
    make_verify_node,
    route_after_reflect,
    route_after_retrieve,
    route_after_verify,
)
from app.agents.agentic_rag.state import AgenticRAGState


def build_agentic_rag_graph(ctx: RunContext):
    """Compile the state machine. The returned object exposes async `ainvoke`.

    ```
       plan ──▶ retrieve ──▶ reflect ──┬── sufficient ──▶ generate ──▶ verify ──┬── END
                  ▲                    │                            ↑          │
                  │                    └── insufficient ──▶ refine ─┘          │
                  │                                                            │
                  └────────────────────────────────────────────────────────────┘
                                       (re-generate on verify retry)
    ```
    """
    graph = StateGraph(AgenticRAGState)

    graph.add_node("plan", make_plan_node(ctx))
    graph.add_node("retrieve", make_retrieve_node(ctx))
    graph.add_node("reflect", make_reflect_node(ctx))
    graph.add_node("refine_query", make_refine_query_node(ctx))
    graph.add_node("generate", make_generate_node(ctx))
    graph.add_node("verify", make_verify_node(ctx))

    graph.set_entry_point("plan")
    graph.add_edge("plan", "retrieve")

    graph.add_conditional_edges(
        "retrieve",
        route_after_retrieve,
        {
            "reflect": "reflect",
            "generate": "generate",
        },
    )

    graph.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {
            "refine_query": "refine_query",
            "generate": "generate",
        },
    )
    graph.add_edge("refine_query", "retrieve")
    graph.add_edge("generate", "verify")

    graph.add_conditional_edges(
        "verify",
        route_after_verify,
        {
            "generate": "generate",
            "end": END,
        },
    )

    return graph.compile()
