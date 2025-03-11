"""
GitHub Repository Analyzer

This module provides functionality to analyze GitHub repositories for code quality
and Celo blockchain integration using the GitHub API and LangChain AI analysis.
"""

import os
import json
import base64
import re
import time
import threading
from typing import Dict, List, Tuple, Any, Optional, TypedDict, Union
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path
import signal

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser

# Import prompt templates
from prompts.code_quality import CODE_QUALITY_PROMPT, HUMAN_CODE_QUALITY_PROMPT
from prompts.celo_integration import (
    CELO_INTEGRATION_PROMPT, 
    HUMAN_CELO_INTEGRATION_PROMPT,
    CELO_ANALYSIS_PROMPT,
    HUMAN_CELO_ANALYSIS_PROMPT
)

# Load environment variables
load_dotenv()

# Type Definitions
class RepoDetails(TypedDict):
    """Repository details type definition"""
    name: str
    description: str
    url: str
    stars: int
    forks: int
    open_issues: int
    last_update: str
    language: str

class CodeQualityScores(TypedDict):
    """Code quality scores type definition"""
    overall_score: float
    readability: float
    standards: float
    complexity: float
    testing: float

class CodeQualityMetrics(TypedDict):
    """Code quality metrics type definition"""
    file_count: int
    test_file_count: int
    doc_file_count: int
    code_files_analyzed: int
    code_lines: Optional[int]
    comment_lines: Optional[int]

class AIAnalysis(TypedDict):
    """AI analysis details type definition"""
    overall_analysis: str
    suggestions: List[str]
    readability_reasoning: str
    standards_reasoning: str
    complexity_reasoning: str
    testing_reasoning: str

class CodeQualityResult(TypedDict):
    """Complete code quality analysis result"""
    overall_score: float
    readability: float
    standards: float
    complexity: float
    testing: float
    ai_analysis: Optional[AIAnalysis]
    metrics: CodeQualityMetrics
    repositories_analyzed: Optional[int]
    note: Optional[str]
    error: Optional[str]

class CeloEvidence(TypedDict):
    """Evidence of Celo integration"""
    file: str
    keyword: str
    repository: Optional[str]

class CeloIntegrationResult(TypedDict):
    """Celo integration analysis result"""
    integrated: bool
    evidence: List[CeloEvidence]
    analysis: Optional[str]
    repositories_with_celo: Optional[int]
    error: Optional[str]

class RepositoryAnalysisResult(TypedDict):
    """Complete repository analysis result"""
    repo_details: RepoDetails
    code_quality: CodeQualityResult
    celo_integration: CeloIntegrationResult
    error: Optional[str]


# Exception classes
class TimeoutError(Exception):
    """Raised when a function execution times out."""
    pass

class GitHubAccessError(Exception):
    """Raised when there's an issue accessing the GitHub API."""
    pass

class AIAnalysisError(Exception):
    """Raised when there's an issue with AI-based analysis."""
    pass

class RepositoryAnalysisError(Exception):
    """Raised when there's an issue analyzing a repository."""
    pass


# Utility functions
def timeout_handler(signum, frame):
    """Signal handler for function timeouts."""
    raise TimeoutError("Function execution timed out")


