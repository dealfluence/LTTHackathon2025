from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
import asyncio


async def send_status_if_websocket_available(websocket, status: str):
    """Helper function to send status updates if websocket is available"""
    if websocket:
        try:
            await websocket.send_json({"type": "status_update", "status": status})
        except Exception as e:
            # Silently handle websocket errors to not break the flow
            pass


# Pydantic model for the router's structured output
class RouteDecision(BaseModel):
    decision: Literal["answer_directly", "escalate_to_lawyer"] = Field(
        description="The decision to either answer the user directly or escalate to a human lawyer."
    )


class LawyerFeedbackDecision(BaseModel):
    feedback_type: Literal["approve_briefing", "provide_corrections"] = Field(
        description="Whether the lawyer approved the briefing or provided corrections"
    )
    extracted_suggestions: str = Field(
        description="Any corrections, modifications, or additional guidance from the lawyer"
    )


def lawyer_feedback_router_node(state: dict, llm: ChatGoogleGenerativeAI):
    """Routes lawyer feedback based on whether it's approval or corrections."""
    lawyer_message = state["lawyer_message"]
    prepared_briefing = state.get("prepared_briefing", "")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Analyze the lawyer's response to determine if they are approving the original briefing or providing corrections/modifications.

APPROVAL indicators: "approved", "looks good", "send it", "this works", "correct", "yes", "okay", "fine"
CORRECTIONS indicators: "change", "modify", "add", "remove", "actually", "instead", "but", "however", "no"

If the response contains ANY corrections, modifications, or additional guidance, classify as "provide_corrections".
Only classify as "approve_briefing" if it's clearly just approval with no changes.

Extract any corrections or suggestions the lawyer provided, even if they also approved parts of the briefing.""",
            ),
            (
                "user",
                """Original briefing: {briefing}

Lawyer response: {lawyer_response}""",
            ),
        ]
    )

    structured_llm = llm.with_structured_output(LawyerFeedbackDecision)
    chain = prompt | structured_llm

    response = chain.invoke(
        {
            "briefing": prepared_briefing,
            "lawyer_response": lawyer_message,
        }
    )

    return {
        "lawyer_feedback_type": response.feedback_type,
        "lawyer_suggestions": response.extracted_suggestions,
    }


def approve_briefing_node(state: dict, llm: ChatGoogleGenerativeAI):
    """Handles approved briefings by formatting the original prepared answer."""
    prepared_briefing = state.get("prepared_briefing", "")
    lawyer_suggestions = state.get("lawyer_suggestions", "")
    history = state["conversation_history"]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Extract and format the proposed answer from this approved legal briefing for the user.

RULES:
- Use the exact proposed answer from the briefing
- Keep it conversational and direct
- Include clause references
- If the lawyer provided minor comments, incorporate them naturally
- No introductory phrases about lawyer approval

EXAMPLE:
Briefing: "User asks: Can they terminate early? Contract says: 30-day notice required (Section 5.2) My proposed answer: Yes, early termination allowed with 30-day written notice. Is this okay?"
Lawyer: "Approved, but mention the penalty"
Response: "Yes, early termination is allowed with 30-day written notice, though early termination charges will apply (Section 5.2)." """,
            ),
            (
                "user",
                """Approved briefing: {briefing}

Any additional lawyer comments: {suggestions}""",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "briefing": prepared_briefing,
            "suggestions": lawyer_suggestions,
        }
    )

    return {
        "base_response": response.content,
        "conversation_history": history + [AIMessage(content=response.content)],
    }


def process_corrections_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """Processes lawyer corrections and synthesizes them into user response."""
    lawyer_message = state["lawyer_message"]
    lawyer_suggestions = state.get("lawyer_suggestions", "")
    escalated_question = state.get("escalated_question", "")
    history = state["conversation_history"]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Convert the lawyer's corrections and guidance into a clear response for the user.

