"""
SEC Analyzer - A comprehensive tool for downloading and cleaning SEC documents for AI ingestion.
"""

__version__ = "0.1.0"
__author__ = "SEC Analyzer Team"

from .analyzer import SECAnalyzer
from .models import Filing, ParsedDocument, AnalyzerConfig, AnalysisResult

__all__ = [
    "SECAnalyzer",
    "Filing", 
    "ParsedDocument",
    "AnalyzerConfig",
    "AnalysisResult",
]
