"""
Command-line interface for the SEC analyzer.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

from .analyzer import SECAnalyzer
from .models import AnalyzerConfig, FormType

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """SEC Analyzer - Download and clean SEC documents for AI ingestion."""
    pass


@cli.command()
@click.argument('ticker')
@click.option('--forms', default='10-K,10-Q,8-K', help='Comma-separated form types to process')
@click.option('--output-dir', default='output', help='Output directory for processed documents')
@click.option('--cache-dir', default='cache', help='Cache directory for downloaded documents')
@click.option('--user-agent', default='Self federallyapproved@gmail.com', help='User agent for SEC requests')
@click.option('--max-concurrent', default=5, help='Maximum concurrent downloads')
@click.option('--formats', default='txt,json,markdown', help='Output formats (txt,json,markdown)')
@click.option('--no-raw', is_flag=True, help='Do not save raw HTML documents')
@click.option('--no-clean', is_flag=True, help='Do not save cleaned text')
@click.option('--no-structured', is_flag=True, help='Do not save structured data')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
def analyze(
    ticker: str,
    forms: str,
    output_dir: str,
    cache_dir: str,
    user_agent: str,
    max_concurrent: int,
    formats: str,
    no_raw: bool,
    no_clean: bool,
    no_structured: bool,
    verbose: bool
):
    """Analyze SEC documents for a given ticker."""
    
    config = AnalyzerConfig(
        user_agent=user_agent,
        output_dir=Path(output_dir),
        cache_dir=Path(cache_dir),
        forms_to_process=forms.split(','),
        max_concurrent_downloads=max_concurrent,
        output_formats=formats.split(','),
        save_raw_documents=not no_raw,
        save_clean_text=not no_clean,
        save_structured_data=not no_structured
    )
    
    analyzer = SECAnalyzer(config)
    
    asyncio.run(_run_analysis(analyzer, ticker, forms.split(','), verbose))


@cli.command()
@click.argument('ticker')
@click.option('--output-dir', default='output', help='Output directory')
@click.option('--user-agent', default='Self federallyapproved@gmail.com', help='User agent for SEC requests')
def list_filings(ticker: str, output_dir: str, user_agent: str):
    """List available SEC filings for a ticker."""
    
    config = AnalyzerConfig(
        user_agent=user_agent,
        output_dir=Path(output_dir)
    )
    
    analyzer = SECAnalyzer(config)
    asyncio.run(_list_filings(analyzer, ticker))


@cli.command()
@click.argument('ticker')
@click.argument('accession_number')
@click.option('--output-dir', default='output', help='Output directory')
@click.option('--user-agent', default='Self federallyapproved@gmail.com', help='User agent for SEC requests')
@click.option('--formats', default='txt,json', help='Output formats')
def analyze_document(
    ticker: str, 
    accession_number: str, 
    output_dir: str, 
    user_agent: str,
    formats: str
):
    """Analyze a single SEC document by accession number."""
    
    config = AnalyzerConfig(
        user_agent=user_agent,
        output_dir=Path(output_dir),
        output_formats=formats.split(',')
    )
    
    analyzer = SECAnalyzer(config)
    asyncio.run(_analyze_single_document(analyzer, ticker, accession_number))


@cli.command()
@click.option('--output-dir', default='output', help='Output directory')
@click.option('--user-agent', default='Self federallyapproved@gmail.com', help='User agent for SEC requests')
def validate(output_dir: str, user_agent: str):
    """Validate SEC analyzer setup and connectivity."""
    
    config = AnalyzerConfig(
        user_agent=user_agent,
        output_dir=Path(output_dir)
    )
    
    analyzer = SECAnalyzer(config)
    asyncio.run(_validate_setup(analyzer))


@cli.command()
@click.argument('ticker')
@click.option('--output-dir', default='output', help='Output directory')
def summary(ticker: str, output_dir: str):
    """Show summary of processed documents for a ticker."""
    
    config = AnalyzerConfig(
        user_agent="Self federallyapproved@gmail.com",
        output_dir=Path(output_dir)
    )
    
    analyzer = SECAnalyzer(config)
    _show_summary(analyzer, ticker)


async def _run_analysis(
    analyzer: SECAnalyzer, 
    ticker: str, 
    forms: List[str], 
    verbose: bool
):
    """Run the main analysis workflow."""
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        
        task = progress.add_task("Validating setup...", total=None)
        validation = await analyzer.validate_setup()
        
        if not all(validation.values()):
            console.print("[red]Setup validation failed:[/red]")
            for check, result in validation.items():
                status = "[green]✓[/green]" if result else "[red]✗[/red]"
                console.print(f"  {status} {check.replace('_', ' ').title()}")
            return
        
        progress.update(task, description="Setup validated ✓")
        
        progress.update(task, description=f"Analyzing {ticker}...")
        
        try:
            result = await analyzer.analyze_ticker(ticker, forms)
            progress.remove_task(task)
            
            _display_results(result, verbose)
            
        except Exception as e:
            progress.remove_task(task)
            console.print(f"[red]Error during analysis: {e}[/red]")
            if verbose:
                console.print_exception()


async def _list_filings(analyzer: SECAnalyzer, ticker: str):
    """List available filings for a ticker."""
    
    try:
        with console.status(f"Fetching filings for {ticker}..."):
            filings = await analyzer.get_available_filings(ticker)
        
        if not filings:
            console.print(f"[yellow]No filings found for {ticker}[/yellow]")
            return
        
        table = Table(title=f"Available SEC Filings for {ticker}")
        table.add_column("Form Type", style="cyan")
        table.add_column("Filing Date", style="green")
        table.add_column("Accession Number", style="blue")
        table.add_column("Company Name", style="magenta")
        
        for filing in filings[:20]:  # Show first 20
            table.add_row(
                filing.form_type,
                filing.filing_date.strftime('%Y-%m-%d'),
                filing.accession_number,
                filing.company_name
            )
        
        console.print(table)
        
        if len(filings) > 20:
            console.print(f"[dim]... and {len(filings) - 20} more filings[/dim]")
            
    except Exception as e:
        console.print(f"[red]Error fetching filings: {e}[/red]")


async def _analyze_single_document(
    analyzer: SECAnalyzer, 
    ticker: str, 
    accession_number: str
):
    """Analyze a single document."""
    
    try:
        with console.status(f"Analyzing document {accession_number}..."):
            parsed_doc = await analyzer.analyze_single_document(ticker, accession_number)
        
        console.print(f"[green]Successfully processed document {accession_number}[/green]")
        console.print(f"Form Type: {parsed_doc.filing.form_type}")
        console.print(f"Company: {parsed_doc.filing.company_name}")
        console.print(f"Filing Date: {parsed_doc.filing.filing_date.strftime('%Y-%m-%d')}")
        console.print(f"Clean Text Length: {len(parsed_doc.clean_text):,} characters")
        console.print(f"Sections: {len(parsed_doc.sections)}")
        console.print(f"Tables: {len(parsed_doc.tables)}")
        
    except Exception as e:
        console.print(f"[red]Error analyzing document: {e}[/red]")


async def _validate_setup(analyzer: SECAnalyzer):
    """Validate analyzer setup."""
    
    with console.status("Validating setup..."):
        validation = await analyzer.validate_setup()
    
    console.print("[bold]Setup Validation Results:[/bold]")
    
    for check, result in validation.items():
        status = "[green]✓[/green]" if result else "[red]✗[/red]"
        console.print(f"  {status} {check.replace('_', ' ').title()}")
    
    if all(validation.values()):
        console.print("\n[green]All checks passed! SEC Analyzer is ready to use.[/green]")
    else:
        console.print("\n[red]Some checks failed. Please fix the issues above.[/red]")


def _display_results(result, verbose: bool):
    """Display analysis results."""
    
    console.print(f"\n[bold green]Analysis Complete for {result.ticker}[/bold green]")
    console.print(f"Company: {result.company_name}")
    console.print(f"CIK: {result.cik}")
    
    stats_table = Table(title="Processing Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="green")
    
    stats_table.add_row("Documents Downloaded", str(result.stats.documents_downloaded))
    stats_table.add_row("Documents Processed", str(result.stats.documents_processed))
    stats_table.add_row("Documents Failed", str(result.stats.documents_failed))
    stats_table.add_row("Total Text Length", f"{result.stats.total_text_length:,} chars")
    stats_table.add_row("Processing Time", f"{result.stats.processing_time_seconds:.2f} seconds")
    
    console.print(stats_table)
    
    if result.stats.forms_processed:
        console.print("\n[bold]Forms Processed:[/bold]")
        for form_type, count in result.stats.forms_processed.items():
            console.print(f"  {form_type}: {count} documents")
    
    if result.output_paths:
        console.print("\n[bold]Output Files Generated:[/bold]")
        for format_type, paths in result.output_paths.items():
            if paths:
                console.print(f"  {format_type.upper()}: {len(paths)} files")
                if verbose:
                    for path in paths[:3]:  # Show first 3
                        console.print(f"    {path}")
                    if len(paths) > 3:
                        console.print(f"    ... and {len(paths) - 3} more")
    
    if result.failed_documents:
        console.print(f"\n[yellow]Failed Documents ({len(result.failed_documents)}):[/yellow]")
        for filing in result.failed_documents[:5]:  # Show first 5
            console.print(f"  {filing.form_type} - {filing.accession_number}")
        if len(result.failed_documents) > 5:
            console.print(f"  ... and {len(result.failed_documents) - 5} more")


def _show_summary(analyzer: SECAnalyzer, ticker: str):
    """Show summary of processed documents."""
    
    summary = analyzer.get_output_summary(ticker)
    
    if not any(cat['file_count'] > 0 for cat in summary.values()):
        console.print(f"[yellow]No processed documents found for {ticker}[/yellow]")
        return
    
    console.print(f"[bold]Output Summary for {ticker}[/bold]")
    
    for category, info in summary.items():
        if info['file_count'] > 0:
            console.print(f"\n[cyan]{category.title()}:[/cyan] {info['file_count']} files")
            console.print(f"  Path: {info['path']}")
            if info['files']:
                for file in info['files'][:3]:  # Show first 3
                    console.print(f"    {file}")
                if len(info['files']) > 3:
                    console.print(f"    ... and {len(info['files']) - 3} more")


def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
