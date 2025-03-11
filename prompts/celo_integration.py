"""
Prompts for Celo blockchain integration analysis using Anthropic's Claude model through LangChain.
"""

CELO_INTEGRATION_PROMPT = """You are tasked with determining if a GitHub repository uses Celo blockchain technology.

Look for any of these Celo-related keywords:
{keywords}

Based on the repository information provided, determine if the project integrates with Celo blockchain.
Consider:
1. Does the project mention Celo in documentation?
2. Does the code contain references to Celo contracts or APIs?
3. Are there dependencies or imports related to Celo?

Respond in JSON format:
{{
    "is_celo_integrated": true/false,
    "confidence": 0-100,
    "evidence": ["reason1", "reason2", ...],
    "explanation": "brief explanation"
}}
"""

HUMAN_CELO_INTEGRATION_PROMPT = """Analyze this GitHub repository for Celo blockchain integration:

Repository: {repo_owner}/{repo_name}

Here's what I know about the repository:
{repo_info}

Determine if this project integrates with Celo blockchain and respond in the requested JSON format."""

CELO_ANALYSIS_PROMPT = """Analyze the evidence of Celo blockchain integration in this GitHub repository.
Provide insights on:
1. How extensively the project uses Celo
2. What Celo features or components are being used
3. The quality of the Celo integration

Be concise and specific in your analysis."""

HUMAN_CELO_ANALYSIS_PROMPT = """This repository has evidence of Celo integration:

{evidence}

Provide a brief analysis of this Celo integration."""