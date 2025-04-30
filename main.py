#!/usr/bin/env python3
"""
AI Project Analyzer - Analyze GitHub projects using LLMs
"""

import sys
import io

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors="replace")

import sys
import argparse
import logging
import time

from src.config import (
    setup_logging,
    get_default_model,
    get_default_temperature,
    get_default_log_level,
    get_github_token,
)
from src.fetcher import fetch_single_repository
from src.analyzer import analyze_single_repository, AVAILABLE_MODELS
from src.file_parser import parse_input_file


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analyze GitHub repositories using LLMs")

    # Create a group for input sources to handle mutual exclusivity
    input_group = parser.add_mutually_exclusive_group(required=True)

    input_group.add_argument(
        "--github-urls",
        type=str,
        help="Comma-separated list of GitHub repository URLs",
    )

    input_group.add_argument(
        "--input-file",
        type=str,
        help="Path to Excel (.xlsx) or CSV file containing GitHub repository URLs",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default="prompts/default.txt",
        help="Path to the prompt file (default: prompts/default.txt)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=get_default_log_level(),
        help=f"Set the logging level (default: {get_default_log_level()})",
    )

    # Add model selection
    parser.add_argument(
        "--model",
        type=str,
        choices=list(AVAILABLE_MODELS.keys()),
        default=get_default_model(),
        help=f"Gemini model to use for analysis (default: {get_default_model()})",
    )

    # Add temperature control
    parser.add_argument(
        "--temperature",
        type=float,
        default=get_default_temperature(),
        help=f"Temperature for generation (0.0-1.0, lower is more deterministic, default: {get_default_temperature()})",
    )

    # Add JSON output option
    parser.add_argument(
        "--json", action="store_true", help="Output analysis in JSON format instead of Markdown"
    )

    # Add GitHub token option
    parser.add_argument(
        "--github-token",
        type=str,
        default=get_github_token(),
        help="GitHub personal access token for API requests (can also be set with GITHUB_TOKEN env var)",
    )

    # Add option to disable metrics
    parser.add_argument(
        "--no-metrics", action="store_true", help="Disable GitHub metrics collection"
    )

    return parser.parse_args()


def format_analysis_output(repo_name, analysis, is_json=False):
    """Format the analysis output for display."""
    if is_json:
        return f"{repo_name} Analysis (JSON):\n{analysis}"
    else:
        return f"{repo_name} Analysis:\n{analysis}"


def main():
    """Main entry point for the application."""
    args = parse_args()

    # Setup logging
    setup_logging(args.log_level)

    # Parse GitHub URLs from args or input file
    github_urls = []

    if args.github_urls:
        # Parse comma-separated list
        github_urls = [url.strip() for url in args.github_urls.split(",")]
        logging.info(f"Found {len(github_urls)} GitHub URLs from command line arguments")
    elif args.input_file:
        # Parse from file
        logging.info(f"Parsing GitHub URLs from file: {args.input_file}")
        try:
            github_urls = parse_input_file(args.input_file)
            logging.info(f"Found {len(github_urls)} GitHub URLs from input file")
        except Exception as e:
            logging.error(f"Failed to parse input file: {str(e)}")
            return 1

    # Log start of analysis with selected model
    logging.info(f"Starting analysis with model: {args.model}, temperature: {args.temperature}")
    if args.json:
        logging.info("Using JSON output format")

    # Configure metrics collection
    include_metrics = not args.no_metrics
    if include_metrics:
        logging.info("GitHub metrics collection is enabled")
    else:
        logging.info("GitHub metrics collection is disabled")

    # Track total GitHub URLs and completed repositories
    total_repos = len(github_urls)
    completed_repos = 0
    all_analyses = {}
    start_time = time.time()

    # Process each repository individually
    for index, url in enumerate(github_urls, 1):
        logging.info(f"Processing repository {index}/{total_repos}: {url}")

        # Step 1: Fetch repository content and metrics
        repo_name, repo_data = fetch_single_repository(
            url, include_metrics=include_metrics, github_token=args.github_token
        )

        # Skip if fetch failed completely
        if not repo_data or not repo_data["content"] or repo_data["content"].startswith("Error:"):
            logging.error(f"Failed to fetch repository: {url}")
            continue

        # Step 2: Analyze repository
        code_digest = repo_data["content"]
        metrics = repo_data.get("metrics", {})

        analysis = analyze_single_repository(
            repo_name,
            code_digest,
            args.prompt,
            model_name=args.model,
            temperature=args.temperature,
            output_json=args.json,
            metrics_data=metrics,
        )

        # Store analysis and print to user
        completed_repos += 1
        all_analyses[repo_name] = analysis
        
        # Print the analysis results directly to the user
        print("\n" + "="*80)
        print(format_analysis_output(repo_name, analysis, args.json))
        print("="*80 + "\n")

        # Print progress indicator
        progress_percentage = (completed_repos / total_repos) * 100
        bar_length = 40
        filled_length = int(bar_length * completed_repos // total_repos)
        progress_bar = "#" * filled_length + "-" * (bar_length - filled_length)

        print(f"\n[{progress_bar}] {completed_repos}/{total_repos} ({progress_percentage:.1f}%)")
        print(f"Completed analysis of: {repo_name}")

        # Estimate time remaining
        if completed_repos < total_repos:
            elapsed_time = time.time() - start_time
            avg_time_per_repo = elapsed_time / completed_repos
            estimated_remaining = avg_time_per_repo * (total_repos - completed_repos)

            # Format the time nicely
            mins, secs = divmod(estimated_remaining, 60)
            time_str = f"{int(mins)}m {int(secs)}s"
            print(f"Estimated time remaining: {time_str}")

    # Final stats
    logging.info(f"Completed analysis of {completed_repos}/{total_repos} repositories")

    if completed_repos == 0:
        logging.error("No repositories were successfully analyzed. Exiting.")
        return 1

    # Print summary of all analyses
    print("\n" + "="*80)
    print("SUMMARY OF ALL ANALYSES")
    print("="*80)
    for repo_name, analysis in all_analyses.items():
        print("\n" + "-"*40)
        print(f"Repository: {repo_name}")
        print("-"*40)
        print(format_analysis_output(repo_name, analysis, args.json))

    # Print execution time
    total_time = time.time() - start_time
    mins, secs = divmod(total_time, 60)
    print(f"\nTotal execution time: {int(mins)} minutes, {int(secs)} seconds")

    logging.info("Analysis complete!")
    return all_analyses  # Return the analyses dictionary


if __name__ == "__main__":
    # When run directly, we'll print the results and exit with status code
    result = main()
    sys.exit(0 if result else 1)