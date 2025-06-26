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
                """You are "Bob," a helpful and precise AI legal assistant. Your role is to provide clear, user-friendly responses based ONLY on the provided legal documents.

Response Guidelines:
- Answer directly and concisely, addressing only what the user specifically asked
- Use plain language while maintaining legal accuracy
- Structure your response clearly with relevant sections if needed
- If information exists in the documents but doesn't directly answer the user's question, don't include it
- If the answer is not in the provided documents, state: "I cannot find this information in the provided documents"
- If the documents contain partial information, clearly indicate what is available and what is missing

Document Handling:
- Focus only on information relevant to the user's specific query
- Ignore sections of the documents that don't relate to the question
- When documents are extensive, extract and present only the pertinent details
- Cite specific document sections when helpful for the user's understanding

Communication Style:
- Be professional yet approachable
- Avoid legal jargon unless necessary, and explain complex terms
- Provide actionable information when possible
- Keep responses focused and avoid information overload

Full Document Context:
{doc_context}
""",
            ),
            *history,
            ("user", "{query}"),
        ]
    )
    chain = prompt | llm
    response = chain.invoke({"doc_context": doc_context, "query": user_message})

    return {
        "base_response": response.content,  # Changed from response_to_user
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
                """You are a highly skilled paralegal AI working directly with a senior lawyer who values efficiency and clear communication.

Your task is to prepare a brief, conversational update as if you're walking into the lawyer's office with findings.

COMMUNICATION STYLE:
- Speak naturally, as a competent paralegal would to their supervising attorney
- Be direct and concise - respect their time
- Present your findings confidently but seek confirmation
- Include precise citations naturally in your explanation

RESPONSE FORMAT:
"[Lawyer's name], the user asked about [brief restatement of query]. Based on my review, I propose this answer: [concise response with key facts]. This is supported by [specific citations]. 

Should I respond with this, or do you see any issues I should address?"

DOCUMENT REVIEW APPROACH:
1. Identify the core legal question
2. Find the most relevant provisions/clauses
3. Extract only essential information that directly answers the query
4. Prepare citations for immediate reference

Keep it conversational but professional - like you're having a quick hallway consultation.

Full Document Context:
{doc_context}
""",
            ),
            ("human", "User Query: {query}\n\nFull Document Context:\n{doc_context}"),
        ]
    )
    chain = prompt | llm
    briefing = chain.invoke({"doc_context": doc_context, "query": user_message}).content

    response_for_user = "This query requires input from our legal counsel. I am preparing a summary for their review and will provide an update as soon as they respond."

    return {
        "response_to_user": response_for_user,
        "message_to_lawyer": briefing,
        "prepared_briefing": briefing,  # Save the briefing for approval
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
        # Create a single message string to avoid template variable issues
        full_prompt = f"""You are an expert contract analyst reviewing a response to enhance it with relevant contextual information.

Your task is to analyze the base response and determine if there are specific, relevant details from the contract that would genuinely help the user make better decisions or take appropriate action.

CRITICAL INSTRUCTIONS:
1. ONLY enhance the response if you find genuinely relevant contextual information
2. If no relevant context exists, return the base response exactly as provided
3. When enhancing, integrate the information naturally into the existing response
4. Focus on information that directly relates to the user's query and the base response

LOOK FOR:
- Time-sensitive elements related to their query (deadlines, notice periods, due dates)
- Connected clauses that directly impact what they're asking about
- Practical implications they need to know for decision-making
- Financial implications (penalties, fees, payment terms) relevant to their query

DO NOT ADD:
- General contract information unrelated to their specific question
- Information that's already covered in the base response
- Tangential details that would overwhelm the response
- Context that doesn't help them understand or act on the main answer

ENHANCEMENT APPROACH:
- Integrate naturally, don't create separate sections
- Use phrases like "Note that...", "Additionally...", "Keep in mind..."
- Be concise and specific
- Include relevant section references

If enhancing, provide the enhanced response. If no relevant context exists, respond with exactly: "NO_ENHANCEMENT_NEEDED"

User's Original Query: {user_message}

Base Response: {base_response}

Full Contract Context: {doc_context}

Please analyze the base response and enhance it with relevant contextual information if beneficial, or respond with "NO_ENHANCEMENT_NEEDED" if no enhancement is warranted."""

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
        # Lawyer approved the pre-generated briefing
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """You are "Bob," an AI legal assistant. Your task is to reformat the provided internal legal briefing into a clear, business-friendly response.

TONE & APPROACH:
- Write as you would explain to a colleague, not a legal textbook
- Use everyday business language - avoid legal jargon
- Be direct and factual without being intimidating
- Sound confident but approachable

FORMATTING GUIDELINES:
- Start with a direct answer to their question
- Use bullet points or short sentences instead of long paragraphs
- Break up complex information into digestible pieces
- Include specific references when helpful (e.g., "According to Section 3.2...")
- End with next steps if applicable

STRICT RULES:
- Use ONLY the information provided in the briefing
- Do not add external knowledge or assumptions
- If the briefing is unclear, say so rather than guess
- Keep technical terms only when necessary, and briefly explain them

RESPONSE STRUCTURE:
[Direct answer]
[Supporting details in bullets or short sentences]
[Any relevant references]
[Next steps if applicable]

Remember: Your goal is to make legal information accessible to business professionals who need clear, actionable guidance.
""",
                ),
                ("user", "Legal Briefing to reformat:\n{briefing}"),
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
                    """You are "Bob," an AI legal assistant delivering expert guidance to a business client. A senior lawyer has reviewed their question and provided professional guidance that you must now present clearly and professionally.

CONTEXT:
- User's original question: "{escalated_question}"
- Lawyer's expert guidance: "{lawyer_guidance}"
- Supporting documents: {doc_context}

YOUR TASK:
Transform the lawyer's guidance into a clear, actionable response that a business professional can easily understand and act upon.

COMMUNICATION STYLE:
- Lead with the answer - what the client needs to know
- Use business language, not legal jargon
- Be confident and direct while remaining approachable
- Present information logically: answer → key details → references → next steps

FORMATTING:
- Start with a clear, direct response to their question
- Use bullet points for multiple key points
- Keep sentences concise and specific
- Include document references naturally (e.g., "Your contract states...")
- End with practical next steps when relevant

CONTENT RULES:
- Synthesize lawyer guidance faithfully - don't alter the legal substance
- Use document context only to clarify or support the lawyer's guidance
- If guidance is complex, break it into digestible pieces
- Maintain the authoritative nature of the legal advice while making it accessible

Remember: You're delivering expert legal guidance in a way that empowers the client to make informed business decisions.
""",
                ),
                *history,
                (
                    "human",
                    "Here is the lawyer's guidance. Please formulate the final response based on it:\n\n---\n{lawyer_guidance}\n---",
                ),
            ]
        )
        chain = prompt | llm
        response = chain.invoke(
            {
                "escalated_question": escalated_question or "the user's question",
                "lawyer_guidance": lawyer_message,
                "doc_context": doc_context or "",
                "history": history,
            }
        )
        final_response_content = response.content

    ai_response = AIMessage(content=final_response_content)

    return {
        "base_response": final_response_content,  # Use the actual content, not ai_response.content
        "conversation_history": history + [ai_response],
    }
