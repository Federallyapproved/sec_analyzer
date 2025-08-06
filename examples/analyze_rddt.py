"""
Example script showing how to analyze SEC documents for Reddit (RDDT).
"""

import asyncio
from pathlib import Path

from sec_analyzer import SECAnalyzer, AnalyzerConfig


async def main():
    """Analyze RDDT SEC documents."""
    
    config = AnalyzerConfig(
        user_agent="SEC Analyzer Example (contact@example.com)",
        output_dir=Path("rddt_output"),
        cache_dir=Path("rddt_cache"),
        forms_to_process=["10-Q", "10-K", "8-K"],
        max_concurrent_downloads=3,
        output_formats=["txt", "json", "markdown"]
    )
    
    analyzer = SECAnalyzer(config)
    
    print("🔍 Validating setup...")
    validation = await analyzer.validate_setup()
    
    if not all(validation.values()):
        print("❌ Setup validation failed:")
        for check, result in validation.items():
            status = "✅" if result else "❌"
            print(f"  {status} {check.replace('_', ' ').title()}")
        return
    
    print("✅ Setup validated successfully!")
    
    print("\n📊 Starting analysis of RDDT SEC documents...")
    
    try:
        result = await analyzer.analyze_ticker("RDDT")
        
        print(f"\n🎉 Analysis completed!")
        print(f"Company: {result.company_name}")
        print(f"Documents processed: {result.stats.documents_processed}")
        print(f"Documents failed: {result.stats.documents_failed}")
        print(f"Total text length: {result.stats.total_text_length:,} characters")
        print(f"Processing time: {result.stats.processing_time_seconds:.2f} seconds")
        
        print(f"\n📁 Output files saved to: {config.output_dir}")
        
        if result.stats.forms_processed:
            print("\n📋 Forms processed:")
            for form_type, count in result.stats.forms_processed.items():
                print(f"  {form_type}: {count} documents")
        
        if result.output_paths:
            print("\n📄 Sample output files:")
            for format_type, paths in result.output_paths.items():
                if paths:
                    print(f"  {format_type.upper()}: {paths[0]}")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
