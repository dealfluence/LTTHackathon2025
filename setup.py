#!/usr/bin/env python3
"""
Setup script for Legal Contract Analysis Bot
Creates necessary directories and initial configuration
"""

import os
import json
from pathlib import Path


def create_directories():
    """Create necessary directories"""
    directories = [
        "data",
        "data/analyses",
        "data/uploads",
        "logs",
        "static/css",
        "static/js",
        "implementations/web/templates",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_env_file():
    """Create .env file if it doesn't exist"""
    env_file = Path(".env")
    if not env_file.exists():
        env_content = """# Legal Contract Analysis Bot Environment Variables
GOOGLE_API_KEY=your_google_api_key_here
LOG_LEVEL=INFO
"""
        with open(env_file, "w") as f:
            f.write(env_content)
        print("✅ Created .env file (please update with your API keys)")
    else:
        print("⚠️  .env file already exists")


def create_gitignore():
    """Create .gitignore file"""
    gitignore_content = """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Environment variables
.env

# Data and uploads
data/
logs/
*.log

# Virtual environment
venv/
env/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.temp
"""

    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("✅ Created .gitignore file")


def main():
    """Main setup function"""
    print("🔧 Setting up Legal Contract Analysis Bot...")

    create_directories()
    create_env_file()
    create_gitignore()

    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Update .env file with your GOOGLE_API_KEY=your_google_api_key_here")
    print("2. Install dependencies: pip install -r requirements/web.txt")
    print("3. Run the application: python run_web.py")
    print("4. Open http://localhost:8000 in your browser")


if __name__ == "__main__":
    main()
