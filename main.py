import os
import json
import pandas as pd
import argparse
import time
import logging
import sys
from github_analyzer import GitHubLangChainAnalyzer
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv
from tqdm import tqdm

# Set up logging
# File handler for detailed logging
file_handler = logging.FileHandler("analysis.log")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.DEBUG)

# Console handler for minimal logging (only errors by default)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(message)s'))
console_handler.setLevel(logging.ERROR)  # Only show errors in console by default

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Suppress logging from other libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)

# Load environment variables from .env file
load_dotenv()

# Spinner animation for CLI
class Spinner:
    def __init__(self, message="Loading"):
        self.message = message
        # Simple spinner frames that work consistently across terminals
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.fallback_frames = ["-", "\\", "|", "/"]  # Fallback if unicode doesn't display well
        self.delay = 0.1
        self.is_spinning = False
        self.index = 0
        self.start_time = time.time()
        # Color setup
        self.colors = {
            'reset': '\033[0m',
            'bold': '\033[1m',
            'green': '\033[92m',
            'blue': '\033[94m',
            'cyan': '\033[96m',
            'yellow': '\033[93m',
            'magenta': '\033[95m'
        }
        
        # Choose the appropriate frame set based on terminal capability
        try:
            # Try printing a unicode character
            print("\u2588", end="", flush=True)
            print("\r", end="", flush=True)  # Clear the test character
            self.current_frames = self.frames
        except UnicodeEncodeError:
            # Fall back to simple ASCII frames if unicode isn't supported
            self.current_frames = self.fallback_frames
        
    def start(self):
        self.is_spinning = True
        self.start_time = time.time()
        
        # Clear the line first
        print("\r" + " " * 120, end="", flush=True)
        
        spinner = f"{self.colors['cyan']}{self.current_frames[self.index]}{self.colors['reset']}"
        message = f"{self.colors['bold']}{self.message}{self.colors['reset']}"
        print(f"\r{spinner} {message}", end="", flush=True)
        
    def update(self, message=None):
        if message:
            self.message = message
            
        # Update animation frame
        self.index = (self.index + 1) % len(self.current_frames)
        
        # Calculate elapsed time
        elapsed = time.time() - self.start_time
        
        # Get current message or use the one passed in
        current_message = self.message if message is None else message
        
        # Check if message contains elapsed time already
        if "running for" in current_message or "completed in" in current_message:
            # Message already contains timing information
            display_message = current_message
        else:
            # Add timing information
            display_message = f"{current_message} ({elapsed:.1f}s)"
        
        # Clear line completely first
        print("\r" + " " * 120, end="", flush=True)
        
        # Format with colors
        spinner = f"{self.colors['cyan']}{self.current_frames[self.index]}{self.colors['reset']}"
        formatted_message = f"{self.colors['bold']}{display_message}{self.colors['reset']}"
        
        # Print the spinner and message
        print(f"\r{spinner} {formatted_message}", end="", flush=True)
        
        # Make animations smoother by adding small delay
        time.sleep(0.05)
        
    def stop(self, message=None):
        final_message = message if message else self.message
        elapsed = time.time() - self.start_time
        
        # Clear line completely first
        print("\r" + " " * 120, end="", flush=True)
        
        # Choose icon based on message content
        if "Error" in final_message or "error" in final_message or "failed" in final_message:
            icon = f"{self.colors['yellow']}⚠️{self.colors['reset']}"  # Warning for errors
        else:
            icon = f"{self.colors['green']}✓{self.colors['reset']}"  # Checkmark for success
        
        message = f"{self.colors['bold']}{final_message}{self.colors['reset']}"
        elapsed_text = f"{self.colors['yellow']}(completed in {elapsed:.1f}s){self.colors['reset']}"
        
        print(f"\r{icon} {message} {elapsed_text}")
        self.is_spinning = False


