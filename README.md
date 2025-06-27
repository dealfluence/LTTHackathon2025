# Legal Contract Analysis Bot

AI-powered legal contract analysis with risk assessment, conversational Q&A, and plain-English summaries. This project provides an intelligent assistant to help legal professionals and business stakeholders quickly understand complex contracts.

## Features

- 🔍 **Conversational Q&A**: Ask questions about the contract in natural language.
- ⚠️ **Intelligent Escalation**: Automatically detects questions requiring human lawyer review and prepares a concise briefing.
- 📋 **Plain-English Summaries**: Generates business-friendly contract overviews.
- 🌐 **Web Interface**: Easy-to-use browser-based UI for analysis and chat.
- 💾 **Local Storage**: Securely persists analysis results and conversations locally.

## Prerequisites

Before you begin, ensure you have the following installed on your system:
- [Python](https://www.python.org/downloads/) (Version 3.12 or higher)
- [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
- `pip` (Python package installer)

## Installation & Setup

Follow these steps to get the application running on your local machine.

### 1. Clone the Repository
Open your terminal and clone the project repository:
```bash
git clone <repository-url>
cd legal-contract-bot
```

### 2. Run the Setup Script
The project includes a setup script to create necessary directories and configuration files.
```bash
python setup.py
```
This will create data directories, a .gitignore file, and a .env file for your API keys.

### 3. Configure Environment Variables
The setup script creates a file named .env in the project's root directory. You must edit this file to add your API key.
Open the .env file and replace your_google_api_key_here with your actual Google AI API key.

### 4. Install Dependencies

Install the required Python packages using the provided requirements file:
```bash
pip install -r requirements/web.txt
```
## Usage

Once the setup is complete and dependencies are installed, you can run the web application.

### 1. Start the Web Server

From the root directory of the project, run:

```bash
python run_web.py
```

You should see output indicating the server has started, typically on http://localhost:8000.

### 2. Access the Application

Open your web browser and navigate to http://localhost:8000.

# Legal Bot LangGraph State Machine - Detailed Explanation

## Overview
This LangGraph implementation creates a sophisticated conversational AI system that can handle legal queries, intelligently route complex questions to human lawyers, and enhance responses with contextual information from legal documents.

## State Structure (`ConversationState`)

The state maintains the following information throughout the conversation flow:

- **conversation_history**: List of all messages (HumanMessage/AIMessage objects)
- **user_message**: Current user query (when user initiates)
- **lawyer_message**: Lawyer's response (when lawyer responds)
- **response_to_user**: Final response to send to the user
- **message_to_lawyer**: Briefing sent to lawyer for escalated queries
- **escalated_question**: Original question that was escalated (provides context)
- **prepared_briefing**: The briefing prepared for the lawyer
- **websocket**: WebSocket connection for real-time status updates
- **base_response**: Response before contextual enhancement

## Node Descriptions

### 1. **Router Node** (`escalation_router_node`)
- **Purpose**: Analyzes incoming user queries to determine if they can be answered by AI or need lawyer escalation
- **Decision Logic**: Uses structured output (Pydantic model) to make binary decision
- **Status Updates**: Sends "escalation" or "direct_response" via WebSocket
- **Output**: Sets `decision` field to either "answer_directly" or "escalate_to_lawyer"

### 2. **Generate Direct Answer Node** (`generate_direct_answer_node`)
- **Purpose**: Creates concise, factual responses using contract information
- **Style**: 1-2 sentences, direct facts, includes clause references
- **Example Output**: "Yes, you can terminate with 30-day written notice (Section 5.2)."
- **Updates**: Adds user message and AI response to conversation history

### 3. **Generate Lawyer Briefing Node** (`generate_lawyer_briefing_node`)
- **Purpose**: Prepares concise briefing for lawyer review when escalation is needed
- **Format**: 
  - User asks: [brief restatement]
  - Contract says: [key fact + clause]
  - Proposed answer: [1 sentence]
  - Any concerns?
- **User Response**: "Checking with legal counsel on this one."
- **Stores**: Briefing, escalated question, and prepared response for later use

### 4. **Handle Lawyer Response Node** (`handle_lawyer_response_node`)
- **Purpose**: Processes lawyer's feedback on escalated queries
- **Two Modes**:
  1. **Approval Mode**: If lawyer approves (keywords: "approve", "yes", etc.), extracts proposed answer from briefing
  2. **Correction Mode**: If lawyer provides corrections, reformats their guidance naturally
- **Output**: Sets base_response for contextual enhancement

### 5. **Contextual Enhancement Node** (`contextual_enhancement_node`)
- **Purpose**: Analyzes base responses and potentially adds important related details
- **Enhancement Rules**:
  - Only adds genuinely important, actionable information
  - Focuses on deadlines, penalties, or connected obligations
  - Keeps additions to one short sentence maximum
  - Returns "NO_ENHANCEMENT_NEEDED" if nothing relevant
- **Error Handling**: Falls back to base response if enhancement fails
- **Status Update**: Sends "contextual_analysis" via WebSocket

## Flow Logic

### Entry Point Decision (`get_entry_point`)
```python
if state.get("lawyer_message"):
    return "handle_lawyer_response"
return "router"
```
- Determines whether the conversation is initiated by a user or continuing from a lawyer's response

### Escalation Decision (`should_escalate`)
```python
return "generate_briefing" if state.get("decision") == "escalate_to_lawyer" else "answer"
```
- Routes based on the router node's decision

## Complete Flow Paths

### Path 1: Direct Answer Flow
1. User message → Router → Direct Answer → Contextual Enhancement → End
2. Used for straightforward queries that can be answered from contract information

### Path 2: Lawyer Escalation Flow
1. User message → Router → Generate Briefing → End
2. Sends briefing to lawyer and tells user "Checking with legal counsel"
3. Conversation pauses for lawyer input

### Path 3: Lawyer Response Flow
1. Lawyer message → Handle Lawyer Response → Contextual Enhancement → End
2. Processes lawyer's feedback and delivers final answer to user

## Key Design Decisions

1. **Contextual Enhancement for All Responses**: Both direct answers and lawyer-approved responses go through enhancement to ensure users get comprehensive information

2. **Briefing Bypass**: Briefings sent to lawyers skip contextual enhancement as they're already comprehensive

3. **State Cleanup**: After contextual enhancement, temporary state fields (base_response, escalated_question, prepared_briefing) are cleared

4. **WebSocket Integration**: Real-time status updates keep users informed about processing stages

5. **Error Resilience**: Each node has error handling to gracefully fall back to safe responses

## Configuration Dependencies

The graph requires:
- **LLM**: ChatGoogleGenerativeAI instance for all language processing
- **doc_context**: Contract/document content for answering queries
- **escalation_rules**: Rules defining when to escalate to human lawyers

This architecture creates a robust, user-friendly legal assistant that knows its limitations and seamlessly involves human expertise when needed.
