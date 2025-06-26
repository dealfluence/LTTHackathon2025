from typing import Literal

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI


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
                """You are "Bob," a helpful and precise AI legal assistant. Your role is to answer user questions based ONLY on the provided legal documents. Do not use any external knowledge. If the answer is not in the documents, state that clearly. Be professional and concise.

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
        "response_to_user": response.content,
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
                """You are a highly skilled paralegal AI. Your task is to prepare a concise briefing memo for a senior lawyer based on the provided user query and the full document context.

1.  Thoroughly review the full document context provided below.
2.  Identify and extract all relevant clauses, sections, and data points that pertain to the user's question.
3.  For each piece of information, cite the document it came from.
4.  Synthesize your findings into a clear, structured summary.
5.  Conclude with a suggested answer to the user.

The final output should be a well-organized memo for the lawyer to review.

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


def handle_lawyer_response_node(
    state: dict, llm: ChatGoogleGenerativeAI, doc_context: str
):
    """
    Handles the lawyer's response, either by reformatting an approved briefing
    or synthesizing a new answer based on corrections.
    """
    lawyer_message = state["lawyer_message"]
    prepared_briefing = state["prepared_briefing"]
    escalated_question = state["escalated_question"]
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
                    """You are "Bob," an AI legal assistant. Your task is to reformat the following internal legal briefing into a clear, professional response for a business client.
Do not add any new information. Simply make it easy for a non-lawyer to understand.
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
                    """You are "Bob," an AI legal assistant. A human lawyer has provided guidance on a user's question. Your task is to synthesize this guidance into a clear, professional response for the end-user.

- The user's original question was: "{escalated_question}"
- The lawyer's guidance is: "{lawyer_guidance}"

Incorporate the lawyer's guidance into a final answer. Refer to the provided document context if necessary to add detail or clarity.

Full Document Context:
{doc_context}
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
                "escalated_question": escalated_question,
                "lawyer_guidance": lawyer_message,
                "doc_context": doc_context,
                "history": history,
            }
        )
        final_response_content = response.content

    ai_response = AIMessage(content=final_response_content)

    return {
        "response_to_user": ai_response.content,
        "conversation_history": history + [ai_response],
        "escalated_question": None,  # Clear the state
        "prepared_briefing": None,  # Clear the state
    }
