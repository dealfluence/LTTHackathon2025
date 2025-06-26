from abc import ABC, abstractmethod
from typing import Dict, Any, List


class DocumentSource(ABC):

    @abstractmethod
    async def load_document(self, source_path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def validate_source(self, source_path: str) -> bool:
        pass

    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        pass
