"""
Repository analysis module for the AI Project Analyzer.

Updated to use direct google-generativeai instead of LangChain.
"""

import logging
import time
import re
from typing import Dict, Optional, Any, Union
import json
import google.generativeai as genai
from src.config import get_gemini_api_key

logger = logging.getLogger(__name__)

# Available models
AVAILABLE_MODELS = {
    "gemini-2.0-flash-lite": {
        "description": "Balanced model for most use cases",
        "max_tokens": 30000,
    },
    "gemini-2.0-flash": {
        "description": "Advanced model with better capabilities",
        "max_tokens": 30000,
    },
}

# Default model to use
DEFAULT_MODEL = "gemini-2.0-flash"
# Default temperature for generation
DEFAULT_TEMPERATURE = 0.2
# Maximum token limit (can be overridden by model-specific limits)
MAX_TOKENS = 900000
# Maximum retry attempts for API calls
MAX_RETRIES = 3
# Delay between retries (in seconds)
RETRY_DELAY = 5

# Initialize the Gemini client once
genai.configure(api_key=get_gemini_api_key())

def load_prompt(prompt_path: str) -> str:
    """[Previous implementation remains exactly the same]"""
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"Prompt file not found: {prompt_path}")
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

def create_prompt(
    prompt_template: str,
    code_digest: str,
    metrics_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Create the final prompt by combining template, metrics, and code digest.
    """
    prompt = prompt_template
    
    if metrics_data:
        metrics_formatted = format_metrics_for_prompt(metrics_data)
        metrics_instruction = f"""
## GitHub Metrics
I've included GitHub metrics for this repository that you should incorporate into your analysis:
{metrics_formatted}

When analyzing the repository, please consider these metrics and include them in your report under appropriate sections. 
Include a 'Repository Metrics' section with all the stats, a 'Top Contributor Profile' section, and a 'Language Distribution' section in your report.
Also add a 'Codebase Breakdown' section based on the strengths, weaknesses, and missing features from the codebase analysis.
"""
        prompt += metrics_instruction
    
    return prompt + f"\n\n{code_digest}"

def analyze_single_repository(
    repo_name: str,
    code_digest: str,
    prompt_path: str,
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    output_json: bool = False,
    metrics_data: Optional[Dict[str, Any]] = None,
) -> Union[str, Dict[str, Any]]:
    """
    Analyze a single repository using Gemini directly.
    """
    start_time = time.time()

    # Load the prompt template
    prompt_template = load_prompt(prompt_path)
    
    # Create the full prompt
    full_prompt = create_prompt(prompt_template, code_digest, metrics_data)
    
    if output_json:
        full_prompt += "\n\nPlease format your response as a valid JSON object containing the analysis results."
    
    retry_count = 0
    while retry_count < MAX_RETRIES:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                full_prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": AVAILABLE_MODELS[model_name].get("max_tokens", MAX_TOKENS)
                }
            )
            
            result = response.text
            
            if output_json:
                try:
                    # Handle JSON response parsing
                    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", result)
                    if json_match:
                        result = json_match.group(1).strip()
                    return json.loads(result)
                except Exception as e:
                    logger.error(f"JSON parsing failed: {str(e)}")
                    return {"error": str(e), "raw_response": result}
            
            return result

        except Exception as e:
            retry_count += 1
            logger.error(f"Error analyzing {repo_name} (attempt {retry_count}/{MAX_RETRIES}): {str(e)}")
            if retry_count < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return f"Error: {str(e)}"

    return f"Error: Failed after {MAX_RETRIES} attempts"

def analyze_repositories(
    repo_digests: Dict[str, str],
    prompt_path: str,
    model_name: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    output_json: bool = False,
    metrics_data: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Union[str, Dict[str, Any]]]:
    """[Previous implementation remains exactly the same]"""
    results = {}
    total_repos = len(repo_digests)
    start_time = time.time()

    logger.info(f"Loading prompt from {prompt_path}")

    for index, (repo_name, code_digest) in enumerate(repo_digests.items(), 1):
        logger.info(f"Analyzing repository {index}/{total_repos}: {repo_name}")

        repo_metrics = metrics_data.get(repo_name, {}) if metrics_data else {}
        analysis = analyze_single_repository(
            repo_name,
            code_digest,
            prompt_path,
            model_name,
            temperature,
            output_json,
            repo_metrics,
        )
        results[repo_name] = analysis

    total_time = time.time() - start_time
    successful_analyses = sum(
        1 for v in results.values() 
        if not isinstance(v, str) or not v.startswith("Error:")
    )
    logger.info(f"Analyzed {successful_analyses}/{total_repos} repositories successfully")
    logger.info(f"Total analysis time: {total_time:.2f} seconds")

    return results

# [All other helper functions remain exactly the same]
def truncate_if_needed(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """[Previous implementation remains exactly the same]"""
    # Very rough estimate: 4 characters per token
    chars_per_token = 4
    max_chars = max_tokens * chars_per_token

    if len(text) > max_chars:
        logger.warning("Code digest exceeds estimated token limit, truncating...")
        truncated = text[:max_chars]
        return truncated + "\n\n[Content truncated due to length]"

    return text

def format_metrics_for_prompt(metrics: Dict[str, Any]) -> str:
    """[Previous implementation remains exactly the same]"""
    formatted = []
    # [Rest of the function remains identical]
    return "\n".join(formatted)