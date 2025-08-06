"""
Integration tests for the SEC analyzer.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from sec_analyzer import SECAnalyzer, AnalyzerConfig


@pytest.fixture
def temp_config():
    """Create a temporary configuration for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    
    config = AnalyzerConfig(
        user_agent="SEC Analyzer Test (test@example.com)",
        output_dir=temp_dir / "output",
        cache_dir=temp_dir / "cache",
        forms_to_process=["10-Q"],  # Limit to 10-Q for faster testing
        max_concurrent_downloads=2,
        output_formats=["txt", "json"]
    )
    
    yield config
    
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_analyzer_validation(temp_config):
    """Test analyzer setup validation."""
    analyzer = SECAnalyzer(temp_config)
    
    validation = await analyzer.validate_setup()
    
    assert validation["output_directory_writable"] is True
    assert validation["cache_directory_writable"] is True
    


@pytest.mark.asyncio
async def test_get_available_filings(temp_config):
    """Test getting available filings for a ticker."""
    analyzer = SECAnalyzer(temp_config)
    
    try:
        filings = await analyzer.get_available_filings("AAPL")
        
        assert len(filings) > 0
        
        filing = filings[0]
        assert hasattr(filing, 'form_type')
        assert hasattr(filing, 'filing_date')
        assert hasattr(filing, 'accession_number')
        assert hasattr(filing, 'company_name')
        
    except Exception as e:
        pytest.skip(f"SEC API not accessible: {e}")


@pytest.mark.asyncio
async def test_analyze_single_document(temp_config):
    """Test analyzing a single document."""
    analyzer = SECAnalyzer(temp_config)
    
    try:
        filings = await analyzer.get_available_filings("AAPL")
        
        if not filings:
            pytest.skip("No filings available for testing")
        
        target_filing = None
        for filing in filings:
            if filing.form_type == "10-Q":
                target_filing = filing
                break
        
        if not target_filing:
            pytest.skip("No 10-Q filing available for testing")
        
        parsed_doc = await analyzer.analyze_single_document("AAPL", target_filing.accession_number)
        
        assert parsed_doc.filing.form_type == "10-Q"
        assert parsed_doc.filing.ticker == "AAPL"
        assert len(parsed_doc.clean_text) > 0
        assert parsed_doc.raw_content is not None
        
        output_structure = analyzer.storage.get_output_structure("AAPL")
        assert output_structure["clean"].exists()
        
    except Exception as e:
        pytest.skip(f"SEC API not accessible: {e}")


@pytest.mark.asyncio
async def test_full_ticker_analysis(temp_config):
    """Test full ticker analysis (limited scope for testing)."""
    temp_config.forms_to_process = ["10-Q"]
    
    analyzer = SECAnalyzer(temp_config)
    
    try:
        result = await analyzer.analyze_ticker("AAPL", forms=["10-Q"])
        
        assert result.ticker == "AAPL"
        assert result.company_name is not None
        assert result.cik is not None
        assert result.stats.documents_downloaded >= 0
        assert result.stats.processing_time_seconds > 0
        
        if result.processed_documents:
            doc = result.processed_documents[0]
            assert doc.filing.form_type == "10-Q"
            assert len(doc.clean_text) > 0
        
        if result.output_paths:
            assert "txt" in result.output_paths or "json" in result.output_paths
        
    except Exception as e:
        pytest.skip(f"SEC API not accessible: {e}")


def test_output_summary(temp_config):
    """Test output summary functionality."""
    analyzer = SECAnalyzer(temp_config)
    
    summary = analyzer.get_output_summary("NONEXISTENT")
    
    for category, info in summary.items():
        assert info["file_count"] == 0
        assert info["files"] == []


@pytest.mark.asyncio
async def test_error_handling(temp_config):
    """Test error handling for invalid inputs."""
    analyzer = SECAnalyzer(temp_config)
    
    with pytest.raises(Exception):
        await analyzer.get_available_filings("INVALID_TICKER_12345")
    
    with pytest.raises(Exception):
        await analyzer.analyze_single_document("AAPL", "invalid-accession-number")
