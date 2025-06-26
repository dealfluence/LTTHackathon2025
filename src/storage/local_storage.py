import json
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..interfaces.storage_adapter import StorageAdapter


class LocalStorageAdapter(StorageAdapter):

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.analyses_path = self.base_path / "analyses"
        self.ensure_directories()

    def ensure_directories(self):
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.analyses_path.mkdir(parents=True, exist_ok=True)

    def _get_analysis_file_path(self, analysis_id: str) -> Path:
        return self.analyses_path / f"{analysis_id}.json"

    async def save_analysis(self, analysis_id: str, data: Dict[str, Any]) -> bool:
        try:
            data["saved_at"] = datetime.now().isoformat()
            data["analysis_id"] = analysis_id

            file_path = self._get_analysis_file_path(analysis_id)
            async with aiofiles.open(file_path, "w") as file:
                await file.write(json.dumps(data, indent=2, default=str))
            return True
        except Exception as e:
            print(f"Error saving analysis {analysis_id}: {e}")
            return False

    async def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        try:
            file_path = self._get_analysis_file_path(analysis_id)
            if not file_path.exists():
                return None

            async with aiofiles.open(file_path, "r") as file:
                content = await file.read()
                return json.loads(content)
        except Exception as e:
            print(f"Error loading analysis {analysis_id}: {e}")
            return None

    async def list_analyses(
        self, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        try:
            analyses = []
            for file_path in self.analyses_path.glob("*.json"):
                try:
                    async with aiofiles.open(file_path, "r") as file:
                        content = await file.read()
                        analysis = json.loads(content)

                        # Apply filters if provided
                        if filters:
                            if self._matches_filters(analysis, filters):
                                analyses.append(analysis)
                        else:
                            analyses.append(analysis)
                except Exception as e:
                    print(f"Error loading analysis file {file_path}: {e}")
                    continue

            # Sort by creation date, newest first
            analyses.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
            return analyses
        except Exception as e:
            print(f"Error listing analyses: {e}")
            return []

    def _matches_filters(
        self, analysis: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        for key, value in filters.items():
            if key == "risk_level":
                if analysis.get("risk_assessment", {}).get("overall_risk") != value:
                    return False
            elif key == "date_from":
                if analysis.get("saved_at", "") < value:
                    return False
            elif key == "date_to":
                if analysis.get("saved_at", "") > value:
                    return False
        return True

    async def delete_analysis(self, analysis_id: str) -> bool:
        try:
            file_path = self._get_analysis_file_path(analysis_id)
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"Error deleting analysis {analysis_id}: {e}")
            return False
