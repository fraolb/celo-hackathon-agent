"""
CLI module for the AI Project Analyzer.

This module provides the Click CLI interface.
"""

import logging
import time
import os
import click
from colorama import Fore, Style, init
from src.config import setup_logging
from src.fetcher import fetch_repositories
from src.analyzer import analyze_repositories, AVAILABLE_MODELS
from src.reporter import save_reports

# Initialize colorama
init()

logger = logging.getLogger(__name__)

def print_color(text, color=Fore.WHITE, bold=False):
    """Helper function for colored output"""
    style = Style.BRIGHT if bold else Style.NORMAL
    print(f"{style}{color}{text}{Style.RESET_ALL}")

@click.command()
@click.option('--github-urls', required=True, help="Comma-separated list of GitHub repository URLs")
@click.option('--prompt', '-p', default="prompts/default.txt", help="Path to the prompt file")
@click.option('--output', '-o', default="reports", help="Directory to save reports")
@click.option('--log-level', '-l', default="INFO", 
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
              help="Set the logging level")
@click.option('--model', '-m', default="gemini-2.0-flash", help="Gemini model to use for analysis")
@click.option('--temperature', '-t', default=0.2, type=float, 
              help="Temperature for generation (0.0-1.0, lower is more deterministic)")
@click.option('--json', '-j', is_flag=True, help="Output analysis in JSON format instead of Markdown")
def analyze(github_urls, prompt, output, log_level, model, temperature, json):
    """
    Analyze GitHub repositories using LLMs.
    """
    # Start timing
    start_time = time.time()

    # Setup logging
    setup_logging(log_level)

    # Validate model
    if model not in AVAILABLE_MODELS:
        available_models = ", ".join(AVAILABLE_MODELS.keys())
        print_color(f"Error: Invalid model '{model}'. Available models: {available_models}", 
                  Fore.RED, bold=True)
        return

    # Parse GitHub URLs
    urls = [url.strip() for url in github_urls.split(",")]

    # Display analysis details
    print_color("AI Project Analyzer", bold=True)
    print_color(f"Model: {model} (Temperature: {temperature})", Fore.CYAN)
    print_color(f"Output format: {'JSON' if json else 'Markdown'}", Fore.CYAN)
    print_color(f"Repositories to analyze: {len(urls)}", Fore.CYAN)

    # Fetch repository digests
    print_color("Fetching repositories...", Fore.GREEN)
    logger.info(f"Fetching {len(urls)} repositories: {', '.join(urls)}")
    repo_digests = fetch_repositories(urls)

    if not repo_digests:
        print_color("Error: No repositories were successfully fetched.", Fore.RED, bold=True)
        return

    # Analyze repositories
    print_color(f"\nAnalyzing {len(repo_digests)} repositories...", Fore.CYAN)
    analyses = analyze_repositories(
        repo_digests,
        prompt,
        model_name=model,
        temperature=temperature,
        output_json=json,
    )

    if not analyses:
        print_color("Error: No repositories were successfully analyzed.", Fore.RED, bold=True)
        return

    # Save reports
    print_color("\nSaving analysis reports...", Fore.GREEN)
    report_paths = save_reports(analyses, output)

    # Print summary
    print_color("\nAnalysis Complete!", Fore.GREEN, bold=True)

    # Show summary report if it exists
    if "__summary__" in report_paths:
        summary_path = report_paths["__summary__"]
        print_color(f"\nSummary Report: {summary_path}", Fore.YELLOW, bold=True)

    # List individual reports
    print_color("\nIndividual Reports:", bold=True)
    for repo_name, report_path in report_paths.items():
        if repo_name != "__summary__":
            print_color(f"- {repo_name}: {report_path}", Fore.CYAN)

    # Print output directory info
    output_dir = os.path.dirname(next(iter(report_paths.values())))
    print_color(f"\nAll reports saved to: {output_dir}", bold=True)

    # Log execution time
    end_time = time.time()
    duration = end_time - start_time
    print_color(f"\nTotal execution time: {duration:.2f} seconds", bold=True)
    logger.info(f"Total execution time: {duration:.2f} seconds")

if __name__ == "__main__":
    analyze()