def load_projects(excel_path: str) -> pd.DataFrame:
    """
    Load projects from Excel file.

    Args:
        excel_path: Path to Excel file

    Returns:
        DataFrame containing project data
    """
    spinner = Spinner(f"Loading projects from {excel_path}")
    spinner.start()
    
    try:
        logger.info(f"Loading project data from Excel file: {excel_path}")
        df = pd.read_excel(excel_path)
        required_columns = [
            "project_name",
            "project_description",
            "project_github_url",
            "project_owner_github_url",
            "project_url",
        ]

        # Check if required columns exist
        for col in required_columns:
            if col not in df.columns:
                spinner.stop(f"Error: Missing column {col}")
                raise ValueError(f"Missing required column: {col}")

        project_count = len(df)
        spinner.stop(f"Successfully loaded {project_count} projects from {excel_path}")
        logger.info(f"Successfully loaded {project_count} projects")
        return df
    except Exception as e:
        error_msg = f"Error loading project data: {str(e)}"
        spinner.stop(f"Failed to load projects: {str(e)}")
        logger.error(error_msg)
        raise Exception(error_msg)


def analyze_projects(
    projects_df: pd.DataFrame, config_path: str = "config.json"
) -> List[Dict[str, Any]]:
    """
    Analyze projects from DataFrame.

    Args:
        projects_df: DataFrame containing project data
        config_path: Path to configuration file

    Returns:
        List of dictionaries containing analysis results
    """
    total_projects = len(projects_df)
    logger.info(f"Starting analysis of {total_projects} projects")
    
    # Initialize progress bar with custom colors and format
    progress_bar = tqdm(
        total=total_projects,
        desc="Analyzing Projects",
        bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        ncols=80,
        colour="green"
    )
    
    analyzer = GitHubLangChainAnalyzer(config_path)
    results = []

    for index, row in projects_df.iterrows():
        project_name = row["project_name"]
        project_description = row["project_description"]
        raw_github_urls = row["project_github_url"]
        
        # Update progress bar description - keep it simple
        progress_bar.set_description(f"Analyzing Projects")
        
        # Get project_owner_github_url (comma-separated GitHub user URLs)
        # This field contains GitHub URLs of the project owners/developers
        raw_owner_urls = row["project_owner_github_url"]
        
        # Process owner GitHub URLs (handle comma-separated URLs)
        owner_github_urls = []
        if isinstance(raw_owner_urls, str):
            # Split by comma and strip whitespace
            owner_github_urls = [url.strip() for url in raw_owner_urls.split(',') if url.strip()]
        elif pd.notna(raw_owner_urls):  # Check if it's not NaN
            # If it's not a string (might be a single URL without commas)
            owner_github_urls = [str(raw_owner_urls)]
        # Otherwise, leave as empty list
        project_url = row["project_url"]
        
        # Process the GitHub URLs (handle comma-separated URLs)
        github_urls = []
        if isinstance(raw_github_urls, str):
            # Split by comma and strip whitespace
            github_urls = [url.strip() for url in raw_github_urls.split(',') if url.strip()]
        else:
            # If it's not a string (might be a single URL without commas or NaN)
            if pd.notna(raw_github_urls):
                github_urls = [str(raw_github_urls)]
        
        # If no valid GitHub URLs, create a default result and continue
        if not github_urls:
            logger.warning(f"No valid GitHub URLs found for project {project_name}")
            
            # Create a default result with error
            project_result = {
                "project_name": project_name,
                "project_description": project_description,
                "project_github_url": "No valid GitHub URL provided",
                "project_owner_github_url": owner_github_urls,
                "project_url": project_url,
                "analysis": {
                    "error": "No valid GitHub URL provided",
                    "code_quality": 0,
                    "celo_integration": False
                }
            }
            
            results.append(project_result)
            progress_bar.update(1)
            continue
        
        # Log the analysis
        logger.info(f"Analyzing project {index+1}/{total_projects}: {project_name} with {len(github_urls)} repo(s)")
        
        # Initialize combined analysis results
        combined_analysis = {
            "repo_details": [],
            "code_quality": {"overall_score": 0, "repositories_analyzed": 0},
            "celo_integration": {"integrated": False, "evidence": [], "repositories_with_celo": 0}
        }
        
        # Create a spinner
        spinner = Spinner(f"Analyzing {len(github_urls)} GitHub repositories for {project_name}")
        spinner.start()
        
        # Analyze each GitHub repository
        for url_index, github_url in enumerate(github_urls):
            try:
                # Skip empty URLs
                if not github_url or not github_url.startswith('http'):
                    logger.warning(f"Skipping invalid URL: {github_url}")
                    continue
                
                # Update spinner with current repo
                spinner.update(f"Analyzing repository {url_index+1}/{len(github_urls)}: {github_url}")
                
                # Define a callback function to update the spinner
                def progress_callback(message):
                    # The spinner's update method now includes animation
                    updated_message = f"[{url_index+1}/{len(github_urls)}] {message}"
                    spinner.update(updated_message)
                    
                    # Helper for manual animation during long operations
                    if "Analyzing" in message or "Checking" in message:
                        # Manually force a few extra animation frames to show activity
                        for _ in range(3):
                            time.sleep(0.1)
                            spinner.update(updated_message)
                
                # Analyze repository with progress updates
                repo_analysis = analyzer.analyze_repository(
                    github_url, 
                    callback=progress_callback
                )
                
                # Store repo details
                if "repo_details" in repo_analysis:
                    combined_analysis["repo_details"].append(repo_analysis["repo_details"])
                
                # Update combined code quality score
                if "code_quality" in repo_analysis:
                    quality = repo_analysis["code_quality"]
                    if isinstance(quality, dict) and "overall_score" in quality:
                        # Increment count and add to total score
                        combined_analysis["code_quality"]["repositories_analyzed"] += 1
                        combined_analysis["code_quality"]["overall_score"] += quality["overall_score"]
                
                # Update Celo integration status
                if "celo_integration" in repo_analysis:
                    celo_integration = repo_analysis["celo_integration"]
                    if isinstance(celo_integration, dict) and "integrated" in celo_integration:
                        if celo_integration["integrated"]:
                            # Mark project as Celo-integrated if any repo is integrated
                            combined_analysis["celo_integration"]["integrated"] = True
                            combined_analysis["celo_integration"]["repositories_with_celo"] += 1
                            
                            # Append evidence if available
                            if "evidence" in celo_integration and celo_integration["evidence"]:
                                # Add repo name to evidence for clarity
                                for evidence in celo_integration["evidence"]:
                                    evidence["repository"] = github_url
                                combined_analysis["celo_integration"]["evidence"].extend(celo_integration["evidence"])
            
            except Exception as e:
                logger.error(f"Error analyzing {github_url}: {str(e)}")
                spinner.update(f"Error analyzing {github_url}: {str(e)}")
        
        # Calculate the average code quality score if we analyzed any repositories
        if combined_analysis["code_quality"]["repositories_analyzed"] > 0:
            avg_score = combined_analysis["code_quality"]["overall_score"] / combined_analysis["code_quality"]["repositories_analyzed"]
            combined_analysis["code_quality"]["overall_score"] = avg_score
        
        # Clear the line first to avoid overlap issues
        print(f"\r{' ' * 100}", end="", flush=True)
        
        # Final update when done
        spinner.stop(f"Completed analysis of {len(github_urls)} repositories for {project_name}")
        
        # Combine project info with analysis results
        project_result = {
            "project_name": project_name,
            "project_description": project_description,
            "project_github_url": raw_github_urls,  # Keep the original value
            "github_urls": github_urls,  # Add the list of URLs
            "project_owner_github_url": owner_github_urls,
            "project_url": project_url,
            "analysis": combined_analysis,
        }

        results.append(project_result)
        
        # Basic success message
        logger.info(f"Successfully analyzed {project_name}")
            
        # Log code quality score and Celo integration status
        if "code_quality" in combined_analysis:
            score = combined_analysis["code_quality"].get("overall_score", 0)
            repos_analyzed = combined_analysis["code_quality"].get("repositories_analyzed", 0)
            logger.info(f"Code quality score for {project_name}: {score:.2f}/100 (based on {repos_analyzed} repositories)")
                    
        # Log Celo integration status
        if "celo_integration" in combined_analysis:
            is_integrated = combined_analysis["celo_integration"].get("integrated", False)
            repos_with_celo = combined_analysis["celo_integration"].get("repositories_with_celo", 0)
            logger.info(f"Celo integration for {project_name}: {'Yes' if is_integrated else 'No'} ({repos_with_celo}/{len(github_urls)} repositories)")
        
        # Update progress bar
        progress_bar.update(1)
        
    # Close progress bar
    progress_bar.close()
    # Add space after progress bar
    print("")
    logger.info(f"Completed analysis of all {total_projects} projects")
    
    return results


