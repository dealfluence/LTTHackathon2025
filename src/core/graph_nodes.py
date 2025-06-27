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

Based on the user's latest message and the conversation history, decide whether to "answer_directly" or "escalate_to_lawyer".
""",
            ),
            ("user", "Conversation History:\n{history}\n\nUser Query: {query}"),
        ]
    )

    structured_llm = llm.with_structured_output(RouteDecision)
    chain = prompt | structured_llm

    response = chain.invoke(
        {
            "escalation_rules": escalation_rules,
            "history": "\n".join([f"{msg.type}: {msg.content}" for msg in history]),
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
                """You are Bob, a legal assistant. Give direct, concise answers using only the contract information provided. If you don't have sufficient information (from the user query) ask clarification questions before esclating the issue.

RESPONSE STYLE:
- Ask clarificatory questions before launching into an answer
- Answer in 1-2 sentences maximum
- State facts directly without introductory phrases
- Include the relevant clause reference in parentheses
- Use natural, conversational language (avoid legal jargon or, if it's unavoidable, include a brief explainer in simple terms)
- No bullet points, special formatting, or section headers
- Offer the user an opportunity to ask for more detail 

EXAMPLES:
- "Yes, you can terminate with 30-day written notice (Section 5.2)."
- "Payment is due within 15 days of invoice date (Section 3.1)."
- "No, confidentiality obligations continue for 2 years post-termination (Section 8.3)."

If the answer isn't in the contract, say: "I don't see that information in the documentation I have access to. Can you tell me a bit more about your issue so I can escalate it to our Legal Team?"

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
Any concerns?"

EXAMPLE:
"User asks: Can they terminate early?
Contract says: 30-day notice required, no penalty (Section 5.2)
My proposed answer: Yes, early termination allowed with 30-days' written notice.
Any concerns?"

Keep it short - lawyers don't have time for lengthy briefings. 
Where an answer needs to be more detailed because of query complexity (e.g. regarding indemnities or liability), split the draft response into two parts: first part should focus on provisions directly relevant to the user query (e.g. for a question about liability caps, focus on aggregate caps and super caps) and then, in the second part, summarise closely connected concepts/provisions (e.g. liabilities that are uncapped - such as those covered by indemnity) so that the lawyer can decide whether to return a fuller response to the user. 

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
        # Create a concise enhancement prompt
        full_prompt = f"""Look at this response and see if there's one important related detail from the contract that the user should know. Only add it if it's directly relevant and actionable.

RULES:
- Only enhance if there's something genuinely important they should know
- Add context naturally to the existing response
- Keep additions brief - one short sentence max
- Focus on deadlines, penalties, or connected obligations
- If nothing important to add, respond with exactly: "NO_ENHANCEMENT_NEEDED"

User asked: {user_message}

Current response: {base_response}

Contract details: {doc_context}

Enhance the response with one relevant detail if beneficial, otherwise respond "NO_ENHANCEMENT_NEEDED"."""

        # Use the LLM directly with a simple message structure
        from langchain_core.messages import HumanMessage

        response = llm.invoke([HumanMessage(content=full_prompt)])

        # Check if enhancement was deemed necessary
        if response.content.strip() == "NO_ENHANCEMENT_NEEDED":
            final_response = base_response
        else:
            final_response = response.content

        return {
            "response_to_user": final_response,
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
            "base_response": None,
            "escalated_question": None,
            "prepared_briefing": None,
        }


def handle_lawyer_response_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """
    Handles the lawyer's response, either by reformatting an approved briefing
    or synthesizing a new answer based on corrections.
    """
    lawyer_message = state["lawyer_message"]
    prepared_briefing = state.get("prepared_briefing")
    escalated_question = state.get("escalated_question")
    history = state["conversation_history"]

    # Simple check for approval keywords
    is_approval = any(
        keyword in lawyer_message.lower()
        for keyword in ["approve", "approved", "yes", "correct", "go ahead", "proceed"]
    )

    if is_approval and prepared_briefing:
        # Lawyer approved the pre-generated briefing - extract the proposed answer
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Extract the proposed answer from this legal briefing and present it naturally to the user.

RULES:
- Use the exact proposed answer from the briefing
- Keep it conversational and direct
- Include clause references
- No introductory phrases or explanations

EXAMPLE:
Briefing: "User asks: Can they terminate early? Contract says: 30-day notice required (Section 5.2) My proposed answer: Yes, early termination allowed with 30-day written notice. Any concerns?"
Response: "Yes, early termination allowed with 30-day written notice (Section 5.2)."
""",
                ),
                ("user", "Briefing: {briefing}"),
            ]
        )
        chain = prompt | llm
        response = chain.invoke({"briefing": prepared_briefing})
        final_response_content = response.content
    else:
        # Lawyer provided corrections or a new answer
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Present the lawyer's guidance to the user in a natural, conversational way.

RULES:
- Keep it concise and direct
- Present facts without preamble
- Include clause references when mentioned
- Sound professional but human
- Don't add "the lawyer says" or similar phrases

The lawyer has provided guidance on: {escalated_question}
Lawyer's guidance: {lawyer_guidance}
""",
                ),
                (
                    "human",
                    "Convert this guidance into a direct response for the user: {lawyer_guidance}",
                ),
            ]
        )
        chain = prompt | llm
        response = chain.invoke(
            {
                "escalated_question": escalated_question or "the user's question",
                "lawyer_guidance": lawyer_message,
            }
        )
        final_response_content = response.content

    return {
        "base_response": final_response_content,
        "conversation_history": history + [AIMessage(content=final_response_content)],
    }
