#!/usr/bin/env python3
"""
Legal Contract Analysis Bot - Web Interface
Entry point for running the web application
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set environment variables for development
os.environ.setdefault("PYTHONPATH", str(src_path))

if __name__ == "__main__":
    import uvicorn
    from src.config.config_manager import ConfigManager

    # Load configuration
    config = ConfigManager()
    web_config = config.get_web_config()

    print("🚀 Starting Legal Contract Analysis Bot Web Interface...")
    print(f"📁 Configuration loaded from: config/config.yaml")
    print(
        f"🌐 Server will start at: http://{web_config.get('host', '0.0.0.0')}:{web_config.get('port', 8000)}"
    )
    # Run the FastAPI application
    uvicorn.run(
        "implementations.web.main:app",
        host=web_config.get("host", "0.0.0.0"),
        port=web_config.get("port", 8000),
        reload=web_config.get("reload", True),
        log_level="info",
    )