def generate_report(results: List[Dict[str, Any]], output_dir: str = "reports") -> None:
    """
    Generate Markdown reports from analysis results.

    Args:
        results: List of dictionaries containing analysis results
        output_dir: Directory to save reports
    """
    # Create a spinner for report generation
    spinner = Spinner(f"Generating reports in {output_dir} directory")
    spinner.start()
    
    logger.info(f"Starting report generation for {len(results)} projects")
    
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate summary report
        spinner.update(f"Creating summary report")
        logger.info(f"Generating summary report in {output_dir}")
        
        summary_path = os.path.join(output_dir, "summary.md")
        with open(summary_path, "w") as f:
            f.write("# Celo Hackathon Project Analysis Summary\n\n")
            f.write("| Project | Score | Celo Integration | GitHub URL |\n")
            f.write("|---------|-------|------------------|------------|\n")

            for result in results:
                project_name = result["project_name"]
                
                # Handle multiple GitHub URLs
                if "github_urls" in result and result["github_urls"]:
                    # For multiple URLs, show the first one with a link and note the count
                    github_urls = result["github_urls"]
                    if len(github_urls) > 1:
                        github_url_display = f"[{github_urls[0]}]({github_urls[0]}) +{len(github_urls)-1} more"
                    else:
                        github_url_display = f"[{github_urls[0]}]({github_urls[0]})"
                else:
                    # Fallback to the original field if github_urls isn't available
                    github_url = result["project_github_url"]
                    github_url_display = f"[{github_url}]({github_url})"

                # Get code quality score
                if "analysis" in result and "code_quality" in result["analysis"]:
                    code_quality = result["analysis"]["code_quality"]
                    if isinstance(code_quality, dict) and "overall_score" in code_quality:
                        score = code_quality["overall_score"]
                        repos_analyzed = code_quality.get("repositories_analyzed", 1)
                        # Add repository count if multiple repositories
                        score_display = f"{score:.2f}" if repos_analyzed <= 1 else f"{score:.2f} ({repos_analyzed} repos)"
                    elif isinstance(code_quality, (int, float)):
                        score = code_quality
                        score_display = f"{score:.2f}"
                    else:
                        score = 0
                        score_display = "0.00"
                else:
                    score = 0
                    score_display = "0.00"

                # Get Celo integration status
                if "analysis" in result and "celo_integration" in result["analysis"]:
                    celo_integration = result["analysis"]["celo_integration"]
                    if isinstance(celo_integration, dict) and "integrated" in celo_integration:
                        celo_integrated = celo_integration["integrated"]
                        repos_with_celo = celo_integration.get("repositories_with_celo", 0)
                    elif isinstance(celo_integration, bool):
                        celo_integrated = celo_integration
                        repos_with_celo = 1 if celo_integrated else 0
                    else:
                        celo_integrated = False
                        repos_with_celo = 0
                    
                    # Show Celo integration status with repository count if multiple repositories
                    if "github_urls" in result and len(result["github_urls"]) > 1:
                        celo_status = f"{'✅' if celo_integrated else '❌'} ({repos_with_celo}/{len(result['github_urls'])})"
                    else:
                        celo_status = "✅" if celo_integrated else "❌"
                else:
                    celo_status = "❌"

                f.write(
                    f"| {project_name} | {score_display} | {celo_status} | {github_url_display} |\n"
                )
        
        # Initialize progress bar for individual reports with custom colors and format
        progress_bar = tqdm(
            total=len(results),
            desc="Generating Reports",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            ncols=80,
            colour="blue"
        )

        # Generate individual reports
        for idx, result in enumerate(results):
            project_name = result["project_name"]
            file_name = project_name.replace(" ", "_").lower()
            report_path = os.path.join(output_dir, f"{file_name}.md")
            
            # Keep the progress description simple
            progress_bar.set_description(f"Generating Reports")
            
            # Log progress
            logger.info(f"Creating report for {project_name} ({idx+1}/{len(results)})")

            with open(report_path, "w") as f:
                f.write(f"# Project Analysis: {result['project_name']}\n\n")

                # Project Overview
                f.write("## Project Overview\n\n")
                f.write(f"**Project Name:** {result['project_name']}\n\n")
                f.write(f"**Project Description:** {result['project_description']}\n\n")
                
                # Handle None/NaN project_url
                project_url = result['project_url']
                if project_url is None or isinstance(project_url, float) and pd.isna(project_url):
                    f.write(f"**Project URL:** Not available\n\n")
                else:
                    f.write(f"**Project URL:** [{project_url}]({project_url})\n\n")
                
                # Add GitHub profiles of project owners/developers
                if "project_owner_github_url" in result and result["project_owner_github_url"]:
                    owner_urls = result["project_owner_github_url"]
                    if len(owner_urls) == 1:
                        f.write(f"**Project Developer:** [{owner_urls[0]}]({owner_urls[0]})\n\n")
                    elif len(owner_urls) > 1:
                        f.write(f"**Project Developers:**\n\n")
                        for i, url in enumerate(owner_urls):
                            f.write(f"{i+1}. [{url}]({url})\n")
                        f.write("\n")
                
                # Handle multiple GitHub URLs
                if "github_urls" in result and result["github_urls"]:
                    # List all GitHub URLs
                    github_urls = result["github_urls"]
                    if len(github_urls) == 1:
                        f.write(f"**GitHub URL:** [{github_urls[0]}]({github_urls[0]})\n\n")
                    else:
                        f.write(f"**GitHub URLs:** ({len(github_urls)} repositories)\n\n")
                        for i, url in enumerate(github_urls):
                            f.write(f"{i+1}. [{url}]({url})\n")
                        f.write("\n")
                else:
                    # Fallback to original format
                    f.write(f"**GitHub URL:** [{result['project_github_url']}]({result['project_github_url']})\n\n")

                # Repository details - handle multiple repositories
                if "analysis" in result and "repo_details" in result["analysis"]:
                    repo_details = result["analysis"]["repo_details"]
                    
                    # Check if we have multiple repositories
                    if isinstance(repo_details, list) and len(repo_details) > 0:
                        f.write("### Repository Statistics\n\n")
                        
                        if len(repo_details) == 1:
                            # Single repository - show simple stats
                            repo = repo_details[0]
                            f.write(f"- **Repository:** {repo.get('name', 'N/A')}\n")
                            f.write(f"- **Stars:** {repo.get('stars', 'N/A')}\n")
                            f.write(f"- **Forks:** {repo.get('forks', 'N/A')}\n")
                            f.write(f"- **Open Issues:** {repo.get('open_issues', 'N/A')}\n")
                            f.write(f"- **Primary Language:** {repo.get('language', 'N/A')}\n")
                            f.write(f"- **Last Updated:** {repo.get('last_update', 'N/A')}\n\n")
                        else:
                            # Multiple repositories - create a summary table
                            f.write("| Repository | Stars | Forks | Issues | Language | Last Updated |\n")
                            f.write("|------------|-------|-------|--------|----------|-------------|\n")
                            
                            for repo in repo_details:
                                repo_name = repo.get('name', 'N/A')
                                stars = repo.get('stars', 0)
                                forks = repo.get('forks', 0)
                                issues = repo.get('open_issues', 0)
                                language = repo.get('language', 'N/A')
                                last_update = repo.get('last_update', 'N/A')
                                if last_update and len(last_update) > 10:
                                    # Simplify date format for table
                                    last_update = last_update.split('T')[0]
                                
                                f.write(f"| {repo_name} | {stars} | {forks} | {issues} | {language} | {last_update} |\n")
                            f.write("\n")
                    elif isinstance(repo_details, dict):
                        # Single repository in old format
                        f.write("### Repository Statistics\n\n")
                        f.write(f"- **Stars:** {repo_details.get('stars', 'N/A')}\n")
                        f.write(f"- **Forks:** {repo_details.get('forks', 'N/A')}\n")
                        f.write(f"- **Open Issues:** {repo_details.get('open_issues', 'N/A')}\n")
                        f.write(f"- **Primary Language:** {repo_details.get('language', 'N/A')}\n")
                        f.write(f"- **Last Updated:** {repo_details.get('last_update', 'N/A')}\n\n")

                # Code Quality
                f.write("## Code Quality Assessment\n\n")

                if "analysis" in result and "code_quality" in result["analysis"]:
                    quality = result["analysis"]["code_quality"]

                    if isinstance(quality, (int, float)):
                        # If code_quality is just a number
                        f.write(f"**Overall Score:** {quality:.2f}/100\n\n")
                    elif isinstance(quality, dict):
                        if "error" in quality:
                            f.write(f"**Error:** {quality['error']}\n\n")
                        else:
                            # Check if we have multiple repository info
                            repos_analyzed = quality.get("repositories_analyzed", 0)
                            
                            # Safely get values with proper type checking
                            overall_score = quality.get("overall_score", 0)
                            if isinstance(overall_score, (int, float)):
                                if repos_analyzed > 1:
                                    f.write(f"**Overall Score:** {overall_score:.2f}/100 (average of {repos_analyzed} repositories)\n\n")
                                else:
                                    f.write(f"**Overall Score:** {overall_score:.2f}/100\n\n")
                            else:
                                f.write(f"**Overall Score:** 0.00/100\n\n")
                            
                            readability = quality.get("readability", 0)
                            if isinstance(readability, (int, float)):
                                f.write(f"**Readability and Documentation:** {readability:.2f}/100\n\n")
                            else:
                                f.write(f"**Readability and Documentation:** 0.00/100\n\n")
                            
                            standards = quality.get("standards", 0)
                            if isinstance(standards, (int, float)):
                                f.write(f"**Coding Standards and Best Practices:** {standards:.2f}/100\n\n")
                            else:
                                f.write(f"**Coding Standards and Best Practices:** 0.00/100\n\n")
                            
                            complexity = quality.get("complexity", 0)
                            if isinstance(complexity, (int, float)):
                                f.write(f"**Algorithm Complexity and Efficiency:** {complexity:.2f}/100\n\n")
                            else:
                                f.write(f"**Algorithm Complexity and Efficiency:** 0.00/100\n\n")
                            
                            testing = quality.get("testing", 0)
                            if isinstance(testing, (int, float)):
                                f.write(f"**Testing and Coverage:** {testing:.2f}/100\n\n")
                            else:
                                f.write(f"**Testing and Coverage:** 0.00/100\n\n")
                    else:
                        f.write(f"**Overall Score:** 0.00/100\n\n")

                        # AI Analysis if available
                        if "ai_analysis" in quality:
                            f.write("### AI Analysis\n\n")
                            ai_analysis = quality["ai_analysis"]
                            
                            if "overall_analysis" in ai_analysis:
                                f.write(f"**Overall Analysis:** {ai_analysis['overall_analysis']}\n\n")
                                
                            if "suggestions" in ai_analysis and ai_analysis["suggestions"]:
                                f.write("**Suggestions for Improvement:**\n\n")
                                for suggestion in ai_analysis["suggestions"]:
                                    f.write(f"- {suggestion}\n")
                                f.write("\n")
                                
                            if "readability_reasoning" in ai_analysis:
                                f.write(f"**Readability Assessment:** {ai_analysis['readability_reasoning']}\n\n")
                                
                            if "standards_reasoning" in ai_analysis:
                                f.write(f"**Standards Assessment:** {ai_analysis['standards_reasoning']}\n\n")
                                
                            if "complexity_reasoning" in ai_analysis:
                                f.write(f"**Complexity Assessment:** {ai_analysis['complexity_reasoning']}\n\n")
                                
                            if "testing_reasoning" in ai_analysis:
                                f.write(f"**Testing Assessment:** {ai_analysis['testing_reasoning']}\n\n")
                        
                        # Metrics
                        if "metrics" in quality:
                            f.write("### Metrics\n\n")
                            metrics = quality["metrics"]
                            f.write(
                                f"- **Total Files:** {metrics.get('file_count', 'N/A')}\n"
                            )
                            f.write(
                                f"- **Test Files:** {metrics.get('test_file_count', 'N/A')}\n"
                            )
                            f.write(
                                f"- **Documentation Files:** {metrics.get('doc_file_count', 'N/A')}\n"
                            )
                            
                            if "code_lines" in metrics:
                                f.write(
                                    f"- **Lines of Code:** {metrics.get('code_lines', 'N/A')}\n"
                                )
                            
                            if "comment_lines" in metrics:
                                f.write(
                                    f"- **Comment Lines:** {metrics.get('comment_lines', 'N/A')}\n"
                                )
                                
                            if "code_files_analyzed" in metrics:
                                f.write(
                                    f"- **Code Files Analyzed:** {metrics.get('code_files_analyzed', 'N/A')}\n"
                                )
                            
                            f.write("\n")
                else:
                    f.write(
                        "Could not assess code quality due to an error or inaccessible repository.\n\n"
                    )

                # Celo Integration
                f.write("## Celo Blockchain Integration\n\n")

                if "analysis" in result and "celo_integration" in result["analysis"]:
                    celo = result["analysis"]["celo_integration"]

                    if isinstance(celo, bool):
                        # If celo_integration is just a boolean
                        integration_status = "Yes" if celo else "No"
                        f.write(f"**Integrated with Celo:** {integration_status}\n\n")
                    elif isinstance(celo, dict):
                        if "error" in celo:
                            f.write(f"**Error:** {celo['error']}\n\n")
                        else:
                            # Get integration status safely
                            if "integrated" in celo:
                                integrated = celo["integrated"]
                                # Check if we have multiple repository data
                                repos_with_celo = celo.get("repositories_with_celo", 0)
                                repos_analyzed = 1  # Default for backward compatibility
                                
                                # Check if we can determine total repositories analyzed
                                if "github_urls" in result and result["github_urls"]:
                                    repos_analyzed = len(result["github_urls"])
                            else:
                                integrated = False
                                repos_with_celo = 0
                                repos_analyzed = 1
                                
                            # Format integration status with repository counts if multiple repos
                            if repos_analyzed > 1:
                                integration_status = f"{'Yes' if integrated else 'No'} ({repos_with_celo}/{repos_analyzed} repositories)"
                            else:
                                integration_status = "Yes" if integrated else "No"

                            f.write(f"**Integrated with Celo:** {integration_status}\n\n")

                            if integrated and "evidence" in celo and isinstance(celo["evidence"], list):
                                f.write("### Evidence of Integration\n\n")
                                for evidence in celo["evidence"]:
                                    if isinstance(evidence, dict) and "keyword" in evidence and "file" in evidence:
                                        # Check if evidence includes repository information
                                        if "repository" in evidence:
                                            f.write(
                                                f"- Found keyword '{evidence['keyword']}' in file: {evidence['file']} (Repository: {evidence['repository']})\n"
                                            )
                                        else:
                                            f.write(
                                                f"- Found keyword '{evidence['keyword']}' in file: {evidence['file']}\n"
                                            )
                                f.write("\n")
                            
                            # Add AI analysis of Celo integration if available
                            if integrated and "analysis" in celo:
                                f.write("### Integration Analysis\n\n")
                                f.write(f"{celo['analysis']}\n\n")
                    else:
                        # Default case if celo_integration is something unexpected
                        f.write(f"**Integrated with Celo:** No\n\n")
                else:
                    f.write(
                        "Could not assess Celo integration due to an error or inaccessible repository.\n\n"
                    )

                # Additional Notes
                f.write("## Additional Notes\n\n")

                if "analysis" in result and "error" in result["analysis"]:
                    f.write(f"- {result['analysis']['error']}\n")
                else:
                    f.write("No additional notes.\n")
            
            # Update progress bar
            progress_bar.update(1)
        
        # Close progress bar
        progress_bar.close()
        # Add space after progress bar
        print("")
        
        # Save raw results to JSON
        spinner.update(f"Saving raw results to JSON")
        logger.info(f"Saving raw results to {output_dir}/results.json")
        with open(os.path.join(output_dir, "results.json"), "w") as f:
            json.dump(results, f, indent=2)
        
        # Final spinner update
        spinner.stop(f"Successfully generated all reports in {output_dir}")
        logger.info(f"Report generation completed successfully")
        
    except Exception as e:
        error_msg = f"Error generating reports: {str(e)}"
        spinner.stop(f"Error generating reports: {str(e)}")
        logger.error(error_msg)
        raise Exception(error_msg)


