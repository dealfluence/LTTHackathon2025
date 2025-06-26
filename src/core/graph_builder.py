from functools import partial
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI

from .conversation_state import ConversationState
from .graph_nodes import (
    escalation_router_node,
    generate_direct_answer_node,
    generate_lawyer_briefing_node,
    handle_lawyer_response_node,
)


def should_escalate(state: dict) -> str:
    """Conditional edge to decide the path after routing."""
    return (
        "generate_briefing"
        if state.get("decision") == "escalate_to_lawyer"
        else "answer"
    )


def get_entry_point(state: dict) -> str:
    """Conditional entry point for user vs. lawyer messages."""
    if state.get("lawyer_message"):
        return "handle_lawyer_response"
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
    lawyer_response_node = partial(
        handle_lawyer_response_node, llm=llm, doc_context=doc_context
    )

    # Add nodes to the graph
    workflow.add_node("router", router_node)
    workflow.add_node("answer", answer_node)
    workflow.add_node("generate_briefing", briefing_node)
    workflow.add_node("handle_lawyer_response", lawyer_response_node)

    # Define the graph's topology
    workflow.set_conditional_entry_point(
        get_entry_point,
        {
            "router": "router",
            "handle_lawyer_response": "handle_lawyer_response",
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

    # All paths lead to the end after processing
    workflow.add_edge("answer", END)
    workflow.add_edge("generate_briefing", END)
    workflow.add_edge("handle_lawyer_response", END)

    return workflow.compile()
