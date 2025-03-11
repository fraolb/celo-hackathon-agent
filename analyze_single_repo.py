#!/usr/bin/env python3
"""
Analyze a single GitHub repository for code quality and Celo integration.
This is useful for testing the analyzer without needing to load from Excel.
"""

import json
import argparse
from github_analyzer import GitHubLangChainAnalyzer
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def main():
    """Main function to run the analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze a single GitHub repository for Celo hackathon evaluation using LangChain GitHub toolkit"
    )
    parser.add_argument("url", help="GitHub repository URL to analyze")
    parser.add_argument(
        "--config", default="config.json", help="Path to configuration file"
    )
    parser.add_argument("--output", help="Output file path for JSON results")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Display verbose output during analysis"
    )
    args = parser.parse_args()
    
    try:
        print(f"Analyzing GitHub repository: {args.url}")
        
        # Initialize analyzer
        analyzer = GitHubLangChainAnalyzer(args.config)
        
        # Analyze repository
        results = analyzer.analyze_repository(args.url)
        
        # Display results summary
        print("\n" + "="*50)
        print("ANALYSIS RESULTS")
        print("="*50)
        
        # Repository details
        if "repo_details" in results:
            repo = results["repo_details"]
            print(f"\nRepository: {repo.get('name', 'N/A')}")
            print(f"Description: {repo.get('description', 'N/A')}")
            print(f"Primary Language: {repo.get('language', 'N/A')}")
            print(f"Stars: {repo.get('stars', 0)} | Forks: {repo.get('forks', 0)} | Issues: {repo.get('open_issues', 0)}")
        
        # Code quality
        if "code_quality" in results:
            quality = results["code_quality"]
            
            if "error" in quality:
                print(f"\nCode Quality Error: {quality['error']}")
            else:
                print(f"\nCode Quality Score: {quality.get('overall_score', 0):.2f}/100")
                print(f"  - Readability: {quality.get('readability', 0):.2f}/100")
                print(f"  - Standards: {quality.get('standards', 0):.2f}/100")
                print(f"  - Complexity: {quality.get('complexity', 0):.2f}/100")
                print(f"  - Testing: {quality.get('testing', 0):.2f}/100")
                
                if "ai_analysis" in quality and "overall_analysis" in quality["ai_analysis"]:
                    print(f"\nAnalysis: {quality['ai_analysis']['overall_analysis']}")
                
                if "ai_analysis" in quality and "suggestions" in quality["ai_analysis"]:
                    print("\nSuggestions:")
                    for suggestion in quality["ai_analysis"]["suggestions"]:
                        print(f"  - {suggestion}")
        
        # Celo integration
        if "celo_integration" in results:
            celo = results["celo_integration"]
            
            if "error" in celo:
                print(f"\nCelo Integration Error: {celo['error']}")
            else:
                integrated = celo.get("integrated", False)
                print(f"\nCelo Integration: {'Yes' if integrated else 'No'}")
                
                if integrated and "evidence" in celo:
                    print("\nEvidence:")
                    for evidence in celo["evidence"][:5]:  # Show up to 5 pieces of evidence
                        print(f"  - Found '{evidence['keyword']}' in {evidence['file']}")
                    
                    if len(celo["evidence"]) > 5:
                        print(f"  - (and {len(celo['evidence']) - 5} more instances)")
                
                if integrated and "analysis" in celo:
                    print(f"\nIntegration Analysis: {celo['analysis']}")
        
        # Save to file if specified
        if args.output:
            with open(args.output, "w") as f:
                json.dump(results, f, indent=2)
            print(f"\nResults saved to {args.output}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())