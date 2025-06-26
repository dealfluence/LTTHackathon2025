from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class StorageAdapter(ABC):

    @abstractmethod
    async def save_analysis(self, analysis_id: str, data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    async def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def list_analyses(
        self, filters: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def delete_analysis(self, analysis_id: str) -> bool:
        pass