RULES:
- Present the lawyer's guidance naturally and conversationally
- Acknowledge when information has been clarified by legal review
- Include clause references when provided
- Don't say "the lawyer says" - just present the information
- If corrections contradict the original briefing, use the lawyer's version

EXAMPLES:

Example 1 - Simple Correction:
Original question: "Can we terminate the IBM agreement early?"
Lawyer correction: "Yes but add that notice must be written and sent to the specified address"
Response: "Yes, you can terminate early with 30 days written notice sent to IBM's designated address, plus applicable termination charges (Section 3.4)."

Example 2 - Complex Guidance:
Original question: "What are our liability limits?"
Lawyer correction: "The cap only applies to direct damages. Indirect damages and IP indemnification are unlimited. Also mention the mutual nature."
Response: "Direct damages are capped at $15 million for both parties, but this doesn't cover indirect damages or intellectual property indemnification, which remain unlimited (Sections 9-10)."

Contract context: {doc_context}
""",
            ),
            (
                "user",
                """Original question: {question}

Lawyer's corrections/guidance: {corrections}

Additional context: {suggestions}

""",
            ),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "question": escalated_question,
            "corrections": lawyer_message,
            "suggestions": lawyer_suggestions,
            "doc_context": doc_context,
        }
    )

    return {
        "base_response": response.content,
        "conversation_history": history + [AIMessage(content=response.content)],
    }


def escalation_router_node(
    state: dict, llm: ChatGoogleGenerativeAI, escalation_rules: str
):
    """Decides whether to escalate to a lawyer or answer directly."""
    user_message = state["user_message"]
    history = state["conversation_history"]
    websocket = state.get("websocket")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert routing system for a legal AI assistant. Your task is to analyze a user's query and decide if it can be answered by the AI or if it requires escalation to a human lawyer.

You must follow these rules for escalation:
{escalation_rules}

EXAMPLES:

Example 1 - ESCALATE (keyword match):
User: "What are our indemnity obligations under the IBM hosting agreement?"
Decision: escalate_to_lawyer
Reason: Contains "indemnity" which is an escalation keyword

Example 2 - ANSWER DIRECTLY (simple factual):
User: "What's the notice period for terminating our co-hosting agreement with Network Associates?"
Decision: answer_directly
Reason: Simple factual question about contract terms

Example 3 - ANSWER DIRECTLY (sounds complex but is factual):
User: "If we miss a payment under the Snotarator distribution agreement, what happens?"
Decision: answer_directly
Reason: Asking about contract terms for late payment, not about breach/litigation

Based on the user's latest message and the conversation history, decide whether to "answer_directly" or "escalate_to_lawyer".
""",
            ),
            *history,
            ("user", "User Query: {query}"),
        ]
    )

    structured_llm = llm.with_structured_output(RouteDecision)
    chain = prompt | structured_llm

    response = chain.invoke(
        {
            "escalation_rules": escalation_rules,
            "query": user_message,
        }
    )

    # Send status update based on decision
    if websocket:
        if response.decision == "escalate_to_lawyer":
            asyncio.create_task(
                send_status_if_websocket_available(websocket, "escalation")
            )
        else:
            asyncio.create_task(
                send_status_if_websocket_available(websocket, "direct_response")
            )

    return {"decision": response.decision}


def generate_direct_answer_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """Generates a direct answer to the user's query."""
    user_message = state["user_message"]
    history = state["conversation_history"]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are Lumen AI, a legal assistant. Give direct, concise answers using only the contract information provided. If you don't have sufficient information ask clarification questions before escalating the issue.

