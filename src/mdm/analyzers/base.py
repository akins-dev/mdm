from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..models.beam import Span

class BeamAnalyzer(ABC):
    @abstractmethod
    def analyze(self, spans: List[Span], supports: List[str], fixed_supports: List[str], **kwargs) -> Dict[str, Any]:
        """
        Analyze the beam and return a standardized dictionary containing:
        - status: str (message for the UI)
        - tabs: dict of {tab_id: label} for the UI
        - tables: dict of table data mapped by tab_id
        """
        pass
