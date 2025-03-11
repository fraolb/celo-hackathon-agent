import os
import json
import base64
import re
import time
import threading
from typing import Dict, List, Tuple, Any, Optional
from dotenv import load_dotenv
from pathlib import Path
import signal

# LangChain imports
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# LangChain GitHub toolkit imports
from langchain_community.agent_toolkits.github.toolkit import GitHubToolkit
from langchain_community.utilities.github import GitHubAPIWrapper
from langgraph.prebuilt import create_react_agent

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


# Timeout decorator
class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("Function execution timed out")


def with_timeout(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Set the timeout handler
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
    Run a function with periodic spinner updates without using threads.
    
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
        # For functions that might take a long time, we can't do much without threading
        # Just run the function and let the spinner animation happen before and after
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


class GitHubLangChainAnalyzer:
    """Class to analyze GitHub repositories for code quality and Celo integration using LangChain's GitHub toolkit."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the GitHub analyzer with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        # Set up analysis parameters
        self.weights = self.config["weights"]
        self.celo_keywords = self.config["celo_keywords"]
        self.celo_files = self.config["celo_files"]
        
        # Set up GitHub token from environment or config
        self.github_token = os.environ.get("GITHUB_TOKEN") or self.config.get("github_token", "")
        if not self.github_token:
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
                    model="claude-3-haiku-20240307",
                    temperature=0.1,
                    anthropic_api_key=self.anthropic_api_key
                )
            except Exception as e:
                print(f"Error initializing Claude model: {str(e)}")
                print("Using fallback analysis methods only.")
        
        # Initialize GitHub toolkit
        self.github_api = None
        self.github_toolkit = None
        self.github_agent = None
        
    def _setup_github_tools(self, repo_url: str):
        """
        Set up GitHub tools with the correct repository.
        
        Args:
            repo_url: URL of the GitHub repository
        """
        # Extract repo owner and name from URL
        repo_parts = repo_url.strip("/").split("/")
        if "github.com" not in repo_url or len(repo_parts) < 5:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        repo_owner = repo_parts[-2]
        repo_name = repo_parts[-1]
        
        # If we have no token, we can still use some repository information
        if not self.github_token:
            print(f"No GitHub token provided. Using limited repository information for {repo_owner}/{repo_name}")
            self.repo = None
            self.repo_owner = repo_owner
            self.repo_name = repo_name
            return repo_owner, repo_name
        
        # If we have a token, use PyGithub for direct access
        try:
            from github import Github
            
            # Initialize GitHub client
            g = Github(self.github_token)
            
            # Get repository
            repo = g.get_repo(f"{repo_owner}/{repo_name}")
            
            # Simple check if repository exists and is accessible
            _ = repo.name
            
            # Repository is accessible, store it for later use
            self.repo = repo
            self.repo_owner = repo_owner
            self.repo_name = repo_name
            return repo_owner, repo_name
            
        except Exception as e:
            print(f"Error accessing repository: {str(e)}")
            # Return basic information even if authentication fails
            self.repo = None
            self.repo_owner = repo_owner
            self.repo_name = repo_name
            return repo_owner, repo_name
            
    def _analyze_repository_manually(self, repo):
        """
        Analyze a repository manually using PyGithub.
        
        Args:
            repo: GitHub repository object
            
        Returns:
            Tuple of repository owner and name
        """
        # Store repo information
        self.repo = repo
        self.repo_owner = repo.owner.login
        self.repo_name = repo.name
        
        return self.repo_owner, self.repo_name
        
    def analyze_repository(self, repo_url: str, callback=None) -> Dict[str, Any]:
        """
        Analyze a GitHub repository for code quality and Celo integration.
        
        Args:
            repo_url: URL of the GitHub repository
            callback: Optional callback function to report progress
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Setup GitHub toolkit and get repo information
            if callback:
                callback(f"Setting up GitHub tools for {repo_url}")
            
            repo_owner, repo_name = self._setup_github_tools(repo_url)
            
            # Get repository details (timeout: 30 seconds)
            if callback:
                callback(f"Fetching repository details for {repo_owner}/{repo_name}")
                
                # Run repository details fetch with active spinner
                repo_details = run_with_active_spinner(
                    func=self._get_repository_details_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Fetching repository details for {repo_owner}/{repo_name}",
                    callback=callback
                )
            else:
                repo_details = self._get_repository_details_with_timeout(repo_owner, repo_name)
            if repo_details is None:
                repo_details = {
                    "name": repo_name,
                    "description": f"Repository for {repo_owner}/{repo_name}",
                    "url": repo_url,
                    "stars": 0,
                    "forks": 0,
                    "open_issues": 0,
                    "last_update": "",
                    "language": ""
                }
            
            # Analyze code quality using LangChain and Anthropic (timeout: 60 seconds) with continuous spinner updates
            if callback:
                callback(f"Analyzing code quality for {repo_owner}/{repo_name}")
                
                # Run code quality analysis with active spinner
                code_quality = run_with_active_spinner(
                    func=self._analyze_code_quality_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Analyzing code quality for {repo_owner}/{repo_name}",
                    callback=callback
                )
            else:
                code_quality = self._analyze_code_quality_with_timeout(repo_owner, repo_name)
            if code_quality is None:
                code_quality = {
                    "overall_score": 50,
                    "readability": 50,
                    "standards": 50,
                    "complexity": 50,
                    "testing": 50,
                    "metrics": {
                        "file_count": 0,
                        "test_file_count": 0,
                        "doc_file_count": 0
                    },
                    "error": "Analysis timed out"
                }
            
            # Check for Celo integration (timeout: 60 seconds) with continuous spinner updates
            if callback:
                callback(f"Checking Celo integration for {repo_owner}/{repo_name}")
                
                # Run Celo integration check with active spinner
                celo_integration = run_with_active_spinner(
                    func=self._check_celo_integration_with_timeout,
                    args=(repo_owner, repo_name),
                    message=f"Checking Celo integration for {repo_owner}/{repo_name}",
                    callback=callback
                )
            else:
                celo_integration = self._check_celo_integration_with_timeout(repo_owner, repo_name)
            if celo_integration is None:
                celo_integration = {
                    "integrated": repo_owner.lower() == "celo-org" or "celo" in repo_name.lower(),
                    "evidence": [],
                    "error": "Analysis timed out"
                }
            
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
                "code_quality": 0,
                "celo_integration": False
            }
    
    @with_timeout(30)
    def _get_repository_details_with_timeout(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Timeout wrapper for _get_repository_details"""
        return self._get_repository_details(repo_owner, repo_name)
        
    @with_timeout(60)
    def _analyze_code_quality_with_timeout(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Timeout wrapper for _analyze_code_quality"""
        return self._analyze_code_quality(repo_owner, repo_name)
        
    @with_timeout(60)
    def _check_celo_integration_with_timeout(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """Timeout wrapper for _check_celo_integration"""
        return self._check_celo_integration(repo_owner, repo_name)
        
    def _get_repository_details(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """
        Get repository details using PyGithub.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            Dictionary containing repository details
        """
        # Fallback values if we can't access the repository
        fallback_info = {
            "name": repo_name,
            "description": "",
            "url": f"https://github.com/{repo_owner}/{repo_name}",
            "stars": 0,
            "forks": 0,
            "open_issues": 0,
            "last_update": "",
            "language": ""
        }
        
        # If we don't have the repo object, return fallback info
        if self.repo is None:
            return fallback_info
        
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
            print(f"Error getting repository details: {str(e)}")
            return fallback_info
            
    def _analyze_code_quality(self, repo_owner: str, repo_name: str) -> Dict[str, Any]:
        """
        Analyze the code quality of a repository using PyGithub and Anthropic.
        
        Args:
            repo_owner: Owner of the repository
            repo_name: Name of the repository
            
        Returns:
            Dictionary containing code quality scores
        """
        # If we don't have access to the repository, use alternative methods
        if self.repo is None:
            # Get basic repository info
            repo_info = self._get_repository_details(repo_owner, repo_name)
            
            # If we have a working LLM, use it for estimation
            if self.llm is not None:
                # Create a prompt asking for a rough estimate based on repository name and metadata
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
                
                # Run analysis with Anthropic model
                analysis_chain = quality_prompt | self.llm | StrOutputParser()
                
                try:
                    analysis_result = analysis_chain.invoke({
                        "repo_owner": repo_owner,
                        "repo_name": repo_name,
                        "repo_description": repo_info.get("description", "")
                    })
                    analysis_json = json.loads(analysis_result)
                    
                    # Extract scores
                    readability_score = analysis_json.get("readability", {}).get("score", 0)
                    standards_score = analysis_json.get("standards", {}).get("score", 0)
                    complexity_score = analysis_json.get("complexity", {}).get("score", 0)
                    testing_score = analysis_json.get("testing", {}).get("score", 0)
                    
                    # Calculate weighted score
                    overall_score = (
                        self.weights["readability"] * (readability_score / 100) +
                        self.weights["standards"] * (standards_score / 100) +
                        self.weights["complexity"] * (complexity_score / 100) +
                        self.weights["testing"] * (testing_score / 100)
                    ) * 100
                    
                    return {
                        "overall_score": round(overall_score, 2),
                        "readability": readability_score,
                        "standards": standards_score,
                        "complexity": complexity_score,
                        "testing": testing_score,
                        "ai_analysis": {
                            "overall_analysis": analysis_json.get("overall_analysis", "") + " (Note: This is an estimate based on limited information)",
                            "suggestions": analysis_json.get("suggestions", []),
                            "readability_reasoning": analysis_json.get("readability", {}).get("reasoning", ""),
                            "standards_reasoning": analysis_json.get("standards", {}).get("reasoning", ""),
                            "complexity_reasoning": analysis_json.get("complexity", {}).get("reasoning", ""),
                            "testing_reasoning": analysis_json.get("testing", {}).get("reasoning", "")
                        },
                        "metrics": {
                            "file_count": 0,
                            "test_file_count": 0,
                            "doc_file_count": 0,
                            "code_files_analyzed": 0
                        },
                        "note": "This analysis is based on AI estimation as direct repository access was not available."
                    }
                except Exception as e:
                    print(f"Error in AI estimation: {str(e)}")
            
            # If LLM is not available or failed, use fallback
            repo_name_lower = repo_name.lower()
            # Simple heuristic based on repository name
            # Check for keywords that might indicate quality code
            quality_indicators = ["awesome", "framework", "official", "production", "stable"]
            quality_score = 0
            
            for indicator in quality_indicators:
                if indicator in repo_name_lower or indicator in repo_owner.lower():
                    quality_score += 15
            
            # Premium on official organization repos
            if repo_owner.lower() in ["microsoft", "google", "facebook", "apple", "amazon", "celo-org"]:
                quality_score += 30
                
            # Cap at 85 - we can't give a perfect score without seeing the code
            quality_score = min(85, quality_score)
            
            # If we found no indicators, give a baseline score
            if quality_score == 0:
                quality_score = 50
            
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
                "note": "This is a basic estimate as direct repository access was not available and AI analysis is disabled."
            }
        
        # If we have access to the repository, perform direct analysis
        try:
            # Get repository contents
            contents = self.repo.get_contents("")
            
            # Count different file types
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
                    file_count += 1
                    file_path = content.path
                    
                    # Check if it's a test file
                    if "test" in file_path.lower() or "spec" in file_path.lower():
                        test_file_count += 1
                        
                    # Check if it's a documentation file
                    if file_path.lower().endswith((".md", ".rst", ".txt", ".doc", ".docx")):
                        doc_file_count += 1
                        
                    # Analyze code file content
                    if file_path.lower().endswith((".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".sol", ".go", ".rb", ".php", ".c", ".cpp", ".cs")):
                        try:
                            # Add to code file paths for potential analysis
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
            
            # Combine all code samples for analysis
            code_sample_text = "\n".join(code_samples)
            
            # If we have code samples and a working LLM, use AI analysis
            if code_samples and self.llm is not None:
                # Create prompt for code quality analysis using templates
                quality_prompt = ChatPromptTemplate.from_messages([
                    ("system", CODE_QUALITY_PROMPT),
                    ("human", HUMAN_CODE_QUALITY_PROMPT)
                ])
                
                # Run analysis with Anthropic model
                analysis_chain = quality_prompt | self.llm | StrOutputParser()
                
                # Get analysis results
                try:
                    analysis_result = analysis_chain.invoke({"code_samples": code_sample_text})
                    analysis_json = json.loads(analysis_result)
                    
                    # Extract scores
                    readability_score = analysis_json.get("readability", {}).get("score", 0)
                    standards_score = analysis_json.get("standards", {}).get("score", 0)
                    complexity_score = analysis_json.get("complexity", {}).get("score", 0)
                    testing_score = analysis_json.get("testing", {}).get("score", 0)
                    
                    # Calculate weighted score
                    overall_score = (
                        self.weights["readability"] * (readability_score / 100) +
                        self.weights["standards"] * (standards_score / 100) +
                        self.weights["complexity"] * (complexity_score / 100) +
                        self.weights["testing"] * (testing_score / 100)
                    ) * 100
                    
                    return {
                        "overall_score": round(overall_score, 2),
                        "readability": readability_score,
                        "standards": standards_score,
                        "complexity": complexity_score,
                        "testing": testing_score,
                        "ai_analysis": {
                            "overall_analysis": analysis_json.get("overall_analysis", ""),
                            "suggestions": analysis_json.get("suggestions", []),
                            "readability_reasoning": analysis_json.get("readability", {}).get("reasoning", ""),
                            "standards_reasoning": analysis_json.get("standards", {}).get("reasoning", ""),
                            "complexity_reasoning": analysis_json.get("complexity", {}).get("reasoning", ""),
                            "testing_reasoning": analysis_json.get("testing", {}).get("reasoning", "")
                        },
                        "metrics": {
                            "file_count": file_count,
                            "test_file_count": test_file_count,
                            "doc_file_count": doc_file_count,
                            "code_files_analyzed": len(code_samples)
                        }
                    }
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Error parsing LLM response: {str(e)}")
                    
            # If no LLM or LLM analysis failed but we have code samples,
            # do a basic analysis based on test/doc counts
            
            # Fallback to heuristic-based analysis if no code samples or analysis failed
            return self._fallback_code_quality_analysis(
                file_count, test_file_count, doc_file_count, len(code_file_paths)
            )
            
        except Exception as e:
            # Return zero scores on error
            print(f"Error in code quality analysis: {str(e)}")
            return {
                "error": f"Error analyzing code quality: {str(e)}",
                "overall_score": 0,
                "readability": 0,
                "standards": 0,
                "complexity": 0,
                "testing": 0,
                "metrics": {}
            }
    
    def _fallback_code_quality_analysis(self, file_count, test_file_count, doc_file_count, code_files_count):
        """
        Fallback method for code quality analysis using heuristics.
        
        Args:
            file_count: Total number of files
            test_file_count: Number of test files
            doc_file_count: Number of documentation files
            code_files_count: Number of code files
            
        Returns:
            Dictionary containing code quality scores
        """
        try:
            # Calculate scores using simple heuristics based on file counts
            readability_score = min(100, 50 + (doc_file_count / max(1, file_count) * 500))  # More docs = better readability
            standards_score = min(100, 50 + (doc_file_count / max(1, file_count) * 500))  # More docs = better standards
            testing_score = min(100, test_file_count / max(1, file_count) * 500)  # Aim for ~20% tests
            
            # Complexity is hard to measure without deep code analysis, use a placeholder
            complexity_score = 70  # Default score
            
            # Calculate weighted score
            overall_score = (
                self.weights["readability"] * (readability_score / 100) +
                self.weights["standards"] * (standards_score / 100) +
                self.weights["complexity"] * (complexity_score / 100) +
                self.weights["testing"] * (testing_score / 100)
            ) * 100
            
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
                "note": "Using fallback analysis method due to LLM processing error."
            }
            
        except Exception as e:
            # Return zero scores on error
            return {
                "error": f"Error in fallback analysis: {str(e)}",
                "overall_score": 0,
                "readability": 0,
                "standards": 0,
                "complexity": 0,
                "testing": 0,
                "metrics": {}
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