RESPONSE STYLE:
- Ask clarificatory questions before launching into an answer
- Answer in 1-2 sentences maximum
- State facts directly without introductory phrases
- Include the relevant clause reference in parentheses
- Use natural, conversational language (avoid legal jargon or, if it's unavoidable, include a brief explainer in simple terms)
- No bullet points, special formatting, or section headers
- Offer the user an opportunity to ask for more detail

EXAMPLES:

Example 1 - Simple Answer:
User: "How long is the term of the IBM hosting agreement?"
Response: "The IBM hosting agreement term ends when all Service Option Attachments expire, unless terminated earlier (Section 3.1). Would you like to know if the contract autorenews?"

Example 2 - Clarification Needed:
User: "Can we change the co-hosting fee?"
Response: "I need more details - are you asking about the quarterly payments of $312,500 or the initial $2.5 million payment in the Network Associates agreement? This will help me find the right provision."

Example 3 - Information Not Available:
User: "What's the process for adding subsidiaries to the joint filing agreement?"
Response: "I don't see specific provisions about adding subsidiaries in the HPS joint filing agreement. Can you tell me more about what you're trying to accomplish so I can escalate it to our Legal Team?"

Example 4 - Clarification Needed:
User: Can we (as IBM) share our co-hosting agreement with a third party vendor we need to use to deliver the services?
Response: Is the vendor you're referring to integral to IBM's delivery of services to BlueFly Inc? If so, then section 14.6 of the co-hosting agreement permits you to do this (without prior consent from BlueFly Inc). Would you like me to check if other conditions apply (e.g. ensuring the relevant vendor complies with the co-hosting agreement)?
Contract: {doc_context}
""",
            ),
            *history,
            ("user", "{query}"),
        ]
    )

    chain = prompt | llm
    response = chain.invoke({"doc_context": doc_context, "query": user_message})

    return {
        "base_response": response.content,
        "conversation_history": history
        + [HumanMessage(content=user_message), AIMessage(content=response.content)],
    }


def generate_lawyer_briefing_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """
    Analyzes the user's question, finds relevant info in the knowledge base,
    and prepares a briefing for the lawyer.
    """
    user_message = state["user_message"]
    history = state["conversation_history"]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You're briefing a busy lawyer. Be extremely concise and professional.

FORMAT:
"User asks: [brief restatement]
Contract says: [key fact + clause reference]
My proposed answer: [1 sentence response]
Is this okay?"

EXAMPLES:

Example 1 - Simple Termination Question:
"User asks: Can Bluefly terminate the IBM agreement early?
Contract says: Yes, with 1 month notice + early termination charges (Section 3.4)
My proposed answer: Yes, you can terminate with 30 days' notice but must pay applicable early termination charges.
Is this okay?"

Example 2 - Complex Liability Question:
"User asks: What's our liability cap under the co-hosting agreement?
Contract says: Part 1: $15 million cap for direct damages (Section 10). Part 2: Excludes third party claims, lost data, and consequential damages (Sections 9-10)
My proposed answer: Direct damages are capped at $15 million, but indemnification for patent/copyright infringement and third party claims remain uncapped.
Is this okay?"

Example 3 - Missing Information:
"User asks: Are non-compete clauses enforceable for the Snotarator distributorship?
Contract says: Agreement prohibits competitive products (Section 1.04) but no jurisdiction-specific enforceability provisions
My proposed answer: Need legal guidance - enforceability varies by jurisdiction and isn't specified in the agreement.
Is this okay?"

Contract: {doc_context}
""",
            ),
            ("human", "User Query: {query}"),
        ]
    )

    chain = prompt | llm
    briefing = chain.invoke({"doc_context": doc_context, "query": user_message}).content

    response_for_user = "Checking with legal counsel on this one."

    return {
        "response_to_user": response_for_user,
        "message_to_lawyer": briefing,
        "prepared_briefing": briefing,
        "escalated_question": user_message,
        "conversation_history": history
        + [
            HumanMessage(content=user_message),
            AIMessage(content=response_for_user),
        ],
    }


