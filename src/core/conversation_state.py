from typing import List, Optional
from fastapi import WebSocket
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage


class ConversationState(TypedDict):
    """
    Represents the state of a single conversation session.
    """

    # The history of messages for this session.
    conversation_history: List[BaseMessage]

    # Input for the current turn from either user or lawyer
    user_message: Optional[str]
    lawyer_message: Optional[str]

    # Output generated during the current turn
    response_to_user: str
    message_to_lawyer: Optional[str]

    # The original question that was escalated to the lawyer
    # This provides context when the lawyer responds.
    escalated_question: Optional[str]
    prepared_briefing: Optional[str]

    # WebSocket connection for sending status updates
    websocket: Optional[WebSocket]
