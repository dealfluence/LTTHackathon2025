from langgraph.graph import StateGraph, START, END
from .workflow_state import ContractAnalysisState
from .workflow_nodes import (
    load_risk_rules_node,
    extract_clauses_node,
    assess_risk_node,
    routing_node,
    human_review_node,
    generate_summary_node,
)


def create_workflow():
    """Create and compile the LangGraph workflow"""

    # Create the state graph
    workflow = StateGraph(ContractAnalysisState)

    # Add nodes
    workflow.add_node("load_rules", load_risk_rules_node)
    workflow.add_node("extract_clauses", extract_clauses_node)
    workflow.add_node("assess_risk", assess_risk_node)
    workflow.add_node("route_decision", routing_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("generate_summary", generate_summary_node)

    # Define the workflow edges
    workflow.add_edge(START, "load_rules")
    workflow.add_edge("load_rules", "extract_clauses")
    workflow.add_edge("extract_clauses", "assess_risk")
    workflow.add_edge("assess_risk", "route_decision")

    # Conditional routing based on risk level
    def should_review(state):
        return (
            "human_review"
            if state.get("review_required", False)
            else "generate_summary"
        )

    workflow.add_conditional_edges(
        "route_decision",
        should_review,
        {"human_review": "human_review", "generate_summary": "generate_summary"},
    )

    workflow.add_edge("human_review", "generate_summary")
    workflow.add_edge("generate_summary", END)

    # Compile the workflow
    return workflow.compile()
