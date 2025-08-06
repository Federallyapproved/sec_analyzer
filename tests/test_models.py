"""
Tests for data models.
"""

import pytest
from datetime import datetime
from pathlib import Path

from sec_analyzer.models import (
    Filing, ParsedDocument, AnalyzerConfig, AnalysisResult,
    ProcessingStats, DocumentSection, FinancialTable, CleaningOptions
)


def test_filing_model():
    """Test Filing model creation and validation."""
    filing = Filing(
        form_type="10-Q",
        filing_date=datetime(2024, 6, 30),
        accession_number="0001713445-24-000196",
        document_url="https://www.sec.gov/Archives/edgar/data/1713445/000171344524000196/rddt-20240630.htm",
        company_name="Reddit, Inc.",
        cik="0001713445",
        ticker="RDDT"
    )
    
    assert filing.form_type == "10-Q"
    assert filing.ticker == "RDDT"
    assert filing.company_name == "Reddit, Inc."


def test_analyzer_config():
    """Test AnalyzerConfig with default values."""
    config = AnalyzerConfig(
        user_agent="Test Agent (test@example.com)"
    )
    
    assert config.user_agent == "Test Agent (test@example.com)"
    assert config.output_dir == Path("output")
    assert config.cache_dir == Path("cache")
    assert "10-K" in config.forms_to_process
    assert config.max_concurrent_downloads == 5
    assert config.save_raw_documents is True


def test_document_section():
    """Test DocumentSection model."""
    section = DocumentSection(
        title="Business Overview",
        content="Reddit is a social media platform...",
        level=2,
        order=1
    )
    
    assert section.title == "Business Overview"
    assert section.level == 2
    assert section.order == 1


def test_financial_table():
    """Test FinancialTable model."""
    table = FinancialTable(
        title="Consolidated Balance Sheets",
        headers=["", "June 30, 2024", "December 31, 2023"],
        rows=[
            ["Total Assets", "$1,000,000", "$900,000"],
            ["Total Liabilities", "$500,000", "$450,000"]
        ]
    )
    
    assert table.title == "Consolidated Balance Sheets"
    assert len(table.headers) == 3
    assert len(table.rows) == 2


def test_processing_stats():
    """Test ProcessingStats model."""
    stats = ProcessingStats(
        documents_downloaded=5,
        documents_processed=4,
        documents_failed=1,
        total_text_length=100000,
        processing_time_seconds=45.5,
        forms_processed={"10-Q": 2, "8-K": 2}
    )
    
    assert stats.documents_downloaded == 5
    assert stats.documents_processed == 4
    assert stats.documents_failed == 1
    assert stats.forms_processed["10-Q"] == 2


def test_cleaning_options():
    """Test CleaningOptions with defaults."""
    options = CleaningOptions()
    
    assert options.remove_html_tags is True
    assert options.remove_xbrl_tags is True
    assert options.preserve_tables is True
    assert options.min_section_length == 50


def test_parsed_document():
    """Test ParsedDocument model."""
    filing = Filing(
        form_type="10-Q",
        filing_date=datetime(2024, 6, 30),
        accession_number="0001713445-24-000196",
        document_url="https://example.com/doc.htm",
        company_name="Test Company",
        cik="0001234567",
        ticker="TEST"
    )
    
    section = DocumentSection(
        title="Test Section",
        content="Test content",
        level=1,
        order=0
    )
    
    parsed_doc = ParsedDocument(
        filing=filing,
        raw_content="<html>Raw content</html>",
        clean_text="Clean text content",
        sections=[section],
        metadata={"test": "value"}
    )
    
    assert parsed_doc.filing.ticker == "TEST"
    assert parsed_doc.clean_text == "Clean text content"
    assert len(parsed_doc.sections) == 1
    assert parsed_doc.metadata["test"] == "value"
    assert isinstance(parsed_doc.processing_timestamp, datetime)