def main():
    """Main function to run the analysis."""
    # Colors for styling
    colors = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'green': '\033[92m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'yellow': '\033[93m',
        'magenta': '\033[95m'
    }
    
    # Show a smaller, cleaner banner
    banner = f"""
    {colors['cyan']}╔═════════════════════════════════════════════════════╗
    ║ {colors['yellow']}CELO HACKATHON PROJECT ANALYZER{colors['cyan']}                  ║
    ╚═════════════════════════════════════════════════════╝{colors['reset']}
    
    {colors['bold']}A tool to analyze GitHub repositories for code quality 
    and Celo blockchain integration.{colors['reset']}
    """
    print(banner)
    
    # Setup argument parser
    parser = argparse.ArgumentParser(
        description="Analyze GitHub projects for Celo hackathon"
    )
    parser.add_argument(
        "--excel", required=True, help="Path to Excel file containing project data"
    )
    parser.add_argument(
        "--config", default="config.json", help="Path to configuration file"
    )
    parser.add_argument("--output", default="reports", help="Directory to save reports")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    
    # Set logging level based on verbosity
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Print startup information in a cleaner format
    print(f"{colors['bold']}Configuration:{colors['reset']}")
    print(f"  {colors['cyan']}📊 Input:{colors['reset']} {args.excel}")
    print(f"  {colors['cyan']}⚙️  Config:{colors['reset']} {args.config}")
    print(f"  {colors['cyan']}📁 Output:{colors['reset']} {args.output}")
    
    print(f"\n{colors['yellow']}Starting analysis...{colors['reset']}\n")
    
    start_time = time.time()
    
    try:
        # Create a global spinner for overall progress
        spinner = Spinner("Initializing analysis")
        spinner.start()
        
        # Load projects from Excel
        spinner.update("Loading project data from Excel")
        projects_df = load_projects(args.excel)
        
        # Update spinner with project count
        project_count = len(projects_df)
        spinner.update(f"Analyzing {project_count} projects")
        
        # Analyze projects
        results = analyze_projects(projects_df, args.config)
        
        # Generate reports
        spinner.update(f"Generating reports for {project_count} projects")
        generate_report(results, args.output)
        
        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        # Show a more stylish completion message
        print(f"\n{colors['green']}╔═════════════════════════════════════════════════════╗{colors['reset']}")
        print(f"{colors['green']}║ {colors['bold']}✅ ANALYSIS COMPLETED SUCCESSFULLY{colors['reset']}{colors['green']}                 ║{colors['reset']}")
        print(f"{colors['green']}╚═════════════════════════════════════════════════════╝{colors['reset']}")
        print(f"\n{colors['bold']}Summary:{colors['reset']}")
        print(f"  {colors['cyan']}⏱️  Time:{colors['reset']} {int(minutes)}m {int(seconds)}s")
        print(f"  {colors['cyan']}📊 Projects:{colors['reset']} {project_count}")
        print(f"  {colors['cyan']}📁 Reports:{colors['reset']} {args.output}/")
        print(f"\n{colors['yellow']}Thank you for using the Celo Hackathon Analysis Tool!{colors['reset']}")
        
        # Log completion
        logger.info(f"Analysis completed successfully in {elapsed_time:.2f} seconds")
        
        return 0

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")
        print("Please check the logs for more details.")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
