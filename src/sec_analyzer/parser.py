"""
SEC document parser and cleaner for extracting cleartext from HTML/XBRL documents.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from bs4 import BeautifulSoup, Tag, NavigableString
from bs4.element import Comment

from .models import (
    Filing, ParsedDocument, DocumentSection, FinancialTable, 
    CleaningOptions
)

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parses and cleans SEC documents for AI ingestion."""
    
    def __init__(self, cleaning_options: Optional[CleaningOptions] = None):
        """Initialize the parser with cleaning options."""
        self.cleaning_options = cleaning_options or CleaningOptions()
        
        self.boilerplate_patterns = [
            r'Table of Contents',
            r'UNITED STATES\s+SECURITIES AND EXCHANGE COMMISSION',
            r'Washington,?\s*D\.?C\.?\s*20549',
            r'FORM\s+\d+-[KQ]',
            r'Commission File Number:?\s*\d+-\d+',
            r'Exact name of registrant as specified in its charter',
            r'State or other jurisdiction of incorporation',
            r'I\.R\.S\. Employer Identification No\.',
            r'Large accelerated filer\s+☐?\s*Accelerated filer',
            r'Non-accelerated filer\s+☐?\s*Smaller reporting company',
        ]
        
        self.table_indicators = [
            'consolidated', 'balance sheet', 'income statement', 'cash flow',
            'statement of operations', 'comprehensive income', 'stockholders equity',
            'financial position', 'earnings', 'revenue', 'assets', 'liabilities'
        ]
    
    def parse_html_document(self, content: str, filing: Filing) -> ParsedDocument:
        """Parse an HTML SEC document and extract structured data."""
        try:
            logger.info(f"Parsing document: {filing.accession_number}")
            
            soup = BeautifulSoup(content, 'lxml')
            
            self._remove_unwanted_elements(soup)
            
            sections = self._extract_sections(soup)
            
            tables = self._extract_tables(soup)
            
            structured_data = self._extract_structured_data(soup)
            
            clean_text = self._extract_clean_text(soup)
            
            metadata = {
                'original_length': len(content),
                'clean_text_length': len(clean_text),
                'sections_count': len(sections),
                'tables_count': len(tables),
                'has_xbrl': self._has_xbrl_tags(soup),
                'parser_version': '1.0',
            }
            
            return ParsedDocument(
                filing=filing,
                raw_content=content,
                clean_text=clean_text,
                sections=sections,
                tables=tables,
                structured_data=structured_data,
                metadata=metadata,
                processing_timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Error parsing document {filing.accession_number}: {e}")
            raise
    
    def _remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
        """Remove unwanted HTML elements."""
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
        
        for tag in soup.find_all(['script', 'style', 'meta', 'link']):
            tag.decompose()
        
        if self.cleaning_options.remove_xbrl_tags:
            for tag in soup.find_all(lambda tag: tag.name and ':' in tag.name):
                if tag.string:
                    tag.replace_with(tag.string)
                else:
                    tag.unwrap()
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[DocumentSection]:
        """Extract document sections based on headings."""
        sections = []
        
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        
        for i, heading in enumerate(headings):
            try:
                level = int(heading.name[1])
                title = self._clean_text(heading.get_text())
                
                if not title or len(title) < 3:
                    continue
                
                content_elements = []
                current = heading.next_sibling
                
                while current:
                    if (hasattr(current, 'name') and 
                        current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                        current_level = int(current.name[1])
                        if current_level <= level:
                            break
                    
                    if hasattr(current, 'get_text'):
                        content_elements.append(current.get_text())
                    elif isinstance(current, NavigableString):
                        content_elements.append(str(current))
                    
                    current = current.next_sibling
                
                content = self._clean_text(' '.join(content_elements))
                
                if len(content) >= self.cleaning_options.min_section_length:
                    sections.append(DocumentSection(
                        title=title,
                        content=content,
                        level=level,
                        order=i
                    ))
                    
            except Exception as e:
                logger.warning(f"Error extracting section from heading: {e}")
                continue
        
        return sections
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[FinancialTable]:
        """Extract financial tables from the document."""
        tables = []
        
        for table_tag in soup.find_all('table'):
            try:
                table_text = table_tag.get_text().lower()
                is_financial = any(indicator in table_text for indicator in self.table_indicators)
                
                if not is_financial:
                    continue
                
                title = self._find_table_title(table_tag)
                
                headers = []
                header_row = table_tag.find('tr')
                if header_row:
                    for th in header_row.find_all(['th', 'td']):
                        header_text = self._clean_text(th.get_text())
                        if header_text:
                            headers.append(header_text)
                
                rows = []
                for tr in table_tag.find_all('tr')[1:]:  # Skip header row
                    row_data = []
                    for td in tr.find_all(['td', 'th']):
                        cell_text = self._clean_text(td.get_text())
                        row_data.append(cell_text)
                    
                    if any(cell.strip() for cell in row_data):  # Skip empty rows
                        rows.append(row_data)
                
                if headers and rows:
                    tables.append(FinancialTable(
                        title=title,
                        headers=headers,
                        rows=rows,
                        metadata={
                            'row_count': len(rows),
                            'column_count': len(headers),
                            'table_index': len(tables)
                        }
                    ))
                    
            except Exception as e:
                logger.warning(f"Error extracting table: {e}")
                continue
        
        return tables
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract structured financial data from XBRL and other sources."""
        structured_data = {}
        
        try:
            xbrl_data = self._extract_xbrl_data(soup)
            if xbrl_data:
                structured_data['xbrl'] = xbrl_data
            
            metrics = self._extract_key_metrics(soup)
            if metrics:
                structured_data['key_metrics'] = metrics
            
            doc_metadata = self._extract_document_metadata(soup)
            if doc_metadata:
                structured_data['document_metadata'] = doc_metadata
                
        except Exception as e:
            logger.warning(f"Error extracting structured data: {e}")
        
        return structured_data
    
    def _extract_clean_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text suitable for AI ingestion."""
        text = soup.get_text()
        
        clean_text = self._clean_text(text)
        
        if self.cleaning_options.remove_boilerplate:
            clean_text = self._remove_boilerplate(clean_text)
        
        return clean_text
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        
        if self.cleaning_options.normalize_whitespace:
            text = re.sub(r'\s+', ' ', text)
            text = re.sub(r'\n\s*\n', '\n\n', text)
        
        text = re.sub(r'[^\w\s\.\,\;\:\!\?\-\(\)\[\]\{\}\"\'\/\%\$\&\@\#]', ' ', text)
        
        return text.strip()
    
    def _remove_boilerplate(self, text: str) -> str:
        """Remove common boilerplate text."""
        for pattern in self.boilerplate_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE | re.MULTILINE)
        
        return text
    
    def _has_xbrl_tags(self, soup: BeautifulSoup) -> bool:
        """Check if document contains XBRL tags."""
        xbrl_tags = soup.find_all(lambda tag: tag.name and ':' in tag.name)
        return len(xbrl_tags) > 0
    
    def _extract_xbrl_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract XBRL financial data."""
        xbrl_data = {}
        
        xbrl_tags = soup.find_all(lambda tag: tag.name and ':' in tag.name)
        
        for tag in xbrl_tags:
            try:
                tag_name = tag.name
                tag_value = tag.get_text().strip()
                
                attrs = dict(tag.attrs) if tag.attrs else {}
                
                if tag_value and tag_name:
                    xbrl_data[tag_name] = {
                        'value': tag_value,
                        'attributes': attrs
                    }
                    
            except Exception as e:
                logger.debug(f"Error processing XBRL tag {tag}: {e}")
                continue
        
        return xbrl_data
    
    def _extract_key_metrics(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract key financial metrics from text."""
        metrics = {}
        text = soup.get_text()
        
        patterns = {
            'revenue': r'(?:revenue|net sales|total revenue)[:\s]+\$?([\d,\.]+)',
            'net_income': r'(?:net income|net earnings)[:\s]+\$?([\d,\.]+)',
            'total_assets': r'(?:total assets)[:\s]+\$?([\d,\.]+)',
            'total_liabilities': r'(?:total liabilities)[:\s]+\$?([\d,\.]+)',
            'cash': r'(?:cash and cash equivalents)[:\s]+\$?([\d,\.]+)',
        }
        
        for metric, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                metrics[metric] = matches[0]
        
        return metrics
    
    def _extract_document_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract document metadata."""
        metadata = {}
        
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        text = soup.get_text()
        date_pattern = r'(?:filed|filing date)[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})'
        date_match = re.search(date_pattern, text, re.IGNORECASE)
        if date_match:
            metadata['filing_date_text'] = date_match.group(1)
        
        return metadata
    
    def _find_table_title(self, table_tag: Tag) -> str:
        """Find the title for a table by looking at preceding elements."""
        title = "Financial Table"
        
        prev_element = table_tag.previous_sibling
        while prev_element:
            if hasattr(prev_element, 'name'):
                if prev_element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    title = self._clean_text(prev_element.get_text())
                    break
                elif prev_element.name == 'caption':
                    title = self._clean_text(prev_element.get_text())
                    break
            prev_element = prev_element.previous_sibling
        
        return title or "Financial Table"
