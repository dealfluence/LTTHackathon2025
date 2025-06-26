import os
import uuid
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    Request,
    HTTPException,
    BackgroundTasks,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
import aiofiles

# Add src to path
import sys

sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from src.config.config_manager import ConfigManager
from src.storage.local_storage import LocalStorageAdapter
from src.document_sources.local_file_source import LocalFileSource
from src.core.workflow_builder import create_workflow

# Initialize FastAPI app
app = FastAPI(
    title="Legal Contract Analysis Bot",
    description="AI-powered legal contract analysis with risk assessment",
    version="1.0.0",
)

# Configuration
config = ConfigManager()

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="implementations/web/templates")

# Initialize components
storage = LocalStorageAdapter(config.get("storage.local.base_path", "./data"))
document_source = LocalFileSource()
workflow = create_workflow()

# Ensure upload directory exists
upload_dir = Path(config.get("document_processing.temp_upload_path", "./data/uploads"))
upload_dir.mkdir(parents=True, exist_ok=True)

# In-memory storage for analysis progress (in production, use Redis)
analysis_progress = {}


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    recent_analyses = await storage.list_analyses()
    recent_analyses = recent_analyses[:10]  # Show last 10

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recent_analyses": recent_analyses,
            "total_analyses": len(recent_analyses),
        },
    )


@app.post("/analyze")
async def analyze_contract(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    sharepoint_url: Optional[str] = Form(None),
):
    """Start contract analysis"""

    if not file and not sharepoint_url:
        raise HTTPException(
            status_code=400, detail="Must provide either file or SharePoint URL"
        )

    # Generate analysis ID
    analysis_id = str(uuid.uuid4())

    # Initialize progress tracking
    analysis_progress[analysis_id] = {
        "status": "starting",
        "progress": 0,
        "current_step": "Initializing",
        "started_at": datetime.now().isoformat(),
    }

    if file:
        # Handle file upload
        file_path = upload_dir / f"{analysis_id}_{file.filename}"
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Start background analysis
        background_tasks.add_task(run_analysis, analysis_id, str(file_path), "file")
    else:
        # Handle SharePoint URL (simplified - just return error for now)
        raise HTTPException(
            status_code=501, detail="SharePoint URL processing not implemented yet"
        )

    return JSONResponse(
        {
            "analysis_id": analysis_id,
            "status": "started",
            "message": "Analysis started successfully",
        }
    )


async def run_analysis(analysis_id: str, source_path: str, source_type: str):
    """Run the contract analysis workflow"""
    try:
        # Update progress
        analysis_progress[analysis_id].update(
            {"status": "processing", "progress": 10, "current_step": "Loading document"}
        )

        # Load document
        document_data = await document_source.load_document(source_path)

        # Update progress
        analysis_progress[analysis_id].update(
            {"progress": 30, "current_step": "Extracting clauses"}
        )

        # Prepare initial state
        initial_state = {
            "document_content": document_data["content"],
            "document_metadata": document_data["metadata"],
            "analysis_id": analysis_id,
            "review_required": False,
            "analysis_complete": False,
            "current_step": "starting",
        }

        # Run workflow
        result = await asyncio.to_thread(workflow.invoke, initial_state)

        # Update progress
        analysis_progress[analysis_id].update(
            {"progress": 90, "current_step": "Saving results"}
        )

        # Save results
        analysis_data = {
            "analysis_id": analysis_id,
            "document_metadata": document_data["metadata"],
            "extracted_clauses": result.get("extracted_clauses"),
            "risk_assessment": result.get("risk_assessment"),
            "summary": result.get("summary"),
            "review_required": result.get("review_required", False),
            "analysis_complete": result.get("analysis_complete", True),
            "created_at": datetime.now().isoformat(),
            "source_type": source_type,
            "source_path": (
                source_path
                if source_type == "sharepoint"
                else document_data["filename"]
            ),
        }

        await storage.save_analysis(analysis_id, analysis_data)

        # Final progress update
        analysis_progress[analysis_id].update(
            {
                "status": "completed",
                "progress": 100,
                "current_step": "Complete",
                "completed_at": datetime.now().isoformat(),
            }
        )

        # Clean up uploaded file
        if source_type == "file" and Path(source_path).exists():
            Path(source_path).unlink()

    except Exception as e:
        analysis_progress[analysis_id].update(
            {"status": "error", "error": str(e), "current_step": "Error occurred"}
        )


@app.get("/analysis/{analysis_id}")
async def get_analysis(request: Request, analysis_id: str):
    """View specific analysis results"""
    analysis = await storage.get_analysis(analysis_id)

    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return templates.TemplateResponse(
        "analysis_result.html", {"request": request, "analysis": analysis}
    )


@app.get("/api/status/{analysis_id}")
async def get_analysis_status(analysis_id: str):
    """Get analysis progress status"""
    if analysis_id not in analysis_progress:
        # Check if analysis exists in storage
        analysis = await storage.get_analysis(analysis_id)
        if analysis:
            return JSONResponse(
                {"status": "completed", "progress": 100, "current_step": "Complete"}
            )
        else:
            raise HTTPException(status_code=404, detail="Analysis not found")

    return JSONResponse(analysis_progress[analysis_id])


@app.get("/analyses")
async def list_analyses(request: Request, risk_level: Optional[str] = None):
    """List all analyses with optional filtering"""
    filters = {}
    if risk_level:
        filters["risk_level"] = risk_level

    analyses = await storage.list_analyses(filters)

    return templates.TemplateResponse(
        "analyses_list.html",
        {"request": request, "analyses": analyses, "current_filter": risk_level},
    )


@app.delete("/api/analysis/{analysis_id}")
async def delete_analysis(analysis_id: str):
    """Delete an analysis"""
    success = await storage.delete_analysis(analysis_id)

    if not success:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return JSONResponse({"message": "Analysis deleted successfully"})


@app.get("/config")
async def config_page(request: Request):
    """Configuration page"""
    return templates.TemplateResponse(
        "config.html", {"request": request, "config": config._config}
    )


if __name__ == "__main__":
    import uvicorn

    web_config = config.get_web_config()
    uvicorn.run(
        app,
        host=web_config.get("host", "0.0.0.0"),
        port=web_config.get("port", 8000),
        reload=web_config.get("reload", True),
    )
