import json
from pathlib import Path
from typing import Dict, Any
from langchain_anthropic import ChatAnthropic
from pydantic import BaseModel, Field
from typing import Literal


# Pydantic models for structured output
class ExtractedClauses(BaseModel):
    termination_clause: str = Field(description="Termination clause text")
    indemnity_clause: str = Field(description="Indemnity clause text")
    governing_law: str = Field(description="Governing law jurisdiction")
    liability_caps: str = Field(description="Liability limitation clause")
    force_majeure: str = Field(description="Force majeure clause")
    payment_terms: str = Field(description="Payment terms")


class RiskAssessment(BaseModel):
    termination_risk: Literal["low", "medium", "high"] = Field(
        description="Risk level for termination terms"
    )
    indemnity_risk: Literal["low", "medium", "high"] = Field(
        description="Risk level for indemnity terms"
    )
    governing_law_risk: Literal["low", "medium", "high"] = Field(
        description="Risk level for governing law"
    )
    liability_risk: Literal["low", "medium", "high"] = Field(
        description="Risk level for liability terms"
    )
    overall_risk: Literal["low", "medium", "high"] = Field(
        description="Overall contract risk level"
    )
    risk_score: int = Field(description="Numerical risk score 1-10")
    red_flags: list[str] = Field(description="List of identified red flags")


def load_risk_rules_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Load organizational risk rules"""
    try:
        rules_file = Path("config/risk-rules.json")
        if rules_file.exists():
            with open(rules_file, "r") as f:
                risk_rules = json.load(f)
        else:
            # Default rules if file doesn't exist
            risk_rules = {
                "termination_rules": {"min_notice_days": 60},
                "governing_law_rules": {
                    "approved_jurisdictions": ["New York", "Delaware", "California"]
                },
                "liability_rules": {"max_liability_multiplier": 5.0},
            }

        return {"risk_rules": risk_rules, "current_step": "rules_loaded"}
    except Exception as e:
        return {
            "error": f"Failed to load risk rules: {str(e)}",
            "current_step": "error",
        }


def extract_clauses_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key clauses from contract"""
    try:
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0.1)

        structured_llm = llm.with_structured_output(ExtractedClauses)

        prompt = f"""
        You are a legal contract analyzer. Extract the following key clauses from this contract.
        If a clause is not found, indicate "Not specified" or "Not found".
        
        Contract text:
        {state['document_content']}
        
        Extract:
        1. Termination clause (notice period, conditions)
        2. Indemnity clause 
        3. Governing law jurisdiction
        4. Liability caps or limitations
        5. Force majeure clause
        6. Payment terms
        """

        result = structured_llm.invoke(prompt)

        return {"extracted_clauses": result.dict(), "current_step": "clauses_extracted"}
    except Exception as e:
        return {
            "error": f"Failed to extract clauses: {str(e)}",
            "current_step": "error",
        }


def assess_risk_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Assess legal risks based on extracted clauses and organizational rules"""
    try:
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0.1)

        structured_llm = llm.with_structured_output(RiskAssessment)

        clauses = state.get("extracted_clauses", {})
        risk_rules = state.get("risk_rules", {})

        prompt = f"""
        You are a legal risk assessor. Analyze these contract clauses for legal risks using the organizational risk rules.
        
        Extracted Clauses:
        {json.dumps(clauses, indent=2)}
        
        Organizational Risk Rules:
        {json.dumps(risk_rules, indent=2)}
        
        Assess each clause area and provide:
        1. Individual risk levels (low/medium/high) for each clause type
        2. Overall risk level for the contract
        3. Numerical risk score (1-10, where 10 is highest risk)
        4. List of specific red flags found
        
        Consider factors like:
        - Termination notice periods vs organizational requirements
        - Governing law jurisdiction approval
        - Liability cap reasonableness
        - Unusual or concerning clause language
        """

        result = structured_llm.invoke(prompt)

        return {"risk_assessment": result.dict(), "current_step": "risk_assessed"}
    except Exception as e:
        return {"error": f"Failed to assess risk: {str(e)}", "current_step": "error"}


def routing_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Route to human review if high risk"""
    risk_assessment = state.get("risk_assessment", {})
    overall_risk = risk_assessment.get("overall_risk", "low")

    review_required = overall_risk in [
        "high",
        "medium",
    ]  # Route medium and high risk for review

    return {"review_required": review_required, "current_step": "routing_complete"}


def human_review_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Simulate human review (in real implementation, this would integrate with Teams)"""
    # For web UI, we'll mark as requiring review and let UI handle it
    return {
        "human_feedback": "Pending legal team review",
        "current_step": "awaiting_review",
    }


def generate_summary_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate plain-English summary"""
    try:
        llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0.2)

        clauses = state.get("extracted_clauses", {})
        risk_assessment = state.get("risk_assessment", {})
        document_metadata = state.get("document_metadata", {})

        prompt = f"""
        Create a clear, professional summary of this legal contract analysis for business stakeholders.
        
        Document: {document_metadata.get('filename', 'Contract')}
        
        Extracted Clauses:
        {json.dumps(clauses, indent=2)}
        
        Risk Assessment:
        {json.dumps(risk_assessment, indent=2)}
        
        Create a summary that includes:
        1. Brief overview of the contract
        2. Key terms and clauses in plain English
        3. Risk assessment with specific concerns
        4. Recommended actions
        5. Any red flags that need immediate attention
        
        Write for a business audience - avoid legal jargon where possible.
        """

        response = llm.invoke(prompt)

        return {
            "summary": response.content,
            "analysis_complete": True,
            "current_step": "complete",
        }
    except Exception as e:
        return {
            "error": f"Failed to generate summary: {str(e)}",
            "current_step": "error",
        }
