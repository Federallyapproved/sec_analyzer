"""
Storage module for saving processed SEC documents in various formats.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

import aiofiles

from .models import Filing, ParsedDocument, AnalyzerConfig, AnalysisResult

logger = logging.getLogger(__name__)


class DocumentStorage:
    """Handles storage of processed SEC documents in multiple formats."""
    
    def __init__(self, config: AnalyzerConfig):
        """Initialize storage with configuration."""
        self.config = config
        self.output_dir = config.output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    async def save_raw_document(self, document: str, filing: Filing) -> Path:
        """Save raw HTML/XML document content."""
        if not self.config.save_raw_documents:
            return None
            
        try:
            ticker_dir = self.output_dir / filing.ticker / "raw"
            ticker_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{filing.form_type}_{filing.accession_number.replace('-', '')}_{filing.filing_date.strftime('%Y%m%d')}.html"
            file_path = ticker_dir / filename
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(document)
            
            logger.debug(f"Saved raw document: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving raw document {filing.accession_number}: {e}")
            raise
    
    async def save_cleaned_document(self, parsed_doc: ParsedDocument) -> Dict[str, Path]:
        """Save cleaned document in multiple formats."""
        if not self.config.save_clean_text:
            return {}
            
        saved_paths = {}
        filing = parsed_doc.filing
        
        try:
            ticker_dir = self.output_dir / filing.ticker / "clean"
            ticker_dir.mkdir(parents=True, exist_ok=True)
            
            base_filename = f"{filing.form_type}_{filing.accession_number.replace('-', '')}_{filing.filing_date.strftime('%Y%m%d')}"
            
            for format_type in self.config.output_formats:
                if format_type == "txt":
                    path = await self._save_as_text(parsed_doc, ticker_dir, base_filename)
                    saved_paths["txt"] = path
                elif format_type == "json":
                    path = await self._save_as_json(parsed_doc, ticker_dir, base_filename)
                    saved_paths["json"] = path
                elif format_type == "markdown":
                    path = await self._save_as_markdown(parsed_doc, ticker_dir, base_filename)
                    saved_paths["markdown"] = path
            
            return saved_paths
            
        except Exception as e:
            logger.error(f"Error saving cleaned document {filing.accession_number}: {e}")
            raise
    
    async def save_structured_data(self, parsed_doc: ParsedDocument) -> Path:
        """Save structured financial data as JSON."""
        if not self.config.save_structured_data:
            return None
            
        try:
            filing = parsed_doc.filing
            
            ticker_dir = self.output_dir / filing.ticker / "structured"
            ticker_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{filing.form_type}_{filing.accession_number.replace('-', '')}_{filing.filing_date.strftime('%Y%m%d')}_structured.json"
            file_path = ticker_dir / filename
            
            structured_data = {
                "filing_info": {
                    "form_type": filing.form_type,
                    "filing_date": filing.filing_date.isoformat(),
                    "accession_number": filing.accession_number,
                    "company_name": filing.company_name,
                    "ticker": filing.ticker,
                    "cik": filing.cik
                },
                "sections": [
                    {
                        "title": section.title,
                        "content": section.content,
                        "level": section.level,
                        "order": section.order
                    }
                    for section in parsed_doc.sections
                ],
                "tables": [
                    {
                        "title": table.title,
                        "headers": table.headers,
                        "rows": table.rows,
                        "metadata": table.metadata
                    }
                    for table in parsed_doc.tables
                ],
                "structured_data": parsed_doc.structured_data,
                "metadata": parsed_doc.metadata,
                "processing_timestamp": parsed_doc.processing_timestamp.isoformat()
            }
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(structured_data, indent=2, ensure_ascii=False))
            
            logger.debug(f"Saved structured data: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving structured data {filing.accession_number}: {e}")
            raise
    
    async def save_analysis_summary(self, result: AnalysisResult) -> Path:
        """Save analysis summary and statistics."""
        try:
            summary_dir = self.output_dir / result.ticker / "summary"
            summary_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = result.analysis_timestamp.strftime('%Y%m%d_%H%M%S')
            filename = f"{result.ticker}_analysis_summary_{timestamp}.json"
            file_path = summary_dir / filename
            
            summary_data = {
                "ticker": result.ticker,
                "company_name": result.company_name,
                "cik": result.cik,
                "analysis_timestamp": result.analysis_timestamp.isoformat(),
                "statistics": {
                    "documents_downloaded": result.stats.documents_downloaded,
                    "documents_processed": result.stats.documents_processed,
                    "documents_failed": result.stats.documents_failed,
                    "total_text_length": result.stats.total_text_length,
                    "processing_time_seconds": result.stats.processing_time_seconds,
                    "forms_processed": result.stats.forms_processed
                },
                "processed_documents": [
                    {
                        "form_type": doc.filing.form_type,
                        "filing_date": doc.filing.filing_date.isoformat(),
                        "accession_number": doc.filing.accession_number,
                        "sections_count": len(doc.sections),
                        "tables_count": len(doc.tables),
                        "clean_text_length": len(doc.clean_text),
                        "has_xbrl": doc.metadata.get("has_xbrl", False)
                    }
                    for doc in result.processed_documents
                ],
                "failed_documents": [
                    {
                        "form_type": filing.form_type,
                        "filing_date": filing.filing_date.isoformat(),
                        "accession_number": filing.accession_number
                    }
                    for filing in result.failed_documents
                ],
                "output_paths": {
                    format_type: [str(path) for path in paths]
                    for format_type, paths in result.output_paths.items()
                }
            }
            
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(summary_data, indent=2, ensure_ascii=False))
            
            logger.info(f"Saved analysis summary: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"Error saving analysis summary for {result.ticker}: {e}")
            raise
    
    async def _save_as_text(self, parsed_doc: ParsedDocument, output_dir: Path, base_filename: str) -> Path:
        """Save document as plain text."""
        file_path = output_dir / f"{base_filename}.txt"
        
        content_parts = []
        
        filing = parsed_doc.filing
        content_parts.append(f"SEC Filing: {filing.form_type}")
        content_parts.append(f"Company: {filing.company_name} ({filing.ticker})")
        content_parts.append(f"Filing Date: {filing.filing_date.strftime('%Y-%m-%d')}")
        content_parts.append(f"Accession Number: {filing.accession_number}")
        content_parts.append("=" * 80)
        content_parts.append("")
        
        content_parts.append(parsed_doc.clean_text)
        
        if parsed_doc.sections:
            content_parts.append("\n" + "=" * 80)
            content_parts.append("DOCUMENT SECTIONS")
            content_parts.append("=" * 80)
            
            for section in parsed_doc.sections:
                content_parts.append(f"\n{'#' * section.level} {section.title}")
                content_parts.append(section.content)
        
        content = "\n".join(content_parts)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return file_path
    
    async def _save_as_json(self, parsed_doc: ParsedDocument, output_dir: Path, base_filename: str) -> Path:
        """Save document as JSON."""
        file_path = output_dir / f"{base_filename}.json"
        
        json_data = {
            "filing": {
                "form_type": parsed_doc.filing.form_type,
                "filing_date": parsed_doc.filing.filing_date.isoformat(),
                "accession_number": parsed_doc.filing.accession_number,
                "company_name": parsed_doc.filing.company_name,
                "ticker": parsed_doc.filing.ticker,
                "cik": parsed_doc.filing.cik
            },
            "clean_text": parsed_doc.clean_text,
            "sections": [
                {
                    "title": section.title,
                    "content": section.content,
                    "level": section.level,
                    "order": section.order
                }
                for section in parsed_doc.sections
            ],
            "metadata": parsed_doc.metadata,
            "processing_timestamp": parsed_doc.processing_timestamp.isoformat()
        }
        
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(json_data, indent=2, ensure_ascii=False))
        
        return file_path
    
    async def _save_as_markdown(self, parsed_doc: ParsedDocument, output_dir: Path, base_filename: str) -> Path:
        """Save document as Markdown."""
        file_path = output_dir / f"{base_filename}.md"
        
        content_parts = []
        
        filing = parsed_doc.filing
        content_parts.append(f"# {filing.form_type} - {filing.company_name}")
        content_parts.append(f"**Ticker:** {filing.ticker}")
        content_parts.append(f"**Filing Date:** {filing.filing_date.strftime('%Y-%m-%d')}")
        content_parts.append(f"**Accession Number:** {filing.accession_number}")
        content_parts.append("")
        
        if parsed_doc.sections:
            for section in parsed_doc.sections:
                content_parts.append(f"{'#' * (section.level + 1)} {section.title}")
                content_parts.append("")
                content_parts.append(section.content)
                content_parts.append("")
        else:
            content_parts.append("## Document Content")
            content_parts.append("")
            content_parts.append(parsed_doc.clean_text)
        
        if parsed_doc.tables:
            content_parts.append("## Financial Tables")
            content_parts.append("")
            
            for i, table in enumerate(parsed_doc.tables):
                content_parts.append(f"### {table.title}")
                content_parts.append("")
                
                if table.headers and table.rows:
                    content_parts.append("| " + " | ".join(table.headers) + " |")
                    content_parts.append("| " + " | ".join(["---"] * len(table.headers)) + " |")
                    
                    for row in table.rows[:10]:
                        if len(row) == len(table.headers):
                            content_parts.append("| " + " | ".join(row) + " |")
                    
                    if len(table.rows) > 10:
                        content_parts.append(f"*... and {len(table.rows) - 10} more rows*")
                
                content_parts.append("")
        
        content = "\n".join(content_parts)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(content)
        
        return file_path
    
    def get_output_structure(self, ticker: str) -> Dict[str, Path]:
        """Get the expected output directory structure for a ticker."""
        ticker_dir = self.output_dir / ticker
        
        return {
            "base": ticker_dir,
            "raw": ticker_dir / "raw",
            "clean": ticker_dir / "clean", 
            "structured": ticker_dir / "structured",
            "summary": ticker_dir / "summary"
        }
