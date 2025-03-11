import os
import json
import pandas as pd
import argparse
from github_analyzer import GitHubAnalyzer
from pathlib import Path
from typing import Dict, List, Any


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
    analyzer = GitHubAnalyzer(config_path)
    results = []

    for _, row in projects_df.iterrows():
        project_name = row["project_name"]
        project_description = row["project_description"]
        project_github_url = row["project_github_url"]
        project_usernames = (
            row["project_usernames"]
            if isinstance(row["project_usernames"], list)
            else []
        )
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
                score = result["analysis"]["code_quality"].get("overall_score", 0)
            else:
                score = 0

            # Get Celo integration status
            if "analysis" in result and "celo_integration" in result["analysis"]:
                celo_integrated = result["analysis"]["celo_integration"].get(
                    "integrated", False
                )
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
            f.write(
                f"**Project URL:** [{result['project_url']}]({result['project_url']})\n\n"
            )
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

                if "error" in quality:
                    f.write(f"**Error:** {quality['error']}\n\n")
                else:
                    f.write(
                        f"**Overall Score:** {quality.get('overall_score', 0):.2f}/100\n\n"
                    )
                    f.write(
                        f"**Readability and Documentation:** {quality.get('readability', 0):.2f}/100\n\n"
                    )
                    f.write(
                        f"**Coding Standards and Best Practices:** {quality.get('standards', 0):.2f}/100\n\n"
                    )
                    f.write(
                        f"**Algorithm Complexity and Efficiency:** {quality.get('complexity', 0):.2f}/100\n\n"
                    )
                    f.write(
                        f"**Testing and Coverage:** {quality.get('testing', 0):.2f}/100\n\n"
                    )

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
                        f.write(
                            f"- **Lines of Code:** {metrics.get('code_lines', 'N/A')}\n"
                        )
                        f.write(
                            f"- **Comment Lines:** {metrics.get('comment_lines', 'N/A')}\n\n"
                        )
            else:
                f.write(
                    "Could not assess code quality due to an error or inaccessible repository.\n\n"
                )

            # Celo Integration
            f.write("## Celo Blockchain Integration\n\n")

            if "analysis" in result and "celo_integration" in result["analysis"]:
                celo = result["analysis"]["celo_integration"]

                if "error" in celo:
                    f.write(f"**Error:** {celo['error']}\n\n")
                else:
                    integrated = celo.get("integrated", False)
                    integration_status = "Yes" if integrated else "No"

                    f.write(f"**Integrated with Celo:** {integration_status}\n\n")

                    if integrated and "evidence" in celo:
                        f.write("### Evidence of Integration\n\n")
                        for evidence in celo["evidence"]:
                            f.write(
                                f"- Found keyword '{evidence['keyword']}' in file: {evidence['file']}\n"
                            )
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
