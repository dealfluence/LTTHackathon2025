import asyncio
import os
import uuid
from pathlib import Path
import sys

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from langchain_core.messages import AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Adjust sys.path to include the src directory
src_path = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(src_path))

from config.config_manager import ConfigManager
from core.graph_builder import create_conversational_graph
from document_sources.local_file_source import LocalFileSource

# --- Application Setup ---
app = FastAPI()

# In-memory session management
sessions = {}


@app.on_event("startup")
async def startup_event():
    """
    Initializes and loads all application dependencies asynchronously
    when the application starts.
    """
    print("Initializing application dependencies...")
    config_manager = ConfigManager()
    llm_config = config_manager.get_llm_config()
    doc_config = config_manager.get_document_config()

    # Load context from files
    doc_source = LocalFileSource()
    knowledge_base_path = Path(doc_config.get("knowledge_base_path"))

    full_doc_context = ""
    if knowledge_base_path.exists():
        for file_path in knowledge_base_path.glob("*"):
            if doc_source.validate_source(str(file_path)):
                print(f"Loading document: {file_path.name}")
                # Correctly await the async function
                doc_data = await doc_source.load_document(str(file_path))
                full_doc_context += (
                    f"\n\n--- Document: {file_path.name} ---\n\n{doc_data['content']}"
                )

    escalation_rules_path = Path(doc_config.get("escalation_rules_file"))
    escalation_rules = ""
    if escalation_rules_path.exists():
        print(f"Loading escalation rules from: {escalation_rules_path.name}")
        escalation_rules = escalation_rules_path.read_text()

    llm = ChatGoogleGenerativeAI(
        model=llm_config.get("model"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=llm_config.get("temperature"),
    )

    # Store the compiled graph in the app's state for global access
    app.state.graph = create_conversational_graph(
        llm, full_doc_context, escalation_rules
    )
    print("Application dependencies initialized and graph compiled.")


# Mount static files
static_path = Path(__file__).resolve().parents[2] / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
async def get_chat_page(request: Request):
    """Serves the main chat page."""
    return templates.TemplateResponse("chat.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "conversation_history": [],
        "escalated_question": None,
        "prepared_briefing": None,
    }

    # Send initial greeting
    await websocket.send_json(
        {
            "type": "user_response",
            "content": "Hi! I'm Bob. How can I help you today?",
        }
    )

    try:
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            content = data.get("content")

            # Get the graph from the application state
            graph = websocket.app.state.graph

            if message_type == "user_message":
                current_state = {
                    "user_message": content,
                    "lawyer_message": None,
                    "conversation_history": sessions[session_id][
                        "conversation_history"
                    ],
                    "escalated_question": sessions[session_id].get(
                        "escalated_question"
                    ),
                    "prepared_briefing": sessions[session_id].get("prepared_briefing"),
                }

                final_state = graph.invoke(current_state)

                sessions[session_id]["conversation_history"] = final_state[
                    "conversation_history"
                ]
                sessions[session_id]["escalated_question"] = final_state.get(
                    "escalated_question"
                )
                sessions[session_id]["prepared_briefing"] = final_state.get(
                    "prepared_briefing"
                )

                await websocket.send_json(
                    {
                        "type": "user_response",
                        "content": final_state["response_to_user"],
                    }
                )

                if final_state.get("message_to_lawyer"):
                    await websocket.send_json(
                        {
                            "type": "lawyer_request",
                            "content": final_state["message_to_lawyer"],
                        }
                    )

            elif message_type == "lawyer_message":
                current_state = {
                    "user_message": None,
                    "lawyer_message": content,
                    "conversation_history": sessions[session_id][
                        "conversation_history"
                    ],
                    "escalated_question": sessions[session_id].get(
                        "escalated_question"
                    ),
                    "prepared_briefing": sessions[session_id].get("prepared_briefing"),
                }

                final_state = graph.invoke(current_state)

                sessions[session_id]["conversation_history"] = final_state[
                    "conversation_history"
                ]
                sessions[session_id]["escalated_question"] = None
                sessions[session_id]["prepared_briefing"] = None

                await websocket.send_json(
                    {
                        "type": "user_response",
                        "content": final_state["response_to_user"],
                    }
                )

    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected")
        if session_id in sessions:
            del sessions[session_id]
    except Exception as e:
        print(f"An error occurred with client {session_id}: {e}")
        await websocket.send_json(
            {"type": "error", "content": f"An unexpected error occurred: {str(e)}"}
        )
        if session_id in sessions:
            del sessions[session_id]
