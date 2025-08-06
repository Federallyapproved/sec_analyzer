"""
Main SEC analyzer orchestrator that coordinates downloading, parsing, and storage.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import (
    Filing, ParsedDocument, AnalyzerConfig, AnalysisResult, 
    ProcessingStats, CleaningOptions
)
from .downloader import SECDownloader
from .parser import DocumentParser
from .storage import DocumentStorage

logger = logging.getLogger(__name__)


class SECAnalyzer:
    """Main orchestrator for SEC document analysis."""
    
    def __init__(self, config: AnalyzerConfig):
        """Initialize the analyzer with configuration."""
        self.config = config
        self.downloader = SECDownloader(config)
        self.parser = DocumentParser(CleaningOptions())
        self.storage = DocumentStorage(config)
        
        self._setup_logging()
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(self.config.output_dir / 'sec_analyzer.log')
            ]
        )
    
    async def analyze_ticker(
        self, 
        ticker: str, 
        forms: Optional[List[str]] = None
    ) -> AnalysisResult:
        """
        Analyze all SEC documents for a given ticker.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'RDDT')
            forms: Optional list of form types to process (e.g., ['10-K', '10-Q'])
            
        Returns:
            AnalysisResult containing processed documents and statistics
        """
        start_time = time.time()
        logger.info(f"Starting analysis for ticker: {ticker}")
        
        try:
            async with self.downloader as downloader:
                company_info = await downloader.get_company_info(ticker)
                logger.info(f"Analyzing {company_info['name']} (CIK: {company_info['cik']})")
                
                downloaded_docs = await downloader.download_all_documents(ticker, forms)
                logger.info(f"Downloaded {len(downloaded_docs)} documents")
            
            processed_documents = []
            failed_documents = []
            output_paths = {"txt": [], "json": [], "markdown": [], "structured": []}
            
            for filing, content in downloaded_docs:
                try:
                    parsed_doc = self.parser.parse_html_document(content, filing)
                    processed_documents.append(parsed_doc)
                    
                    if self.config.save_raw_documents:
                        await self.storage.save_raw_document(content, filing)
                    
                    if self.config.save_clean_text:
                        clean_paths = await self.storage.save_cleaned_document(parsed_doc)
                        for format_type, path in clean_paths.items():
                            if path:
                                output_paths[format_type].append(path)
                    
                    if self.config.save_structured_data:
                        structured_path = await self.storage.save_structured_data(parsed_doc)
                        if structured_path:
                            output_paths["structured"].append(structured_path)
                    
                    logger.info(f"Successfully processed: {filing.form_type} - {filing.accession_number}")
                    
                except Exception as e:
                    logger.error(f"Failed to process {filing.accession_number}: {e}")
                    failed_documents.append(filing)
            
            processing_time = time.time() - start_time
            stats = self._calculate_stats(processed_documents, failed_documents, processing_time)
            
            result = AnalysisResult(
                ticker=ticker,
                company_name=company_info['name'],
                cik=company_info['cik'],
                processed_documents=processed_documents,
                failed_documents=failed_documents,
                stats=stats,
                output_paths=output_paths,
                analysis_timestamp=datetime.utcnow()
            )
            
            await self.storage.save_analysis_summary(result)
            
            logger.info(f"Analysis completed for {ticker}: {len(processed_documents)} documents processed, {len(failed_documents)} failed")
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing ticker {ticker}: {e}")
            raise
    
    async def analyze_single_document(
        self, 
        ticker: str, 
        accession_number: str
    ) -> ParsedDocument:
        """
        Analyze a single SEC document by accession number.
        
        Args:
            ticker: Stock ticker symbol
            accession_number: SEC accession number
            
        Returns:
            ParsedDocument containing the processed document
        """
        logger.info(f"Analyzing single document: {accession_number}")
        
        try:
            async with self.downloader as downloader:
                filings = await downloader.get_company_filings(ticker)
                target_filing = None
                
                for filing in filings:
                    if filing.accession_number == accession_number:
                        target_filing = filing
                        break
                
                if not target_filing:
                    raise ValueError(f"Document {accession_number} not found for ticker {ticker}")
                
                content = await downloader.download_document(target_filing)
            
            parsed_doc = self.parser.parse_html_document(content, target_filing)
            
            if self.config.save_raw_documents:
                await self.storage.save_raw_document(content, target_filing)
            
            if self.config.save_clean_text:
                await self.storage.save_cleaned_document(parsed_doc)
            
            if self.config.save_structured_data:
                await self.storage.save_structured_data(parsed_doc)
            
            logger.info(f"Successfully processed single document: {accession_number}")
            return parsed_doc
            
        except Exception as e:
            logger.error(f"Error analyzing document {accession_number}: {e}")
            raise
    
    async def get_available_filings(self, ticker: str) -> List[Filing]:
        """
        Get list of available filings for a ticker without downloading.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            List of available Filing objects
        """
        try:
            async with self.downloader as downloader:
                filings = await downloader.get_company_filings(ticker)
                logger.info(f"Found {len(filings)} available filings for {ticker}")
                return filings
                
        except Exception as e:
            logger.error(f"Error getting filings for {ticker}: {e}")
            raise
    
    def _calculate_stats(
        self, 
        processed_docs: List[ParsedDocument], 
        failed_docs: List[Filing],
        processing_time: float
    ) -> ProcessingStats:
        """Calculate processing statistics."""
        total_text_length = sum(len(doc.clean_text) for doc in processed_docs)
        
        forms_processed = {}
        for doc in processed_docs:
            form_type = doc.filing.form_type
            forms_processed[form_type] = forms_processed.get(form_type, 0) + 1
        
        return ProcessingStats(
            documents_downloaded=len(processed_docs) + len(failed_docs),
            documents_processed=len(processed_docs),
            documents_failed=len(failed_docs),
            total_text_length=total_text_length,
            processing_time_seconds=processing_time,
            forms_processed=forms_processed
        )
    
    async def validate_setup(self) -> Dict[str, bool]:
        """
        Validate that the analyzer is properly configured and can access SEC data.
        
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "output_directory_writable": False,
            "cache_directory_writable": False,
            "sec_api_accessible": False,
            "edgar_library_working": False
        }
        
        try:
            test_file = self.config.output_dir / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            validation_results["output_directory_writable"] = True
            
        except Exception as e:
            logger.error(f"Output directory not writable: {e}")
        
        try:
            test_file = self.config.cache_dir / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            validation_results["cache_directory_writable"] = True
            
        except Exception as e:
            logger.error(f"Cache directory not writable: {e}")
        
        try:
            async with self.downloader as downloader:
                company_info = await downloader.get_company_info("AAPL")
                if company_info and company_info.get('name'):
                    validation_results["sec_api_accessible"] = True
                    validation_results["edgar_library_working"] = True
                    
        except Exception as e:
            logger.error(f"SEC API or edgar library test failed: {e}")
        
        return validation_results
    
    def get_output_summary(self, ticker: str) -> Dict[str, Any]:
        """
        Get summary of output files for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with output file information
        """
        output_structure = self.storage.get_output_structure(ticker)
        summary = {}
        
        for category, path in output_structure.items():
            if path.exists():
                files = list(path.glob("*"))
                summary[category] = {
                    "path": str(path),
                    "file_count": len(files),
                    "files": [f.name for f in files]
                }
            else:
                summary[category] = {
                    "path": str(path),
                    "file_count": 0,
                    "files": []
                }
        
        return summary