def with_timeout(seconds: int):
    """
    Decorator to add timeout functionality to functions.
    
    Args:
        seconds: Number of seconds before timing out
        
    Returns:
        Decorated function with timeout capability
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Set the timeout handler (only works on Unix systems)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
                signal.alarm(0)  # Disable the alarm
                return result
            except TimeoutError:
                print(f"Function {func.__name__} timed out after {seconds} seconds")
                return None
            finally:
                signal.alarm(0)  # Ensure the alarm is disabled
        return wrapper
    return decorator


def run_with_active_spinner(func, args=(), kwargs={}, message=None, callback=None, update_interval=0.2):
    """
    Run a function while updating a spinner/progress indicator.
    
    Args:
        func: Function to run
        args: Arguments to pass to the function
        kwargs: Keyword arguments to pass to the function
        message: Message to display in the spinner
        callback: Callback function for updating the spinner
        update_interval: Not used in this non-threaded implementation
        
    Returns:
        The result of the function
    """
    if callback is None:
        # If no callback, just run the function directly
        return func(*args, **kwargs)
    
    # Initial spinner update
    if message:
        callback(f"{message}")
    
    # Directly run the function
    start_time = time.time()
    try:
        # Execute the function
        result = func(*args, **kwargs)
        
        # Update spinner after completion
        elapsed = time.time() - start_time
        if message:
            callback(f"{message} (completed in {elapsed:.1f}s)")
            
        return result
    except Exception as e:
        # Update spinner with error
        elapsed = time.time() - start_time
        if message:
            callback(f"{message} - Error: {str(e)} after {elapsed:.1f}s")
        raise e


@dataclass
class Config:
    """Configuration for the repository analyzer."""
    weights: Dict[str, float]
    celo_keywords: List[str]
    celo_files: List[str]
    github_token: str
    model_name: str = "claude-3-haiku-20240307"
    temperature: float = 0.1
    
    @classmethod
    def from_file(cls, config_path: str = "config.json") -> 'Config':
        """
        Load configuration from a JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Config object with loaded settings
        """
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            
        # Get GitHub token from environment or config
        github_token = os.environ.get("GITHUB_TOKEN") or config_data.get("github_token", "")
        
        return cls(
            weights=config_data["weights"],
            celo_keywords=config_data["celo_keywords"],
            celo_files=config_data["celo_files"],
            github_token=github_token
        )


class GitHubLangChainAnalyzer:
    """
    Analyzes GitHub repositories for code quality and Celo blockchain integration.
    
    This class combines GitHub API access, code analysis, and AI-powered evaluation
    to provide insights into repository quality and Celo integration.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the GitHub analyzer with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        self.config = Config.from_file(config_path)
        
        if not self.config.github_token:
            print("Warning: No GitHub token found. API rate limits may apply.")
        
        # Set up Anthropic model
        self.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.anthropic_api_key:
            print("Warning: No Anthropic API key found. Using fallback analysis methods only.")
        
        # Initialize LLM if we have an API key
        self.llm = None
        if self.anthropic_api_key:
            try:
                self.llm = ChatAnthropic(
                    model=self.config.model_name,
                    temperature=self.config.temperature,
                    anthropic_api_key=self.anthropic_api_key
                )
            except Exception as e:
                print(f"Error initializing Claude model: {str(e)}")
                print("Using fallback analysis methods only.")
        
        # Initialize GitHub repository references
        self.repo = None
        self.repo_owner = None
        self.repo_name = None
        
    def _parse_github_url(self, repo_url: str) -> Tuple[str, str]:
        """
        Parse a GitHub URL to extract owner and repository name.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            Tuple of repository owner and name
            
        Raises:
            ValueError: If the URL is not a valid GitHub repository URL
        """
        # Extract repo owner and name from URL
        repo_parts = repo_url.strip("/").split("/")
        if "github.com" not in repo_url or len(repo_parts) < 5:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        repo_owner = repo_parts[-2]
        repo_name = repo_parts[-1]
        
        return repo_owner, repo_name
    
    def _connect_to_github_api(self, repo_owner: str, repo_name: str) -> Any:
        """
        Connect to GitHub API and get repository object.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            GitHub repository object or None if connection fails
        """
        if not self.config.github_token:
            print(f"No GitHub token provided. Using limited repository information for {repo_owner}/{repo_name}")
            return None
        
        # If we have a token, use PyGithub for direct access
        try:
            from github import Github
            
            # Initialize GitHub client
            g = Github(self.config.github_token)
            
            # Get repository
            repo = g.get_repo(f"{repo_owner}/{repo_name}")
            
            # Simple check if repository exists and is accessible
            _ = repo.name
            
            return repo
            
        except Exception as e:
            error_msg = f"Error accessing repository {repo_owner}/{repo_name}: {str(e)}"
            print(error_msg)
            raise GitHubAccessError(error_msg)
    
    def _setup_github_tools(self, repo_url: str) -> Tuple[str, str]:
        """
        Set up GitHub tools with the correct repository.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            Tuple of repository owner and name
        """
        # Parse GitHub URL to get owner and name
        repo_owner, repo_name = self._parse_github_url(repo_url)
        
        try:
            # Connect to GitHub API and get repository object
            self.repo = self._connect_to_github_api(repo_owner, repo_name)
        except GitHubAccessError:
            # If we can't access the repository, set repo to None
            self.repo = None
        
        # Store repository info regardless of API success
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        
        return repo_owner, repo_name
        
    def _create_fallback_repo_details(self, repo_owner: str, repo_name: str, repo_url: str) -> RepoDetails:
        """
        Create fallback repository details when repository access fails.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            repo_url: URL of the repository
            
        Returns:
            RepoDetails with basic information
        """
        return {
            "name": repo_name,
            "description": f"Repository for {repo_owner}/{repo_name}",
            "url": repo_url,
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "last_update": "",
            "language": ""
        }
    
    def _create_fallback_code_quality(self, error_message: str = None) -> CodeQualityResult:
        """
        Create fallback code quality results when analysis fails.
        
        Args:
            error_message: Optional error message
            
        Returns:
            CodeQualityResult with fallback values
        """
        # Use a reasonable default score
        base_score = 75 
        
        result = {
            "overall_score": base_score,
            "readability": base_score,
            "standards": base_score,
            "complexity": base_score,
            "testing": base_score,
            "metrics": {
                "file_count": 0,
                "test_file_count": 0,
                "doc_file_count": 0,
                "code_files_analyzed": 0
            },
            "repositories_analyzed": 1
        }
        
        if error_message:
            result["note"] = f"Used fallback quality estimation: {error_message}"
            
        return result
    
    def _create_fallback_celo_integration(self, repo_name: str, error_message: str = None) -> CeloIntegrationResult:
        """
        Create fallback Celo integration results when analysis fails.
        
        Args:
            repo_name: Name of the repository
            error_message: Optional error message
            
        Returns:
            CeloIntegrationResult with fallback assessment
        """
        # Simple heuristic - check if repository name contains "celo"
        has_celo_in_name = "celo" in repo_name.lower()
        
        # Create evidence if needed
        evidence = []
        if has_celo_in_name:
            evidence = [{"file": "Repository name", "keyword": "celo"}]
        
        result = {
            "integrated": has_celo_in_name,
            "evidence": evidence,
            "repositories_with_celo": 1 if has_celo_in_name else 0
        }
        
        if error_message:
            result["note"] = f"Used fallback integration detection: {error_message}"
            
        return result
    
    def analyze_repository(self, repo_url: str, callback=None) -> RepositoryAnalysisResult:
        """
        Analyze a GitHub repository for code quality and Celo integration.
        
        Args:
            repo_url: URL of the GitHub repository
            callback: Optional callback function to report progress
            
        Returns:
            RepositoryAnalysisResult containing analysis results
        """
        try:
            # Setup GitHub access and get repo information
            if callback:
                callback(f"Setting up GitHub tools for {repo_url}")
            
            repo_owner, repo_name = self._setup_github_tools(repo_url)
            
            # Step 1: Get repository details
            repo_details = self._get_repository_details_safely(repo_owner, repo_name, repo_url, callback)
            
            # Step 2: Analyze code quality
            code_quality = self._analyze_code_quality_safely(repo_owner, repo_name, callback)
            
            # Step 3: Check for Celo integration
            celo_integration = self._check_celo_integration_safely(repo_owner, repo_name, callback)
            
            # Compile results
            if callback:
                callback(f"Compiling analysis results for {repo_owner}/{repo_name}")
                
            results = {
                "repo_details": repo_details,
                "code_quality": code_quality,
                "celo_integration": celo_integration
            }
            
            return results
            
        except Exception as e:
            error_message = f"Error analyzing repository: {str(e)}"
            
            if callback:
                # Show error in spinner
                callback(f"Error analyzing {repo_url}: {str(e)}")
                # Wait a moment so the user can see the error
                time.sleep(1)
                
            return {
                "error": error_message,
                "repo_details": self._create_fallback_repo_details(
                    repo_owner=repo_url.split('/')[-2] if 'github.com' in repo_url else "unknown",
                    repo_name=repo_url.split('/')[-1] if 'github.com' in repo_url else "unknown",
                    repo_url=repo_url
                ),
                "code_quality": self._create_fallback_code_quality(error_message),
                "celo_integration": self._create_fallback_celo_integration(
                    repo_name=repo_url.split('/')[-1] if 'github.com' in repo_url else "unknown",
                    error_message=error_message
                )
            }
    
    def _get_repository_details_safely(self, repo_owner: str, repo_name: str, repo_url: str, callback=None) -> RepoDetails:
        """
        Safely get repository details with error handling and fallback.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            repo_url: URL of the repository
            callback: Optional callback function for progress updates
            
        Returns:
            RepoDetails with repository information
        """
        # Get repository details with timeout
        if callback:
            callback(f"Fetching repository details for {repo_owner}/{repo_name}")
            
            try:
                repo_details = run_with_active_spinner(
                    func=self._get_repository_details_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Fetching repository details for {repo_owner}/{repo_name}",
                    callback=callback
                )
            except Exception as e:
                # Handle API or connection errors
                error_message = str(e)
                callback(f"Error fetching repository details: {error_message}")
                repo_details = None
        else:
            repo_details = self._get_repository_details_with_timeout(repo_owner, repo_name)
        
        # If details couldn't be retrieved, use fallback
        if repo_details is None:
            return self._create_fallback_repo_details(repo_owner, repo_name, repo_url)
        
        return repo_details
    
    def _analyze_code_quality_safely(self, repo_owner: str, repo_name: str, callback=None) -> CodeQualityResult:
        """
        Safely analyze code quality with error handling and fallback.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            callback: Optional callback function for progress updates
            
        Returns:
            CodeQualityResult with analysis results
        """
        if callback:
            callback(f"Analyzing code quality for {repo_owner}/{repo_name}")
            
            try:
                code_quality = run_with_active_spinner(
                    func=self._analyze_code_quality_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Analyzing code quality for {repo_owner}/{repo_name}",
                    callback=callback
                )
            except Exception as e:
                # Handle API overload or other errors
                error_message = str(e)
                callback(f"API error during code quality analysis: {error_message}")
                return self._create_fallback_code_quality(error_message)
        else:
            code_quality = self._analyze_code_quality_with_timeout(repo_owner, repo_name)
        
        # Handle timeout or error cases
        if code_quality is None:
            return self._create_fallback_code_quality("Analysis timed out")
        
        return code_quality
    
    def _check_celo_integration_safely(self, repo_owner: str, repo_name: str, callback=None) -> CeloIntegrationResult:
        """
        Safely check Celo integration with error handling and fallback.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            callback: Optional callback function for progress updates
            
        Returns:
            CeloIntegrationResult with analysis results
        """
        if callback:
            callback(f"Checking Celo integration for {repo_owner}/{repo_name}")
            
            try:
                celo_integration = run_with_active_spinner(
                    func=self._check_celo_integration_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Checking Celo integration for {repo_owner}/{repo_name}",
                    callback=callback
                )
            except Exception as e:
                # Handle API overload or other errors
                error_message = str(e)
                callback(f"API error: {error_message}")
                return self._create_fallback_celo_integration(repo_name, error_message)
        else:
            celo_integration = self._check_celo_integration_with_timeout(repo_owner, repo_name)
        
        # Handle timeout or error cases
        if celo_integration is None:
            return self._create_fallback_celo_integration(repo_name, "Analysis timed out")
        
        return celo_integration
    
    @with_timeout(30)
    def _get_repository_details_with_timeout(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Timeout wrapper for _get_repository_details"""
        return self._get_repository_details(repo_owner, repo_name)
        
    @with_timeout(60)
    def _analyze_code_quality_with_timeout(self, repo_owner: str, repo_name: str) -> CodeQualityResult:
        """Timeout wrapper for _analyze_code_quality"""
        return self._analyze_code_quality(repo_owner, repo_name)
        
    @with_timeout(60)
    def _check_celo_integration_with_timeout(self, repo_owner: str, repo_name: str) -> CeloIntegrationResult:
        """Timeout wrapper for _check_celo_integration"""
        return self._check_celo_integration(repo_owner, repo_name)
        
    def _get_repository_details(self, repo_owner: str, repo_name: str) -> RepoDetails:
        """
        Get repository details using PyGithub.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            RepoDetails with repository information
        """
        # If we don't have the repo object, return fallback info
        if self.repo is None:
            return self._create_fallback_repo_details(
                repo_owner, 
                repo_name, 
                f"https://github.com/{repo_owner}/{repo_name}"
            )
        
        try:
            # Get repository details directly
            repo_info = {
                "name": self.repo.name,
                "description": self.repo.description or "",
                "url": self.repo.html_url,
                "stars": self.repo.stargazers_count,
                "forks": self.repo.forks_count,
                "open_issues": self.repo.open_issues_count,
                "last_update": self.repo.updated_at.isoformat() if self.repo.updated_at else "",
                "language": self.repo.language or ""
            }
            
            return repo_info
            
        except Exception as e:
            error_msg = f"Error getting repository details: {str(e)}"
            print(error_msg)
            raise GitHubAccessError(error_msg)
            
    def _analyze_code_quality(self, repo_owner: str, repo_name: str) -> CodeQualityResult:
        """
        Analyze the code quality of a repository using GitHub API and AI assistance.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            CodeQualityResult with analysis data
        """
        # Choose analysis method based on repository access
        if self.repo is None:
            return self._analyze_code_quality_without_access(repo_owner, repo_name)
        else:
            return self._analyze_code_quality_with_access(repo_owner, repo_name)
    
    def _analyze_code_quality_without_access(self, repo_owner: str, repo_name: str) -> CodeQualityResult:
        """
        Analyze code quality without direct repository access.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            CodeQualityResult with estimated quality
        """
        # Get basic repository information
        repo_info = self._get_repository_details(repo_owner, repo_name)
        
        # Try AI-based estimation if available
        if self.llm is not None:
            try:
                return self._estimate_quality_with_ai(repo_owner, repo_name, repo_info)
            except Exception as e:
                print(f"Error in AI estimation of code quality: {str(e)}")
                # Fall through to heuristic analysis on failure
        
        # Use heuristic analysis as fallback
        return self._estimate_quality_with_heuristics(repo_owner, repo_name)
    
    def _estimate_quality_with_ai(self, repo_owner: str, repo_name: str, repo_info: RepoDetails) -> CodeQualityResult:
        """
        Estimate code quality using AI based on repository metadata.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            repo_info: Repository details
            
        Returns:
            CodeQualityResult with AI-based quality estimation
        """
        # Create a prompt for the AI model
        quality_prompt = ChatPromptTemplate.from_template(
            """You are a senior software engineer tasked with making a rough estimate of a GitHub repository's code quality.
            Based on the limited information provided about the repository (name, organization, description), 
            provide a reasonable estimate of what the code quality might be like.
            
            Repository: {repo_owner}/{repo_name}
            Description: {repo_description}
            
            I don't have direct access to the code, so please make an educated guess based on the repository name,
            owner, and any other information you might know about this project. If you've heard of this repository
            before, you can use that knowledge.
            
            Respond in JSON format:
            {{
                "readability": {{"score": 0-100, "reasoning": "explanation"}},
                "standards": {{"score": 0-100, "reasoning": "explanation"}},
                "complexity": {{"score": 0-100, "reasoning": "explanation"}},
                "testing": {{"score": 0-100, "reasoning": "explanation"}},
                "overall_analysis": "brief overall analysis",
                "suggestions": ["suggestion1", "suggestion2"]
            }}
            """
        )
        
        # Run analysis with the AI model
        analysis_chain = quality_prompt | self.llm | StrOutputParser()
        analysis_result = analysis_chain.invoke({
            "repo_owner": repo_owner,
            "repo_name": repo_name,
            "repo_description": repo_info.get("description", "")
        })
        
        # Parse the AI response
        analysis_json = json.loads(analysis_result)
        
        # Extract scores and reasoning from AI response
        readability = analysis_json.get("readability", {})
        standards = analysis_json.get("standards", {})
        complexity = analysis_json.get("complexity", {})
        testing = analysis_json.get("testing", {})
        
        readability_score = readability.get("score", 0) if isinstance(readability, dict) else 0
        standards_score = standards.get("score", 0) if isinstance(standards, dict) else 0
        complexity_score = complexity.get("score", 0) if isinstance(complexity, dict) else 0
        testing_score = testing.get("score", 0) if isinstance(testing, dict) else 0
        
        # Calculate weighted score
        overall_score = self._calculate_weighted_score(
            readability_score, standards_score, complexity_score, testing_score
        )
        
        # Compile and return the results
        return {
            "overall_score": round(overall_score, 2),
            "readability": readability_score,
            "standards": standards_score,
            "complexity": complexity_score,
            "testing": testing_score,
            "ai_analysis": {
                "overall_analysis": analysis_json.get("overall_analysis", "") + " (Note: This is an estimate based on limited information)",
                "suggestions": analysis_json.get("suggestions", []),
                "readability_reasoning": readability.get("reasoning", ""),
                "standards_reasoning": standards.get("reasoning", ""),
                "complexity_reasoning": complexity.get("reasoning", ""),
                "testing_reasoning": testing.get("reasoning", "")
            },
            "metrics": {
                "file_count": 0,
                "test_file_count": 0,
                "doc_file_count": 0,
                "code_files_analyzed": 0
            },
            "repositories_analyzed": 1,
            "note": "This analysis is based on AI estimation as direct repository access was not available."
        }
    
    def _estimate_quality_with_heuristics(self, repo_owner: str, repo_name: str) -> CodeQualityResult:
        """
        Estimate code quality using heuristics based on repository name and owner.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            CodeQualityResult with heuristic-based quality estimation
        """
        repo_name_lower = repo_name.lower()
        repo_owner_lower = repo_owner.lower()
        
        # Simple heuristic based on repository name and owner
        quality_indicators = ["awesome", "framework", "official", "production", "stable"]
        quality_score = 0
        
        # Check for quality indicators in name and owner
        for indicator in quality_indicators:
            if indicator in repo_name_lower or indicator in repo_owner_lower:
                quality_score += 15
        
        # Apply premium for well-known organizations
        premium_orgs = ["microsoft", "google", "facebook", "apple", "amazon", "celo-org"]
        if repo_owner_lower in premium_orgs:
            quality_score += 30
            
        # Cap at 85 - we can't give a perfect score without seeing the code
        quality_score = min(85, quality_score)
        
        # If we found no indicators, give a baseline score
        if quality_score == 0:
            quality_score = 50
        
        # Return consistent result structure
        return {
            "overall_score": quality_score,
            "readability": quality_score,
            "standards": quality_score,
            "complexity": quality_score,
            "testing": quality_score,
            "metrics": {
                "file_count": 0,
                "test_file_count": 0,
                "doc_file_count": 0,
                "code_files_analyzed": 0
            },
            "repositories_analyzed": 1,
            "note": "This is a basic estimate based on repository metadata, as direct repository access was not available."
        }
    
    def _analyze_code_quality_with_access(self, repo_owner: str, repo_name: str) -> CodeQualityResult:
        """
        Analyze code quality with direct repository access.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            CodeQualityResult with detailed quality analysis
        """
        try:
            # Collect code samples and file metrics
            file_metrics, code_samples = self._collect_code_samples()
            
            # If we have code samples and a working LLM, use AI analysis
            if code_samples and self.llm is not None:
                try:
                    return self._analyze_code_with_ai(code_samples, file_metrics)
                except Exception as e:
                    print(f"Error in AI analysis of code: {str(e)}")
                    # Fall through to fallback analysis
            
            # Fallback to heuristic-based analysis
            return self._fallback_code_quality_analysis(
                file_metrics["file_count"],
                file_metrics["test_file_count"],
                file_metrics["doc_file_count"],
                file_metrics["code_files_analyzed"]
            )
            
        except Exception as e:
            error_msg = f"Error analyzing repository code: {str(e)}"
            print(error_msg)
            
            # Return error result
            return {
                "error": error_msg,
                "overall_score": 0,
                "readability": 0,
                "standards": 0,
                "complexity": 0,
                "testing": 0,
                "metrics": {
                    "file_count": 0,
                    "test_file_count": 0,
                    "doc_file_count": 0,
                    "code_files_analyzed": 0
                },
                "repositories_analyzed": 0
            }
    
    def _collect_code_samples(self) -> Tuple[Dict[str, int], List[str]]:
        """
        Collect code samples and file metrics from repository.
        
        Returns:
            Tuple of file metrics and code samples
        """
        # Get repository contents
        contents = self.repo.get_contents("")
        
        # Initialize counters
        file_count = 0
        test_file_count = 0
        doc_file_count = 0
        
        # Process files recursively
        files_to_process = list(contents)
        processed_paths = set()
        
        # Code samples for analysis
        code_samples = []
        code_file_paths = []
        
        # Maximum files to process to avoid excessive API calls
        max_files_to_process = 100
        files_processed = 0
        
        # Process repository files
        while files_to_process and files_processed < max_files_to_process:
            content = files_to_process.pop(0)
            if content.path in processed_paths:
                continue
            
            processed_paths.add(content.path)
            files_processed += 1
            
            if content.type == "dir":
                try:
                    # Add directory contents to processing queue
                    dir_contents = self.repo.get_contents(content.path)
                    if isinstance(dir_contents, list):
                        files_to_process.extend(dir_contents)
                    else:
                        files_to_process.append(dir_contents)
                except Exception:
                    # Skip directories we can't access
                    continue
                    
            elif content.type == "file":
                file_count += 1
                file_path = content.path
                
                # Classify file types
                if "test" in file_path.lower() or "spec" in file_path.lower():
                    test_file_count += 1
                    
                if file_path.lower().endswith((".md", ".rst", ".txt", ".doc", ".docx")):
                    doc_file_count += 1
                    
                # Collect code file samples
                code_extensions = (".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".sol", 
                                  ".go", ".rb", ".php", ".c", ".cpp", ".cs")
                if file_path.lower().endswith(code_extensions):
                    try:
                        # Add to code file paths
                        code_file_paths.append(file_path)
                        
                        # Only sample up to 10 code files
                        if len(code_samples) < 10:
                            file_content = self.repo.get_contents(file_path).decoded_content.decode('utf-8')
                            # Limit sample size
                            sample = file_content[:1000] + "..." if len(file_content) > 1000 else file_content
                            code_samples.append(f"File: {file_path}\n\n{sample}\n\n")
                    except Exception:
                        # Skip files that can't be decoded
                        continue
        
        # Compile file metrics
        file_metrics = {
            "file_count": file_count,
            "test_file_count": test_file_count,
            "doc_file_count": doc_file_count,
            "code_files_analyzed": len(code_file_paths)
        }
        
        return file_metrics, code_samples
    
    def _analyze_code_with_ai(self, code_samples: List[str], file_metrics: Dict[str, int]) -> CodeQualityResult:
        """
        Analyze code quality using AI.
        
        Args:
            code_samples: List of code samples
            file_metrics: Repository file metrics
            
        Returns:
            CodeQualityResult with AI-based analysis
        """
        # Combine code samples for analysis
        code_sample_text = "\n".join(code_samples)
        
        # Create prompt for code quality analysis
        quality_prompt = ChatPromptTemplate.from_messages([
            ("system", CODE_QUALITY_PROMPT),
            ("human", HUMAN_CODE_QUALITY_PROMPT)
        ])
        
        # Run analysis with AI model
        analysis_chain = quality_prompt | self.llm | StrOutputParser()
        analysis_result = analysis_chain.invoke({"code_samples": code_sample_text})
        
        # Parse the AI response
        analysis_json = json.loads(analysis_result)
        
        # Extract scores and reasoning
        readability = analysis_json.get("readability", {})
        standards = analysis_json.get("standards", {})
        complexity = analysis_json.get("complexity", {})
        testing = analysis_json.get("testing", {})
        
        readability_score = readability.get("score", 0) if isinstance(readability, dict) else 0
        standards_score = standards.get("score", 0) if isinstance(standards, dict) else 0
        complexity_score = complexity.get("score", 0) if isinstance(complexity, dict) else 0
        testing_score = testing.get("score", 0) if isinstance(testing, dict) else 0
        
        # Calculate weighted score
        overall_score = self._calculate_weighted_score(
            readability_score, standards_score, complexity_score, testing_score
        )
        
        # Compile and return the results
        return {
            "overall_score": round(overall_score, 2),
            "readability": readability_score,
            "standards": standards_score,
            "complexity": complexity_score,
            "testing": testing_score,
            "ai_analysis": {
                "overall_analysis": analysis_json.get("overall_analysis", ""),
                "suggestions": analysis_json.get("suggestions", []),
                "readability_reasoning": readability.get("reasoning", ""),
                "standards_reasoning": standards.get("reasoning", ""),
                "complexity_reasoning": complexity.get("reasoning", ""),
                "testing_reasoning": testing.get("reasoning", "")
            },
            "metrics": file_metrics,
            "repositories_analyzed": 1
        }
    
    def _calculate_weighted_score(self, readability: float, standards: float, 
                                 complexity: float, testing: float) -> float:
        """
        Calculate weighted overall score from component scores.
        
        Args:
            readability: Readability score (0-100)
            standards: Standards score (0-100)
            complexity: Complexity score (0-100)
            testing: Testing score (0-100)
            
        Returns:
            Weighted overall score (0-100)
        """
        # Calculate weighted score based on configuration weights
        weighted_score = (
            self.config.weights["readability"] * (readability / 100) +
            self.config.weights["standards"] * (standards / 100) +
            self.config.weights["complexity"] * (complexity / 100) +
            self.config.weights["testing"] * (testing / 100)
        ) * 100
        
        return weighted_score
    
    def _fallback_code_quality_analysis(self, file_count: int, test_file_count: int, 
                                  doc_file_count: int, code_files_count: int) -> CodeQualityResult:
        """
        Fallback method for code quality analysis using heuristics based on file counts.
        
        Args:
            file_count: Total number of files
            test_file_count: Number of test files
            doc_file_count: Number of documentation files
            code_files_count: Number of code files
            
        Returns:
            CodeQualityResult with heuristic-based scores
        """
        try:
            # Calculate scores using simple heuristics based on file counts
            # More docs = better readability (aim for ~10-20% docs)
            readability_score = min(100, 50 + (doc_file_count / max(1, file_count) * 500))
            
            # More docs = better standards
            standards_score = min(100, 50 + (doc_file_count / max(1, file_count) * 500))
            
            # Aim for ~20% tests
            testing_score = min(100, test_file_count / max(1, file_count) * 500)
            
            # Complexity is hard to measure without deep code analysis, use a placeholder
            complexity_score = 70  # Default score
            
            # Calculate weighted score
            overall_score = self._calculate_weighted_score(
                readability_score, standards_score, complexity_score, testing_score
            )
            
            # Return complete result object
            return {
                "overall_score": round(overall_score, 2),
                "readability": round(readability_score, 2),
                "standards": round(standards_score, 2),
                "complexity": round(complexity_score, 2),
                "testing": round(testing_score, 2),
                "metrics": {
                    "file_count": file_count,
                    "test_file_count": test_file_count,
                    "doc_file_count": doc_file_count,
                    "code_files_analyzed": code_files_count
                },
                "repositories_analyzed": 1,
                "note": "Using file count heuristics for analysis due to unavailable AI processing."
            }
            
        except Exception as e:
            error_msg = f"Error in fallback analysis: {str(e)}"
            print(error_msg)
            
            # Return structured error result
            return {
                "error": error_msg,
                "overall_score": 0,
                "readability": 0,
                "standards": 0,
                "complexity": 0,
                "testing": 0,
                "metrics": {
                    "file_count": file_count,
                    "test_file_count": test_file_count,
                    "doc_file_count": doc_file_count,
                    "code_files_analyzed": 0
                },
                "repositories_analyzed": 0
            }
    
    def _check_celo_integration(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """
        Check if a repository uses Celo blockchain technology using PyGithub and Anthropic.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            Dictionary containing Celo integration information
        """
        # If we don't have direct access to the repository, use AI-based estimation
        if self.repo is None:
            # Get repository information for the prompt
            repo_info = self._get_repository_details(repo_owner, repo_name)
            
            # Special case for Celo organization repos - they are likely to be Celo-related
            if repo_owner.lower() == "celo-org" or "celo" in repo_owner.lower():
                return {
                    "integrated": True,
                    "evidence": [
                        {
                            "file": "Organization name",
                            "keyword": "celo-org"
                        }
                    ],
                    "analysis": f"This repository belongs to the {repo_owner} organization, which is likely related to the Celo blockchain ecosystem. Unable to perform detailed analysis due to API access limitations."
                }
                
            # For other repositories, do a simple check on name/description
            repo_name_lower = repo_name.lower()
            repo_description = repo_info.get("description", "").lower()
            
            # Check for Celo keywords in name or description
            celo_evidence = []
            for keyword in self.celo_keywords:
                if keyword.lower() in repo_name_lower:
                    celo_evidence.append({
                        "file": "Repository name",
                        "keyword": keyword
                    })
                elif keyword.lower() in repo_description:
                    celo_evidence.append({
                        "file": "Repository description",
                        "keyword": keyword
                    })
            
            # If we found evidence, return it
            if celo_evidence:
                return {
                    "integrated": True,
                    "evidence": celo_evidence,
                    "analysis": f"The repository name or description contains Celo-related keywords. Unable to perform detailed analysis due to API access limitations."
                }
            
            # If no basic evidence and we have a LLM, use it for more detailed analysis
            if self.llm is not None:
                keywords_str = ', '.join(self.celo_keywords)
                celo_prompt = ChatPromptTemplate.from_template(
                    f"""You are a blockchain expert tasked with determining if a project is related to the Celo blockchain.
                    
                    Consider the following:
                    1. Does the repository name or organization contain "celo"?
                    2. Does the description mention Celo or related terms?
                    3. Based on your knowledge, is this repository known to be part of the Celo ecosystem?
                    
                    Celo-related keywords include: {keywords_str}
                    
                    Repository: {{repo_owner}}/{{repo_name}}
                    Description: {{repo_description}}
                    
                    I don't have direct access to the code. Make your best assessment based on the name, owner, and description.
                    
                    Respond in JSON format:
                    {{{{
                        "is_celo_integrated": true/false,
                        "confidence": 0-100,
                        "evidence": ["reason1", "reason2", ...],
                        "explanation": "brief explanation"
                    }}}}
                    """
                )
                
                # Run analysis with Anthropic model
                celo_chain = celo_prompt | self.llm | StrOutputParser()
                
                try:
                    celo_result = celo_chain.invoke({
                        "repo_owner": repo_owner,
                        "repo_name": repo_name,
                        "repo_description": repo_info.get("description", "")
                    })
                    celo_json = json.loads(celo_result)
                    
                    is_integrated = celo_json.get("is_celo_integrated", False)
                    confidence = celo_json.get("confidence", 0)
                    
                    # Only report as integrated if confidence is reasonable
                    if is_integrated and confidence > 50:
                        evidence = []
                        for reason in celo_json.get("evidence", []):
                            evidence.append({
                                "file": "AI analysis",
                                "keyword": reason
                            })
                        
                        return {
                            "integrated": True,
                            "evidence": evidence,
                            "analysis": celo_json.get("explanation", "") + " (Note: This is an estimate based on limited information)"
                        }
                except Exception as e:
                    print(f"Error in AI estimation of Celo integration: {str(e)}")
            
            # Default to not integrated if no evidence found
            return {
                "integrated": False,
                "evidence": []
            }
        
        # If we have direct repository access, do more thorough analysis
        integration_evidence = []
        
        try:
            # Check config files for Celo keywords
            for file_path in self.celo_files:
                try:
                    content = self.repo.get_contents(file_path)
                    if content and content.type == "file":
                        content_str = base64.b64decode(content.content).decode('utf-8')
                        for keyword in self.celo_keywords:
                            if keyword.lower() in content_str.lower():
                                integration_evidence.append({
                                    "file": file_path,
                                    "keyword": keyword
                                })
                except Exception:
                    # File doesn't exist, skip
                    continue
            
            # If no evidence found in config files, check README files
            if not integration_evidence:
                readme_files = [
                    "README.md", "README", "Readme.md", "readme.md",
                    "docs/README.md", "docs/Readme.md", "documentation/README.md"
                ]
                
                for readme_file in readme_files:
                    try:
                        content = self.repo.get_contents(readme_file)
                        if content and content.type == "file":
                            content_str = base64.b64decode(content.content).decode('utf-8')
                            for keyword in self.celo_keywords:
                                if keyword.lower() in content_str.lower():
                                    integration_evidence.append({
                                        "file": readme_file,
                                        "keyword": keyword
                                    })
                    except Exception:
                        # File doesn't exist, skip
                        continue
            
            # If still no evidence, search code in all files
            if not integration_evidence:
                # Get all repository contents
                contents = self.repo.get_contents("")
                files_to_process = list(contents)
                processed_paths = set()
                
                # Maximum files to process to avoid excessive API calls
                max_files_to_process = 200
                files_processed = 0
                
                # Process files recursively
                while files_to_process and files_processed < max_files_to_process:
                    content = files_to_process.pop(0)
                    if content.path in processed_paths:
                        continue
                    
                    processed_paths.add(content.path)
                    files_processed += 1
                    
                    if content.type == "dir":
                        try:
                            dir_contents = self.repo.get_contents(content.path)
                            if isinstance(dir_contents, list):
                                files_to_process.extend(dir_contents)
                            else:
                                files_to_process.append(dir_contents)
                        except Exception:
                            # Handle cases where directory access fails
                            continue
                            
                    elif content.type == "file":
                        # Skip binary files and files that are too large
                        if content.path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.gz', '.tar')):
                            continue
                            
                        try:
                            # Read file content
                            file_content = base64.b64decode(content.content).decode('utf-8')
                            
                            # Check for Celo keywords
                            for keyword in self.celo_keywords:
                                if keyword.lower() in file_content.lower():
                                    integration_evidence.append({
                                        "file": content.path,
                                        "keyword": keyword
                                    })
                                    # Once evidence is found for this file, move to next file
                                    break
                        except Exception:
                            # Skip files that can't be decoded
                            continue
            
            # If still no evidence, use AI analysis
            if not integration_evidence:
                # Get repository information for the prompt
                repo_info = self._get_repository_details(repo_owner, repo_name)
                repo_info_str = f"""Repository: {repo_owner}/{repo_name}
                Description: {repo_info.get('description', '')}
                Primary Language: {repo_info.get('language', '')}
                """
                
                # Create prompt for Celo integration search using templates
                system_template = CELO_INTEGRATION_PROMPT.format(
                    keywords=', '.join(self.celo_keywords)
                )
                celo_search_prompt = ChatPromptTemplate.from_messages([
                    ("system", system_template),
                    ("human", HUMAN_CELO_INTEGRATION_PROMPT)
                ])
                
                # Run analysis with Anthropic model
                celo_chain = celo_search_prompt | self.llm | StrOutputParser()
                
                # Get analysis results
                try:
                    celo_result = celo_chain.invoke({
                        "repo_owner": repo_owner,
                        "repo_name": repo_name,
                        "repo_info": repo_info_str
                    })
                    
                    celo_json = json.loads(celo_result)
                    
                    # Use LLM's assessment if it found evidence
                    if celo_json.get("is_celo_integrated", False) and celo_json.get("confidence", 0) > 50:
                        for evidence in celo_json.get("evidence", []):
                            integration_evidence.append({
                                "file": "AI analysis",
                                "keyword": evidence
                            })
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Error parsing LLM response for Celo integration: {str(e)}")
            
            # Determine integration status
            is_integrated = len(integration_evidence) > 0
            
            # If integrated, use LLM to do a deeper analysis
            if is_integrated:
                try:
                    # Create prompt for Celo integration analysis using templates
                    celo_analysis_prompt = ChatPromptTemplate.from_messages([
                        ("system", CELO_ANALYSIS_PROMPT),
                        ("human", HUMAN_CELO_ANALYSIS_PROMPT)
                    ])
                    
                    # Format evidence for the prompt
                    evidence_str = "\n".join([f"- Found '{e['keyword']}' in {e['file']}" for e in integration_evidence])
                    
                    # Run analysis with Anthropic model
                    analysis_chain = celo_analysis_prompt | self.llm | StrOutputParser()
                    analysis = analysis_chain.invoke({"evidence": evidence_str})
                    
                    return {
                        "integrated": is_integrated,
                        "evidence": integration_evidence,
                        "analysis": analysis
                    }
                except Exception as e:
                    print(f"Error in Celo integration analysis: {str(e)}")
                    return {
                        "integrated": is_integrated,
                        "evidence": integration_evidence
                    }
            else:
                return {
                    "integrated": is_integrated,
                    "evidence": integration_evidence
                }
                
        except Exception as e:
            return {
                "error": f"Error checking Celo integration: {str(e)}",
                "integrated": False,
                "evidence": []
            }