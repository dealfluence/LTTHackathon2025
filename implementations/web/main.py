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

    # === DEBUG: Check environment variables ===
    print("=== ENVIRONMENT DEBUG ===")
    google_api_key = os.getenv("GOOGLE_API_KEY")
    print(f"GOOGLE_API_KEY exists: {'GOOGLE_API_KEY' in os.environ}")
    print(
        f"GOOGLE_API_KEY value: {google_api_key[:10] + '...' if google_api_key else 'None'}"
    )
    print(f"GOOGLE_API_KEY length: {len(google_api_key) if google_api_key else 0}")
    print(f"Railway environment: {os.getenv('RAILWAY_ENVIRONMENT_NAME', 'not set')}")
    print(
        f"All env vars with 'GOOGLE' or 'API': {[k for k in os.environ.keys() if 'GOOGLE' in k.upper() or 'API' in k.upper()]}"
    )
    print("========================")

    # === VALIDATE API KEY ===
    if not google_api_key:
        print("❌ ERROR: GOOGLE_API_KEY environment variable not found!")
        print("Available environment variables:")
        for key in sorted(os.environ.keys()):
            print(f"  {key}")
        raise ValueError("GOOGLE_API_KEY must be set in environment variables")

    if google_api_key in [
        "your_google_api_key_here",
        "your_actual_google_api_key_here",
    ]:
        print("❌ ERROR: GOOGLE_API_KEY is still set to placeholder value!")
        raise ValueError(
            "Please set a real Google API key in GOOGLE_API_KEY environment variable"
        )

    if len(google_api_key) < 30:  # Google API keys are typically longer
        print("⚠️ WARNING: GOOGLE_API_KEY seems too short, might be invalid")

    print(
        f"✅ Google API key found and validated (length: {len(google_api_key)} chars)"
    )

    # === INITIALIZE CONFIGURATION ===
    config_manager = ConfigManager()
    llm_config = config_manager.get_llm_config()
    doc_config = config_manager.get_document_config()

    # === LOAD DOCUMENTS ===
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
    else:
        print(f"⚠️ Knowledge base path does not exist: {knowledge_base_path}")

    escalation_rules_path = Path(doc_config.get("escalation_rules_file"))
    escalation_rules = ""
    if escalation_rules_path.exists():
        print(f"Loading escalation rules from: {escalation_rules_path.name}")
        escalation_rules = escalation_rules_path.read_text()
    else:
        print(f"⚠️ Escalation rules file does not exist: {escalation_rules_path}")

    # === INITIALIZE GOOGLE AI ===
    try:
        print(f"Initializing Google AI with model: {llm_config.get('model')}")
        print(f"Temperature: {llm_config.get('temperature')}")

        # Force the API key to be explicitly set
        os.environ["GOOGLE_API_KEY"] = google_api_key

        llm = ChatGoogleGenerativeAI(
            model=llm_config.get("model"),
            google_api_key=google_api_key,  # Explicitly pass the key
            temperature=llm_config.get("temperature"),
            thinking_budget=0,
        )

        print("✅ ChatGoogleGenerativeAI initialized successfully")

        # Test the LLM with a simple call
        try:
            test_response = llm.invoke("Hello")
            print("✅ Google AI test call successful")
        except Exception as test_error:
            print(f"⚠️ Google AI test call failed: {test_error}")
            # Don't fail startup, but log the issue

    except Exception as e:
        print(f"❌ ERROR initializing Google AI: {e}")
        print(f"Error type: {type(e).__name__}")
        print(f"Model: {llm_config.get('model')}")
        print(f"Temperature: {llm_config.get('temperature')}")
        print(
            f"API key first 10 chars: {google_api_key[:10] if google_api_key else 'None'}"
        )
        raise

    # === CREATE GRAPH ===
    try:
        app.state.graph = create_conversational_graph(
            llm, full_doc_context, escalation_rules
        )
        print("✅ Application dependencies initialized and graph compiled.")
    except Exception as e:
        print(f"❌ ERROR creating conversational graph: {e}")
        raise


# Mount static files
static_path = Path(__file__).resolve().parents[2] / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Setup templates
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/")
async def get_chat_page(request: Request):
    """Serves the main chat page."""
    return templates.TemplateResponse("chat.html", {"request": request})


async def send_status_update(websocket: WebSocket, status: str):
    """Send status update to client"""
    await websocket.send_json({"type": "status_update", "status": status})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "conversation_history": [],
        "escalated_question": None,
        "prepared_briefing": None,
        "lawyer_feedback_type": None,
        "lawyer_suggestions": None,
    }

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
                    "websocket": websocket,  # Pass websocket for status updates
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
                    "websocket": websocket,
                }

                try:
                    final_state = graph.invoke(current_state)

                    # Update session state from final_state (the nodes will clear what they need to)
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
                except Exception as e:
                    print(f"Error processing lawyer message: {e}")
                    print(f"Current state: {current_state}")
                    await websocket.send_json(
                        {
                            "type": "error",
                            "content": f"An error occurred processing the lawyer's response: {str(e)}",
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
