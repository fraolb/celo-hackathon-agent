#!/usr/bin/env python3
"""
Entry point for Celo Hackathon Analyzer.

This script launches the analysis of GitHub repositories for Celo hackathon projects,
evaluating code quality and checking for Celo blockchain integration.
"""

from src.main import main

if __name__ == "__main__":
    import sys
    sys.exit(main())