import os
import json
import pandas as pd
import argparse
from github_analyzer import GitHubLangChainAnalyzer
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def load_projects(excel_path: str) -> pd.DataFrame:
    """
    Load projects from Excel file.

    Args:
        excel_path: Path to Excel file

    Returns:
        DataFrame containing project data
    """
    try:
        df = pd.read_excel(excel_path)
        required_columns = [
            "project_name",
            "project_description",
            "project_github_url",
            "project_usernames",
            "project_url",
        ]

        # Check if required columns exist
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")

        return df
    except Exception as e:
        raise Exception(f"Error loading project data: {str(e)}")


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
    analyzer = GitHubLangChainAnalyzer(config_path)
    results = []

    for _, row in projects_df.iterrows():
        project_name = row["project_name"]
        project_description = row["project_description"]
        project_github_url = row["project_github_url"]
        # Convert project_usernames to a list if it's a string or NaN value
        project_usernames = []
        if isinstance(row["project_usernames"], list):
            project_usernames = row["project_usernames"]
        elif isinstance(row["project_usernames"], str):
            # Check if the string looks like a list representation
            if row["project_usernames"].startswith('[') and row["project_usernames"].endswith(']'):
                try:
                    import ast
                    project_usernames = ast.literal_eval(row["project_usernames"])
                except (SyntaxError, ValueError):
                    # If parsing fails, treat as comma-separated
                    project_usernames = [name.strip() for name in row["project_usernames"].split(',')]
            else:
                # Handle comma-separated strings
                project_usernames = [name.strip() for name in row["project_usernames"].split(',')]
        # Otherwise, leave as empty list
        project_url = row["project_url"]

        print(f"Analyzing project: {project_name}")

        # Analyze GitHub repository
        repo_analysis = analyzer.analyze_repository(project_github_url)

        # Combine project info with analysis results
        project_result = {
            "project_name": project_name,
            "project_description": project_description,
            "project_github_url": project_github_url,
            "project_usernames": project_usernames,
            "project_url": project_url,
            "analysis": repo_analysis,
        }

        results.append(project_result)

    return results


def generate_report(results: List[Dict[str, Any]], output_dir: str = "reports") -> None:
    """
    Generate Markdown reports from analysis results.

    Args:
        results: List of dictionaries containing analysis results
        output_dir: Directory to save reports
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Generate summary report
    summary_path = os.path.join(output_dir, "summary.md")
    with open(summary_path, "w") as f:
        f.write("# Celo Hackathon Project Analysis Summary\n\n")
        f.write("| Project | Score | Celo Integration | GitHub URL |\n")
        f.write("|---------|-------|------------------|------------|\n")

        for result in results:
            project_name = result["project_name"]
            github_url = result["project_github_url"]

            # Get code quality score
            if "analysis" in result and "code_quality" in result["analysis"]:
                code_quality = result["analysis"]["code_quality"]
                if isinstance(code_quality, dict) and "overall_score" in code_quality:
                    score = code_quality["overall_score"]
                elif isinstance(code_quality, (int, float)):
                    score = code_quality
                else:
                    score = 0
            else:
                score = 0

            # Get Celo integration status
            if "analysis" in result and "celo_integration" in result["analysis"]:
                celo_integration = result["analysis"]["celo_integration"]
                if isinstance(celo_integration, dict) and "integrated" in celo_integration:
                    celo_integrated = celo_integration["integrated"]
                elif isinstance(celo_integration, bool):
                    celo_integrated = celo_integration
                else:
                    celo_integrated = False
                celo_status = "✅" if celo_integrated else "❌"
            else:
                celo_status = "❌"

            f.write(
                f"| {project_name} | {score:.2f} | {celo_status} | [{github_url}]({github_url}) |\n"
            )

    # Generate individual reports
    for result in results:
        project_name = result["project_name"].replace(" ", "_").lower()
        report_path = os.path.join(output_dir, f"{project_name}.md")

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
            f.write(
                f"**GitHub URL:** [{result['project_github_url']}]({result['project_github_url']})\n\n"
            )

            # Repository details
            if "analysis" in result and "repo_details" in result["analysis"]:
                repo = result["analysis"]["repo_details"]
                f.write("### Repository Statistics\n\n")
                f.write(f"- **Stars:** {repo.get('stars', 'N/A')}\n")
                f.write(f"- **Forks:** {repo.get('forks', 'N/A')}\n")
                f.write(f"- **Open Issues:** {repo.get('open_issues', 'N/A')}\n")
                f.write(f"- **Primary Language:** {repo.get('language', 'N/A')}\n")
                f.write(f"- **Last Updated:** {repo.get('last_update', 'N/A')}\n\n")

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
                        # Safely get values with proper type checking
                        overall_score = quality.get("overall_score", 0)
                        if isinstance(overall_score, (int, float)):
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
                        else:
                            integrated = False
                        integration_status = "Yes" if integrated else "No"

                        f.write(f"**Integrated with Celo:** {integration_status}\n\n")

                        if integrated and "evidence" in celo and isinstance(celo["evidence"], list):
                            f.write("### Evidence of Integration\n\n")
                            for evidence in celo["evidence"]:
                                if isinstance(evidence, dict) and "keyword" in evidence and "file" in evidence:
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

    print(f"Reports generated in {output_dir} directory")


def main():
    """Main function to run the analysis."""
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
    args = parser.parse_args()

    try:
        # Load projects from Excel
        projects_df = load_projects(args.excel)

        # Analyze projects
        results = analyze_projects(projects_df, args.config)

        # Generate reports
        generate_report(results, args.output)

        # Save raw results to JSON for further processing if needed
        with open(os.path.join(args.output, "results.json"), "w") as f:
            json.dump(results, f, indent=2)

        print(f"Analysis completed. Reports saved to {args.output} directory.")

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
