"""
GitHub repository access utilities.
"""

import base64
from typing import Dict, List, Tuple, Any, Optional

from src.models.types import RepoDetails
from src.models.config import Config
from src.utils.timeout import GitHubAccessError, with_timeout


class GitHubRepository:
    """Class for interacting with GitHub repositories."""
    
    def __init__(self, config: Config):
        """
        Initialize with configuration.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.repo = None
        self.repo_owner = None
        self.repo_name = None
    
    def parse_github_url(self, repo_url: str) -> Tuple[str, str]:
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
    
    def connect_to_github_api(self, repo_owner: str, repo_name: str) -> Any:
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
    
    def setup_repository(self, repo_url: str) -> Tuple[str, str]:
        """
        Set up GitHub connection for a repository.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            Tuple of repository owner and name
        """
        # Parse GitHub URL to get owner and name
        repo_owner, repo_name = self.parse_github_url(repo_url)
        
        try:
            # Connect to GitHub API and get repository object
            self.repo = self.connect_to_github_api(repo_owner, repo_name)
        except GitHubAccessError:
            # If we can't access the repository, set repo to None
            self.repo = None
        
        # Store repository info regardless of API success
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        
        return repo_owner, repo_name
    
    def create_fallback_repo_details(self, repo_owner: str, repo_name: str, repo_url: str) -> RepoDetails:
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
    
    @with_timeout(30)
    def get_repository_details(self) -> RepoDetails:
        """
        Get repository details using GitHub API.
        
        Returns:
            RepoDetails with repository information
        """
        # If we don't have the repo object, return fallback info
        if self.repo is None:
            return self.create_fallback_repo_details(
                self.repo_owner, 
                self.repo_name, 
                f"https://github.com/{self.repo_owner}/{self.repo_name}"
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
    
    def collect_code_samples(self) -> Tuple[Dict[str, int], List[str]]:
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
        
    def search_files_for_keywords(self, file_paths: List[str], keywords: List[str]) -> List[Dict[str, str]]:
        """
        Search specific files for keywords.
        
        Args:
            file_paths: List of file paths to search
            keywords: List of keywords to search for
            
        Returns:
            List of evidence dictionaries
        """
        evidence = []
        
        for file_path in file_paths:
            try:
                content = self.repo.get_contents(file_path)
                if content and content.type == "file":
                    content_str = base64.b64decode(content.content).decode('utf-8')
                    for keyword in keywords:
                        if keyword.lower() in content_str.lower():
                            evidence.append({
                                "file": file_path,
                                "keyword": keyword
                            })
            except Exception:
                # File doesn't exist, skip
                continue
                
        return evidence