def contextual_enhancement_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """
    Analyzes the base response and user query to potentially enhance the response
    with relevant contextual information from the contract.
    """
    base_response = state.get("base_response")
    user_message = state.get("user_message") or state.get("escalated_question")
    history = state["conversation_history"]
    websocket = state.get("websocket")

    print(f"Contextual enhancement - base_response exists: {bool(base_response)}")
    print(f"Contextual enhancement - user_message: {user_message}")
    print(f"Contextual enhancement - doc_context exists: {bool(doc_context)}")

    # Validate inputs before proceeding
    if not base_response:
        print("Error: No base_response found in state")
        return {
            "response_to_user": "An error occurred processing your request.",
            "conversation_history": history,
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }

    if not user_message:
        print(
            "Warning: No user_message or escalated_question found in state - returning base response"
        )
        return {
            "response_to_user": base_response,
            "conversation_history": history,
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }

    # Ensure we have valid strings (not None)
    user_message = str(user_message).strip()
    base_response = str(base_response).strip()
    doc_context = str(doc_context or "").strip()

    if not user_message or not base_response:
        print("Warning: Empty user_message or base_response - returning base response")
        return {
            "response_to_user": base_response,
            "conversation_history": history,
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }

    # Send status update
    if websocket:
        asyncio.create_task(
            send_status_if_websocket_available(websocket, "contextual_analysis")
        )

    try:
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are a legal AI assistant providing contextual enhancement to contract-related responses. Your role is to add only simple, factual contract details that are directly relevant to the user's question.

CRITICAL RESPONSIBILITIES:
- Only add straightforward contractual facts (dates, amounts, deadlines, basic obligations)
- DO NOT add anything requiring legal interpretation, judgment, or analysis
- DO NOT add information about complex legal concepts, liability, indemnification, or dispute resolution
- If the enhancement would require legal expertise to interpret, respond with "NO_ENHANCEMENT_NEEDED"
- Focus only on operational details the user should know

ENHANCEMENT RULES:
- Only enhance if there's something genuinely important they should know
- Add context naturally to the existing response
- Keep additions brief - one short sentence max
- Focus on deadlines, payment amounts, notice periods, or basic procedural requirements
- If nothing important to add, respond with exactly: "NO_ENHANCEMENT_NEEDED"

EXAMPLES:

Example 1 - Safe Enhancement:
User Query: "When do we need to pay IBM for hosting services?"
Base Response: "Payment is due upon receipt of invoice (Section 4.2)."
Enhanced Response: "Payment is due upon receipt of invoice (Section 4.2). Note that late payments incur fees as specified in the invoice terms."

Example 2 - No Enhancement (too complex):
User Query: "What are our liability limits?"
Base Response: "Direct damages are capped at $15 million (Section 10)."
Enhanced Response: "NO_ENHANCEMENT_NEEDED"

Example 3 - Safe Enhancement:
User Query: "What's the notice period for termination?"
Base Response: "30 days written notice is required (Section 3.4)."
Enhanced Response: "30 days written notice is required (Section 3.4), and notice must be sent to the address specified in Section 12.1."
""",
                ),
                (
                    "user",
                    """User asked: {user_message}

Current response: {base_response}

Contract details: {doc_context}

Enhance the response with one relevant factual detail if beneficial, otherwise respond "NO_ENHANCEMENT_NEEDED".""",
                ),
            ]
        )

        chain = prompt | llm
        response = chain.invoke(
            {
                "user_message": user_message,
                "base_response": base_response,
                "doc_context": doc_context,
            }
        )

        # Check if enhancement was deemed necessary
        if response.content.strip() == "NO_ENHANCEMENT_NEEDED":
            final_response = base_response
        else:
            final_response = response.content

        return {
            "response_to_user": final_response,
            "conversation_history": history,
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }

    except Exception as e:
        print(f"Error in contextual enhancement: {e}")
        print(f"user_message: '{user_message}'")
        print(f"base_response length: {len(base_response)}")
        print(f"doc_context length: {len(doc_context)}")
        # If there's an error, just return the base response and clear state
        return {
            "response_to_user": base_response,
            "conversation_history": history,
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }
