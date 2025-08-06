# SEC Analyzer

A comprehensive Python tool for downloading and cleaning SEC documents for AI ingestion. This tool provides a complete pipeline for fetching SEC filings, parsing HTML/XBRL content, and extracting clean text suitable for AI analysis.

## Features

- **Automated Document Download**: Fetch SEC documents using the official EDGAR API
- **Intelligent Parsing**: Extract clean text from HTML/XBRL SEC filings
- **Multiple Output Formats**: Generate text, JSON, and Markdown outputs
- **Async Processing**: Efficient concurrent document processing
- **Comprehensive CLI**: Easy-to-use command-line interface
- **Structured Data Extraction**: Extract financial tables and XBRL data
- **Caching**: Built-in caching to avoid re-downloading documents

## Supported Document Types

- 10-K (Annual Reports)
- 10-Q (Quarterly Reports)
- 8-K (Current Reports)
- DEF 14A (Proxy Statements)
- Other SEC forms as needed

## Installation

### From Source

```bash
git clone https://github.com/Federallyapproved/sec_analyzer.git
cd sec_analyzer
pip install -e .
```

### Development Installation

```bash
git clone https://github.com/Federallyapproved/sec_analyzer.git
cd sec_analyzer
pip install -e ".[dev]"
```

## Quick Start

### Command Line Usage

```bash
# Analyze all documents for a ticker
sec-analyzer analyze RDDT

# Analyze specific form types
sec-analyzer analyze RDDT --forms 10-Q,10-K

# List available filings
sec-analyzer list-filings RDDT

# Analyze a single document
sec-analyzer analyze-document RDDT 0001713445-24-000196

# Validate setup
sec-analyzer validate
```

### Python API Usage

```python
import asyncio
from pathlib import Path
from sec_analyzer import SECAnalyzer, AnalyzerConfig

async def main():
    # Configure the analyzer
    config = AnalyzerConfig(
        user_agent="Your App Name (contact@example.com)",
        output_dir=Path("output"),
        forms_to_process=["10-K", "10-Q", "8-K"]
    )
    
    # Create analyzer
    analyzer = SECAnalyzer(config)
    
    # Analyze a ticker
    result = await analyzer.analyze_ticker("RDDT")
    
    print(f"Processed {result.stats.documents_processed} documents")
    print(f"Total text length: {result.stats.total_text_length:,} characters")

if __name__ == "__main__":
    asyncio.run(main())
```

## Architecture

The SEC Analyzer follows a modular architecture with clear separation of concerns:

```
src/sec_analyzer/
├── __init__.py          # Package initialization
├── models.py            # Pydantic data models
├── downloader.py        # SEC document downloading
├── parser.py            # HTML/XBRL parsing and cleaning
├── storage.py           # Multi-format output storage
├── analyzer.py          # Main orchestrator
└── cli.py              # Command-line interface
```

### Core Components

1. **Downloader**: Uses the `edgar-sec` library to fetch documents from the SEC EDGAR database
2. **Parser**: Extracts clean text from HTML/XBRL documents, removing tags while preserving structure
3. **Storage**: Saves processed documents in multiple formats (text, JSON, Markdown)
4. **Analyzer**: Orchestrates the entire pipeline from download to storage

## Configuration

Create a `config.yaml` file to customize behavior:

```yaml
# User agent for SEC API requests (required)
user_agent: "Your App Name (contact@example.com)"

# Output settings
output_dir: "output"
cache_dir: "cache"

# Document types to process
forms_to_process:
  - "10-K"
  - "10-Q" 
  - "8-K"

# Processing settings
max_concurrent_downloads: 5
rate_limit_delay: 0.1

# Output formats
output_formats:
  - "txt"
  - "json"
  - "markdown"

# Document cleaning options
cleaning_options:
  remove_html_tags: true
  remove_xbrl_tags: true
  preserve_tables: true
  preserve_sections: true
  remove_boilerplate: true
  normalize_whitespace: true
  extract_financial_data: true
  min_section_length: 50
```

## Output Structure

The tool creates an organized directory structure for each ticker:

```
output/
└── RDDT/
    ├── raw/                 # Original HTML documents
    ├── clean/               # Cleaned text files
    │   ├── *.txt           # Plain text format
    │   ├── *.json          # JSON format with metadata
    │   └── *.md            # Markdown format
    ├── structured/          # Structured data extraction
    │   └── *_structured.json
    └── summary/             # Analysis summaries
        └── *_analysis_summary.json
```

## Examples

### Analyze Reddit (RDDT) Documents

```python
# examples/analyze_rddt.py
import asyncio
from sec_analyzer import SECAnalyzer, AnalyzerConfig

async def main():
    config = AnalyzerConfig(
        user_agent="SEC Analyzer Example (contact@example.com)",
        forms_to_process=["10-Q", "10-K", "8-K"]
    )
    
    analyzer = SECAnalyzer(config)
    result = await analyzer.analyze_ticker("RDDT")
    
    print(f"✅ Processed {result.stats.documents_processed} documents")
    print(f"📊 Forms processed: {result.stats.forms_processed}")

asyncio.run(main())
```

### Process a Single Document

```python
# examples/single_document.py
import asyncio
from sec_analyzer import SECAnalyzer, AnalyzerConfig

async def main():
    config = AnalyzerConfig(
        user_agent="SEC Analyzer Example (contact@example.com)"
    )
    
    analyzer = SECAnalyzer(config)
    
    # Get available filings
    filings = await analyzer.get_available_filings("RDDT")
    
    # Process the most recent 10-Q
    recent_10q = next(f for f in filings if f.form_type == "10-Q")
    parsed_doc = await analyzer.analyze_single_document("RDDT", recent_10q.accession_number)
    
    print(f"📄 Processed: {parsed_doc.filing.form_type}")
    print(f"📝 Clean text length: {len(parsed_doc.clean_text):,} characters")
    print(f"📊 Tables found: {len(parsed_doc.tables)}")

asyncio.run(main())
```

## Testing

Run the test suite:

```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=src/sec_analyzer --cov-report=html

# Run specific test file
python -m pytest tests/test_models.py -v
```

## Development

### Setup Development Environment

```bash
git clone https://github.com/Federallyapproved/sec_analyzer.git
cd sec_analyzer
pip install -e ".[dev]"
```

### Code Formatting

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/
mypy src/
```

### Running Examples

```bash
# Test with RDDT ticker
python examples/analyze_rddt.py

# Test single document processing
python examples/single_document.py
```

## API Reference

### AnalyzerConfig

Configuration class for the SEC analyzer.

**Parameters:**
- `user_agent` (str): User agent for SEC API requests (required)
- `output_dir` (Path): Output directory for processed documents
- `cache_dir` (Path): Cache directory for downloaded documents
- `forms_to_process` (List[str]): List of form types to process
- `max_concurrent_downloads` (int): Maximum concurrent downloads
- `output_formats` (List[str]): Output formats to generate

### SECAnalyzer

Main orchestrator class for SEC document analysis.

**Methods:**
- `analyze_ticker(ticker, forms=None)`: Analyze all documents for a ticker
- `analyze_single_document(ticker, accession_number)`: Analyze a single document
- `get_available_filings(ticker)`: Get list of available filings
- `validate_setup()`: Validate analyzer configuration

### Models

- `Filing`: Represents a single SEC filing
- `ParsedDocument`: Represents a parsed and processed document
- `AnalysisResult`: Result of analyzing a ticker's documents
- `DocumentSection`: Represents a section within a document
- `FinancialTable`: Represents a financial table

## Requirements

- Python 3.8+
- edgar-sec >= 2.0.0
- beautifulsoup4 >= 4.12.0
- lxml >= 4.9.0
- aiofiles >= 23.0.0
- pydantic >= 2.0.0
- click >= 8.0.0
- rich >= 13.0.0

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run the test suite
6. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check the examples directory for usage patterns
- Review the test files for implementation details

## Changelog

### v0.1.0
- Initial release
- Core document downloading and parsing functionality
- CLI interface
- Support for 10-K, 10-Q, 8-K documents
- Multiple output formats (text, JSON, Markdown)
- Comprehensive test suite
