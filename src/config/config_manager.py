import yaml
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv


class ConfigManager:
    def __init__(self, config_path: str = "config/config.yaml"):
        load_dotenv()
        self.config_path = Path(config_path)
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

        with open(self.config_path, "r") as file:
            config = yaml.safe_load(file)

        # Override with environment variables
        if os.getenv("ANTHROPIC_API_KEY"):
            config.setdefault("llm", {})["api_key"] = os.getenv("ANTHROPIC_API_KEY")

        return config

    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_web_config(self) -> Dict[str, Any]:
        return self.get("interface.web", {})

    def get_storage_config(self) -> Dict[str, Any]:
        return self.get("storage", {})

    def get_llm_config(self) -> Dict[str, Any]:
        return self.get("llm", {})

    def get_document_config(self) -> Dict[str, Any]:
        return self.get("document_processing", {})

    def get_risk_config(self) -> Dict[str, Any]:
        return self.get("risk_assessment", {})
