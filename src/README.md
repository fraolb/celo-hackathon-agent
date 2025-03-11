# Celo Hackathon Project Analyzer - Source Code

This directory contains the refactored implementation of the Celo Hackathon Project Analyzer.

## Directory Structure

- **models/**: Data types and configuration
  - `types.py`: TypedDict definitions for data structures
  - `config.py`: Configuration management

- **analyzer/**: Components for analyzing repositories
  - `repo_analyzer.py`: Main repository analyzer class
  - `github_repo.py`: GitHub repository access
  - `code_quality.py`: Code quality analysis
  - `celo_detector.py`: Celo integration detection

- **utils/**: Utility functions
  - `spinner.py`: Terminal spinner and progress indicators
  - `timeout.py`: Timeout handling utilities

- **reporting/**: Report generation
  - `report_generator.py`: Markdown report generation

- **main.py**: Main application logic

## Component Interactions

1. The `main.py` module orchestrates the analysis workflow:
   - Loads projects from Excel
   - Initializes the repository analyzer
   - Processes each project
   - Generates reports

2. The `repo_analyzer.py` coordinates the analysis components:
   - Uses `github_repo.py` to access repository content
   - Uses `code_quality.py` to evaluate code quality
   - Uses `celo_detector.py` to check for Celo integration

3. The `report_generator.py` creates Markdown reports:
   - Generates summary report
   - Creates individual project reports
   - Exports raw data as JSON

## Error Handling

The system uses a robust error handling approach:
- Custom exception types in `utils/timeout.py`
- Fallback mechanisms when API calls fail
- Graceful degradation to heuristic analysis when AI is unavailable

## Configuration

Configuration is loaded from `config.json` in the root directory:
- Weights for code quality metrics
- Celo keywords for integration detection
- Model settings for AI analysis