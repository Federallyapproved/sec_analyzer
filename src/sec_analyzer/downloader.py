"""
SEC document downloader using edgar-sec library.
"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

import aiofiles
import aiohttp
from edgar_sec import Company, Filing as EdgarFiling

from .models import Filing, AnalyzerConfig

logger = logging.getLogger(__name__)


class SECDownloader:
    """Downloads SEC documents using the edgar-sec library."""
    
    def __init__(self, config: AnalyzerConfig):
        """Initialize the downloader with configuration."""
        self.config = config
        self.cache_dir = config.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def get_company_filings(self, ticker: str) -> List[Filing]:
        """Get all filings for a company by ticker symbol."""
        try:
            logger.info(f"Fetching filings for ticker: {ticker}")
            
            from edgar_sec import EdgarAPI
            api = EdgarAPI()
            
            ticker_to_cik = {
                'RDDT': '0001713445',
                'AAPL': '0000320193',
                'MSFT': '0000789019',
                'GOOGL': '0001652044',
                'TSLA': '0001318605'
            }
            
            cik = ticker_to_cik.get(ticker.upper())
            if not cik:
                raise ValueError(f"CIK not found for ticker {ticker}. Supported tickers: {list(ticker_to_cik.keys())}")
            
            submissions = api.get_submissions(cik)
            
            company_name = submissions.get('name', ticker)
            filings_data = submissions.get('filings', {}).get('recent', {})
            
            result_filings = []
            
            forms = filings_data.get('form', [])
            filing_dates = filings_data.get('filingDate', [])
            accession_numbers = filings_data.get('accessionNumber', [])
            primary_documents = filings_data.get('primaryDocument', [])
            
            for i in range(len(forms)):
                form_type = forms[i]
                if form_type in self.config.forms_to_process:
                    accession_clean = accession_numbers[i].replace('-', '')
                    document_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_clean}/{primary_documents[i]}"
                    
                    our_filing = Filing(
                        form_type=form_type,
                        filing_date=datetime.strptime(filing_dates[i], '%Y-%m-%d'),
                        accession_number=accession_numbers[i],
                        document_url=document_url,
                        company_name=company_name,
                        cik=cik,
                        ticker=ticker.upper(),
                        file_size=None
                    )
                    result_filings.append(our_filing)
            
            logger.info(f"Found {len(result_filings)} filings for {ticker}")
            return result_filings
            
        except Exception as e:
            logger.error(f"Error fetching filings for {ticker}: {e}")
            raise
    
    async def download_document(self, filing: Filing) -> str:
        """Download a specific document and return its content."""
        try:
            cache_path = self._get_cache_path(filing)
            if cache_path.exists():
                logger.debug(f"Loading from cache: {cache_path}")
                async with aiofiles.open(cache_path, 'r', encoding='utf-8') as f:
                    return await f.read()
            
            logger.info(f"Downloading document: {filing.accession_number}")
            
            if not self.session:
                raise RuntimeError("Downloader not initialized. Use async context manager.")
            
            headers = {
                'User-Agent': self.config.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }
            
            async with self.session.get(filing.document_url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()
            
            await self._cache_document(filing, content)
            
            await asyncio.sleep(self.config.rate_limit_delay)
            
            return content
            
        except Exception as e:
            logger.error(f"Error downloading document {filing.accession_number}: {e}")
            raise
    
    async def download_all_documents(
        self, 
        ticker: str, 
        forms: Optional[List[str]] = None
    ) -> List[tuple[Filing, str]]:
        """Download all documents for a ticker."""
        try:
            filings = await self.get_company_filings(ticker)
            
            if forms:
                filings = [f for f in filings if f.form_type in forms]
            
            logger.info(f"Downloading {len(filings)} documents for {ticker}")
            
            semaphore = asyncio.Semaphore(self.config.max_concurrent_downloads)
            
            async def download_with_semaphore(filing: Filing) -> tuple[Filing, str]:
                async with semaphore:
                    content = await self.download_document(filing)
                    return filing, content
            
            tasks = [download_with_semaphore(filing) for filing in filings]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_results = []
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Download failed: {result}")
                else:
                    successful_results.append(result)
            
            logger.info(f"Successfully downloaded {len(successful_results)} documents")
            return successful_results
            
        except Exception as e:
            logger.error(f"Error downloading documents for {ticker}: {e}")
            raise
    
    def _get_cache_path(self, filing: Filing) -> Path:
        """Get the cache file path for a filing."""
        filename = f"{filing.ticker}_{filing.form_type}_{filing.accession_number.replace('-', '')}.html"
        return self.cache_dir / filename
    
    async def _cache_document(self, filing: Filing, content: str) -> None:
        """Cache a document to disk."""
        try:
            cache_path = self._get_cache_path(filing)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            async with aiofiles.open(cache_path, 'w', encoding='utf-8') as f:
                await f.write(content)
                
            logger.debug(f"Cached document: {cache_path}")
            
        except Exception as e:
            logger.warning(f"Failed to cache document {filing.accession_number}: {e}")
    
    async def get_company_info(self, ticker: str) -> Dict[str, Any]:
        """Get basic company information."""
        try:
            from edgar_sec import EdgarAPI
            api = EdgarAPI()
            
            ticker_to_cik = {
                'RDDT': '0001713445',
                'AAPL': '0000320193',
                'MSFT': '0000789019',
                'GOOGL': '0001652044',
                'TSLA': '0001318605'
            }
            
            cik = ticker_to_cik.get(ticker.upper())
            if not cik:
                raise ValueError(f"CIK not found for ticker {ticker}. Supported tickers: {list(ticker_to_cik.keys())}")
            
            submissions = api.get_submissions(cik)
            
            return {
                'name': submissions.get('name', ticker),
                'cik': cik,
                'ticker': ticker.upper(),
                'sic': submissions.get('sic', None),
                'industry': submissions.get('sicDescription', None),
            }
            
        except Exception as e:
            logger.error(f"Error getting company info for {ticker}: {e}")
            raise
