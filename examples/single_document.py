"""
Example script showing how to analyze a single SEC document.
"""

import asyncio
from pathlib import Path

from sec_analyzer import SECAnalyzer, AnalyzerConfig


async def main():
    """Analyze a single RDDT document."""
    
    config = AnalyzerConfig(
        user_agent="SEC Analyzer Single Document Example (contact@example.com)",
        output_dir=Path("single_doc_output"),
        output_formats=["txt", "json"]
    )
    
    analyzer = SECAnalyzer(config)
    
    print("🔍 Fetching available RDDT filings...")
    
    try:
        filings = await analyzer.get_available_filings("RDDT")
        
        if not filings:
            print("❌ No filings found for RDDT")
            return
        
        print(f"📋 Found {len(filings)} filings. Recent ones:")
        for filing in filings[:5]:
            print(f"  {filing.form_type} - {filing.filing_date.strftime('%Y-%m-%d')} - {filing.accession_number}")
        
        recent_10q = None
        for filing in filings:
            if filing.form_type == "10-Q":
                recent_10q = filing
                break
        
        if not recent_10q:
            print("❌ No 10-Q filings found")
            return
        
        print(f"\n📊 Analyzing recent 10-Q: {recent_10q.accession_number}")
        
        parsed_doc = await analyzer.analyze_single_document("RDDT", recent_10q.accession_number)
        
        print(f"\n🎉 Document analysis completed!")
        print(f"Form Type: {parsed_doc.filing.form_type}")
        print(f"Company: {parsed_doc.filing.company_name}")
        print(f"Filing Date: {parsed_doc.filing.filing_date.strftime('%Y-%m-%d')}")
        print(f"Clean Text Length: {len(parsed_doc.clean_text):,} characters")
        print(f"Sections: {len(parsed_doc.sections)}")
        print(f"Tables: {len(parsed_doc.tables)}")
        
        if parsed_doc.sections:
            print(f"\n📑 Document sections:")
            for section in parsed_doc.sections[:3]:
                print(f"  {section.title} (Level {section.level})")
        
        if parsed_doc.tables:
            print(f"\n📊 Financial tables:")
            for table in parsed_doc.tables[:3]:
                print(f"  {table.title} ({len(table.rows)} rows)")
        
        print(f"\n📁 Output saved to: {config.output_dir}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
