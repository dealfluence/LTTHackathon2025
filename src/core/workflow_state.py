from typing import Dict, Any, Optional
from typing_extensions import TypedDict


class ContractAnalysisState(TypedDict):
    # Input
    document_content: str
    document_metadata: Dict[str, Any]
    analysis_id: str

    # Processing stages
    risk_rules: Optional[Dict[str, Any]]
    extracted_clauses: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    review_required: bool
    human_feedback: Optional[str]

    # Output
    summary: Optional[str]
    analysis_complete: bool

    # Error handling
    error: Optional[str]
    current_step: str
