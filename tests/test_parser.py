"""
Tests for document parser.
"""

import pytest
from bs4 import BeautifulSoup
from datetime import datetime

from sec_analyzer.parser import DocumentParser
from sec_analyzer.models import Filing, CleaningOptions


@pytest.fixture
def sample_filing():
    """Create a sample filing for testing."""
    return Filing(
        form_type="10-Q",
        filing_date=datetime(2024, 6, 30),
        accession_number="0001713445-24-000196",
        document_url="https://example.com/doc.htm",
        company_name="Test Company",
        cik="0001234567",
        ticker="TEST"
    )


@pytest.fixture
def sample_html():
    """Sample HTML content for testing."""
    return """
    <html>
    <head><title>Test Document</title></head>
    <body>
        <h1>Business Overview</h1>
        <p>This is the business overview section with important information.</p>
        
        <h2>Financial Results</h2>
        <p>Revenue increased significantly this quarter.</p>
        
        <table>
            <tr><th>Metric</th><th>Q2 2024</th><th>Q1 2024</th></tr>
            <tr><td>Revenue</td><td>$100M</td><td>$90M</td></tr>
            <tr><td>Net Income</td><td>$20M</td><td>$15M</td></tr>
        </table>
        
        <ix:nonfraction contextRef="c1" name="us-gaap:Revenue" unitRef="usd">100000000</ix:nonfraction>
        
        <script>console.log('test');</script>
        <style>.test { color: red; }</style>
    </body>
    </html>
    """


def test_parser_initialization():
    """Test parser initialization with default options."""
    parser = DocumentParser()
    assert parser.cleaning_options.remove_html_tags is True
    assert parser.cleaning_options.remove_xbrl_tags is True


def test_parser_with_custom_options():
    """Test parser with custom cleaning options."""
    options = CleaningOptions(
        remove_html_tags=False,
        min_section_length=100
    )
    parser = DocumentParser(options)
    assert parser.cleaning_options.remove_html_tags is False
    assert parser.cleaning_options.min_section_length == 100


def test_parse_html_document(sample_filing, sample_html):
    """Test parsing HTML document."""
    parser = DocumentParser()
    parsed_doc = parser.parse_html_document(sample_html, sample_filing)
    
    assert parsed_doc.filing == sample_filing
    assert parsed_doc.raw_content == sample_html
    assert len(parsed_doc.clean_text) > 0
    assert isinstance(parsed_doc.processing_timestamp, datetime)


def test_remove_unwanted_elements():
    """Test removal of unwanted HTML elements."""
    html = """
    <html>
    <body>
        <p>Keep this text</p>
        <script>Remove this</script>
        <style>Remove this too</style>
        <!-- Remove this comment -->
        <ix:nonfraction>XBRL data</ix:nonfraction>
    </body>
    </html>
    """
    
    parser = DocumentParser()
    soup = BeautifulSoup(html, 'lxml')
    parser._remove_unwanted_elements(soup)
    
    assert len(soup.find_all('script')) == 0
    assert len(soup.find_all('style')) == 0
    
    text = soup.get_text()
    assert 'Keep this text' in text


def test_extract_sections():
    """Test section extraction from HTML."""
    html = """
    <html>
    <body>
        <h1>Main Section</h1>
        <p>This is the main section content with enough text to meet minimum length requirements.</p>
        
        <h2>Subsection</h2>
        <p>This is subsection content with sufficient length for testing purposes.</p>
        
        <h3>Short</h3>
        <p>Too short</p>
    </body>
    </html>
    """
    
    parser = DocumentParser()
    soup = BeautifulSoup(html, 'lxml')
    sections = parser._extract_sections(soup)
    
    assert len(sections) >= 1
    assert any(section.title == "Main Section" for section in sections)


def test_extract_tables():
    """Test table extraction from HTML."""
    html = """
    <html>
    <body>
        <h2>Consolidated Balance Sheet</h2>
        <table>
            <tr><th>Assets</th><th>2024</th><th>2023</th></tr>
            <tr><td>Cash</td><td>$100M</td><td>$90M</td></tr>
            <tr><td>Total Assets</td><td>$500M</td><td>$450M</td></tr>
        </table>
        
        <table>
            <tr><td>Non-financial table</td><td>Data</td></tr>
        </table>
    </body>
    </html>
    """
    
    parser = DocumentParser()
    soup = BeautifulSoup(html, 'lxml')
    tables = parser._extract_tables(soup)
    
    assert len(tables) >= 1
    financial_table = tables[0]
    assert "Assets" in financial_table.headers[0]
    assert len(financial_table.rows) >= 2


def test_clean_text():
    """Test text cleaning functionality."""
    parser = DocumentParser()
    
    text = "This   has    excessive     whitespace\n\n\n\nand newlines"
    cleaned = parser._clean_text(text)
    assert "excessive whitespace" in cleaned
    assert "    " not in cleaned
    
    text = "Text with special chars: @#$%^&*()"
    cleaned = parser._clean_text(text)
    assert len(cleaned) > 0


def test_has_xbrl_tags():
    """Test XBRL tag detection."""
    parser = DocumentParser()
    
    html_with_xbrl = "<html><body><ix:nonfraction>100</ix:nonfraction></body></html>"
    soup_with_xbrl = BeautifulSoup(html_with_xbrl, 'lxml')
    assert parser._has_xbrl_tags(soup_with_xbrl) is True
    
    html_without_xbrl = "<html><body><p>Regular content</p></body></html>"
    soup_without_xbrl = BeautifulSoup(html_without_xbrl, 'lxml')
    assert parser._has_xbrl_tags(soup_without_xbrl) is False


def test_extract_xbrl_data():
    """Test XBRL data extraction."""
    html = """
    <html>
    <body>
        <ix:nonfraction contextRef="c1" name="us-gaap:Revenue" unitRef="usd">100000000</ix:nonfraction>
        <ix:nonnumeric contextRef="c1" name="us-gaap:EntityRegistrantName">Test Company</ix:nonnumeric>
    </body>
    </html>
    """
    
    parser = DocumentParser()
    soup = BeautifulSoup(html, 'lxml')
    xbrl_data = parser._extract_xbrl_data(soup)
    
    assert len(xbrl_data) >= 2
    assert any('Revenue' in key for key in xbrl_data.keys())


def test_extract_key_metrics():
    """Test key financial metrics extraction."""
    text = """
    Revenue: $100,000,000
    Net income: $20,000,000
    Total assets: $500,000,000
    Cash and cash equivalents: $50,000,000
    """
    
    parser = DocumentParser()
    soup = BeautifulSoup(f"<html><body><p>{text}</p></body></html>", 'lxml')
    metrics = parser._extract_key_metrics(soup)
    
    assert 'revenue' in metrics
    assert '100,000,000' in metrics['revenue']
