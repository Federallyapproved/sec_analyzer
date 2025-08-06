"""
Data models for SEC document processing.
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, ConfigDict


class FormType(str, Enum):
    """Supported SEC form types."""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q" 
    FORM_8K = "8-K"
    FORM_DEF14A = "DEF 14A"
    FORM_S1 = "S-1"
    FORM_S3 = "S-3"


class Filing(BaseModel):
    """Represents a single SEC filing."""
    model_config = ConfigDict(frozen=True)
    
    form_type: str = Field(..., description="Type of SEC form (e.g., 10-K, 10-Q)")
    filing_date: datetime = Field(..., description="Date the filing was submitted")
    accession_number: str = Field(..., description="Unique SEC accession number")
    document_url: str = Field(..., description="URL to the document")
    company_name: str = Field(..., description="Name of the filing company")
    cik: str = Field(..., description="Central Index Key")
    ticker: Optional[str] = Field(None, description="Stock ticker symbol")
    file_size: Optional[int] = Field(None, description="Document size in bytes")


class DocumentSection(BaseModel):
    """Represents a section within a document."""
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Section content")
    level: int = Field(..., description="Heading level (1-6)")
    order: int = Field(..., description="Order within document")


class FinancialTable(BaseModel):
    """Represents a financial table extracted from a document."""
    title: str = Field(..., description="Table title")
    headers: List[str] = Field(..., description="Column headers")
    rows: List[List[str]] = Field(..., description="Table data rows")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional table metadata")


class ParsedDocument(BaseModel):
    """Represents a parsed and processed SEC document."""
    filing: Filing = Field(..., description="Original filing information")
    raw_content: str = Field(..., description="Raw HTML/XML content")
    clean_text: str = Field(..., description="Cleaned text for AI ingestion")
    sections: List[DocumentSection] = Field(default_factory=list, description="Document sections")
    tables: List[FinancialTable] = Field(default_factory=list, description="Extracted financial tables")
    structured_data: Dict[str, Any] = Field(default_factory=dict, description="Structured financial data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Processing metadata")
    processing_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When document was processed")


class AnalyzerConfig(BaseModel):
    """Configuration for the SEC analyzer."""
    user_agent: str = Field(..., description="User agent for SEC API requests")
    output_dir: Path = Field(default=Path("output"), description="Output directory for processed documents")
    cache_dir: Path = Field(default=Path("cache"), description="Cache directory for downloaded documents")
    forms_to_process: List[str] = Field(
        default=[FormType.FORM_10K, FormType.FORM_10Q, FormType.FORM_8K],
        description="List of form types to process"
    )
    max_concurrent_downloads: int = Field(default=5, description="Maximum concurrent downloads")
    rate_limit_delay: float = Field(default=0.1, description="Delay between requests in seconds")
    save_raw_documents: bool = Field(default=True, description="Whether to save raw HTML documents")
    save_clean_text: bool = Field(default=True, description="Whether to save cleaned text")
    save_structured_data: bool = Field(default=True, description="Whether to save structured data")
    output_formats: List[str] = Field(
        default=["txt", "json", "markdown"],
        description="Output formats to generate"
    )


class ProcessingStats(BaseModel):
    """Statistics from document processing."""
    documents_downloaded: int = Field(default=0)
    documents_processed: int = Field(default=0)
    documents_failed: int = Field(default=0)
    total_text_length: int = Field(default=0)
    processing_time_seconds: float = Field(default=0.0)
    forms_processed: Dict[str, int] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Result of analyzing a ticker's SEC documents."""
    ticker: str = Field(..., description="Stock ticker analyzed")
    company_name: str = Field(..., description="Company name")
    cik: str = Field(..., description="Central Index Key")
    processed_documents: List[ParsedDocument] = Field(..., description="Successfully processed documents")
    failed_documents: List[Filing] = Field(default_factory=list, description="Documents that failed processing")
    stats: ProcessingStats = Field(..., description="Processing statistics")
    output_paths: Dict[str, List[Path]] = Field(default_factory=dict, description="Paths to generated output files")
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When analysis was completed")


class CleaningOptions(BaseModel):
    """Options for document cleaning."""
    remove_html_tags: bool = Field(default=True, description="Remove HTML tags")
    remove_xbrl_tags: bool = Field(default=True, description="Remove XBRL tags")
    preserve_tables: bool = Field(default=True, description="Preserve table structure")
    preserve_sections: bool = Field(default=True, description="Preserve section headers")
    remove_boilerplate: bool = Field(default=True, description="Remove common boilerplate text")
    normalize_whitespace: bool = Field(default=True, description="Normalize whitespace")
    extract_financial_data: bool = Field(default=True, description="Extract structured financial data")
    min_section_length: int = Field(default=50, description="Minimum section length to keep")
