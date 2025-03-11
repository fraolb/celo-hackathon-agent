# Celo Hackathon Project Analyzer

This tool analyzes GitHub repositories for Celo hackathon projects, evaluating code quality and checking for Celo blockchain integration.

## Features

- Reads project data from an Excel file
- Analyzes GitHub repositories using the GitHub API
- Evaluates code quality based on multiple factors
- Checks for Celo blockchain integration
- Generates detailed Markdown reports

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

3. Configure GitHub API token (optional but recommended to avoid rate limits):
   - Create a GitHub token with repo scope at https://github.com/settings/tokens
   - Add the token to `config.json` in the `github_token` field

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

## Output

The tool generates the following reports:
- `summary.md`: Overview of all analyzed projects
- Individual project reports with detailed analysis
- `results.json`: Raw data in JSON format

## License

MIT