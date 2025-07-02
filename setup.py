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
        "data/knowledge_base",
        "logs",
        "static/css",
        "static/js",
        "implementations/web/templates",
    ]

    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
        print(f"✅ Created directory: {directory}")


def create_knowledge_base_readme():
    """Create README for knowledge base directory"""
    knowledge_base_path = Path("data/knowledge_base")
    readme_path = knowledge_base_path / "README.md"

    if not readme_path.exists():
        readme_content = """# Knowledge Base

This directory contains the legal documents and contracts that the AI will use to answer questions.

## Supported File Types
- `.txt` files
- `.md` files
- Other text-based formats

## Adding Documents
1. Place your contract files in this directory
2. The AI will automatically load them on startup
3. Files should contain plain text or markdown

## Example Files
Add your contract files here, such as:
- `hosting_agreement.txt`
- `distribution_agreement.md`
- `escalation_rules.txt`

## Important Notes
- These files will be included in git and deployed to production
- Do not include sensitive information that shouldn't be in version control
- Files are loaded at application startup
"""

        with open(readme_path, "w") as f:
            f.write(readme_content)
        print("✅ Created knowledge base README")


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

# Data and uploads (but keep knowledge_base)
data/analyses/
data/uploads/
logs/
*.log

# Allow knowledge_base to be tracked
!data/knowledge_base/
!data/knowledge_base/**

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
    create_knowledge_base_readme()
    create_env_file()
    create_gitignore()

    print("\n🎉 Setup complete!")
    print("\n📋 Next steps:")
    print("1. Add your contract/legal documents to data/knowledge_base/")
    print("2. Update .env file with your GOOGLE_API_KEY")
    print("3. Install dependencies: pip install -r requirements/web.txt")
    print("4. Run the application: python run_web.py")
    print("5. Open http://localhost:8000 in your browser")

    print("\n📄 Knowledge Base:")
    print("   - Add your legal documents to data/knowledge_base/")
    print("   - Supported formats: .txt, .md")
    print("   - Files will be included in git and deployed to Railway")


if __name__ == "__main__":
    main()
