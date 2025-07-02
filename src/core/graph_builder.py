from functools import partial
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from .conversation_state import ConversationState
from .graph_nodes import (
    approve_briefing_node,
    escalation_router_node,
    generate_direct_answer_node,
    generate_lawyer_briefing_node,
    contextual_enhancement_node,
    lawyer_feedback_router_node,
    process_corrections_node,
)


def should_escalate(state: dict) -> str:
    """Conditional edge to decide the path after routing."""
    return (
        "generate_briefing"
        if state.get("decision") == "escalate_to_lawyer"
        else "answer"
    )


def route_lawyer_feedback(state: dict) -> str:
    """Conditional edge to route lawyer feedback based on type."""
    feedback_type = state.get("lawyer_feedback_type", "provide_corrections")
    return feedback_type


def get_entry_point(state: dict) -> str:
    """Conditional entry point for user vs. lawyer messages."""
    if state.get("lawyer_message"):
        return "lawyer_feedback_router"
    return "router"


def create_conversational_graph(
    llm: ChatGoogleGenerativeAI, doc_context: str, escalation_rules: str
):
    """
    Creates the LangGraph agent for the legal bot.
    """
    workflow = StateGraph(ConversationState)

    # Bind the LLM and context to the node functions
    router_node = partial(
        escalation_router_node,
        llm=llm,
        escalation_rules=escalation_rules,
    )
    answer_node = partial(generate_direct_answer_node, llm=llm, doc_context=doc_context)
    briefing_node = partial(
        generate_lawyer_briefing_node, llm=llm, doc_context=doc_context
    )
    # NEW: Lawyer feedback nodes
    lawyer_router_node = partial(lawyer_feedback_router_node, llm=llm)
    approve_node = partial(approve_briefing_node, llm=llm)
    corrections_node = partial(
        process_corrections_node, llm=llm, doc_context=doc_context
    )

    contextual_node = partial(
        contextual_enhancement_node, llm=llm, doc_context=doc_context
    )

    # Add nodes to the graph
    workflow.add_node("router", router_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("generate_briefing", briefing_node)
    # NEW: Replace handle_lawyer_response with router + handlers
    workflow.add_node("lawyer_feedback_router", lawyer_router_node)
    workflow.add_node("approve_briefing", approve_node)
    workflow.add_node("provide_corrections", corrections_node)
    workflow.add_node("contextual_enhancement", contextual_node)

    # Define the graph's topology
    workflow.set_conditional_entry_point(
        get_entry_point,
        {
            "router": "router",
            "lawyer_feedback_router": "lawyer_feedback_router",  # CHANGED: was "handle_lawyer_response"
        },
    )
    workflow.add_conditional_edges(
        "router",
        should_escalate,
        {
            "generate_briefing": "generate_briefing",
            "answer": "answer",
        },
    )

    # NEW: Lawyer feedback routing
    workflow.add_conditional_edges(
        "lawyer_feedback_router",
        route_lawyer_feedback,
        {
            "approve_briefing": "approve_briefing",
            "provide_corrections": "provide_corrections",
        },
    )

    # All paths lead to contextual enhancement
    workflow.add_edge("answer", "contextual_enhancement")
    workflow.add_edge("approve_briefing", "contextual_enhancement")
    workflow.add_edge("provide_corrections", "contextual_enhancement")

    # Only the briefing goes directly to END
    workflow.add_edge("generate_briefing", END)

    # Final enhanced response goes to END
    workflow.add_edge("contextual_enhancement", END)

    return workflow.compile()
