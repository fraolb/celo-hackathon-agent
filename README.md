# Celo Hackathon Project Analyzer with LangChain and Anthropic

This tool analyzes GitHub repositories for Celo hackathon projects, evaluating code quality and checking for Celo blockchain integration using LangChain and Anthropic's Claude AI model.

## Features

- Reads project data from an Excel file
- Analyzes GitHub repositories using LangChain's GitHub toolkit, which provides powerful access to repository information without requiring local cloning
- Evaluates code quality using Anthropic's Claude AI model
- Provides intelligent assessment of code quality and best practices
- Checks for Celo blockchain integration with AI-powered analysis
- Generates detailed Markdown reports with LLM-driven insights

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/celo-hackathon-agent.git
cd celo-hackathon-agent
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API tokens:
   - Create a GitHub token with repo scope at https://github.com/settings/tokens
   - Get an Anthropic API key from https://console.anthropic.com/
   - Create a `.env` file based on `.env.example` and add your tokens:
     ```
     GITHUB_TOKEN=your_github_token_here
     ANTHROPIC_API_KEY=your_anthropic_api_key_here
     ```

## Usage

### Prepare Project Data

Create an Excel file with the following columns:
- `project_name`: Name of the project
- `project_description`: Brief description of the project
- `project_github_url`: URL of the project's GitHub repository
- `project_usernames`: List of usernames associated with the project
- `project_url`: Main website URL of the project

Or use the provided sample data generator:
```bash
python create_sample_data.py
```

### Run the Analyzer

```bash
python main.py --excel sample_projects.xlsx --output reports
```

Optional arguments:
- `--config`: Path to custom configuration file (default: `config.json`)
- `--output`: Directory to save reports (default: `reports`)

### Configuration

You can customize the analysis by editing `config.json`:
- `weights`: Adjust the weight of each code quality category
- `celo_keywords`: Keywords to search for when checking Celo integration
- `celo_files`: Files to check for Celo-related configurations

The tool leverages LangChain's components:
- `langchain_community.agent_toolkits.github.toolkit`: A powerful toolkit that interacts with GitHub repositories through PyGitHub
- `langchain_github`: Used to access and analyze GitHub repositories
- `langchain_anthropic`: Connects to Claude AI for intelligent code analysis
- `langchain_core`: Provides chains and prompts for structured reasoning
- `langgraph`: Creates reactive agents that can use GitHub tools effectively

## Output

The tool generates the following reports:
- `summary.md`: Overview of all analyzed projects
- Individual project reports with detailed analysis, including:
  - AI-powered code quality assessment with detailed reasoning
  - Intelligent analysis of coding standards and best practices
  - Suggestions for code improvements
  - Comprehensive evaluation of Celo blockchain integration
  - Evidence and analysis of how the project uses Celo technology
- `results.json`: Raw data in JSON format for further processing

## License

MIT