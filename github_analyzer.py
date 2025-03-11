import os
import json
import base64
from github import Github, GithubException
from typing import Dict, List, Tuple, Any, Optional


class GitHubAnalyzer:
    """Class to analyze GitHub repositories for code quality and Celo integration."""
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize the GitHub analyzer with configuration.
        
        Args:
            config_path: Path to the configuration file
        """
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
            
        # Initialize GitHub client
        self.github_token = self.config.get("github_token", "")
        self.github = Github(self.github_token) if self.github_token else Github()
        
        # Set up analysis parameters
        self.weights = self.config["weights"]
        self.celo_keywords = self.config["celo_keywords"]
        self.celo_files = self.config["celo_files"]
        
    def analyze_repository(self, repo_url: str) -> Dict[str, Any]:
        """
        Analyze a GitHub repository for code quality and Celo integration.
        
        Args:
            repo_url: URL of the GitHub repository
            
        Returns:
            Dictionary containing analysis results
        """
        try:
            # Extract repo owner and name from URL
            repo_parts = repo_url.strip("/").split("/")
            if "github.com" not in repo_url or len(repo_parts) < 5:
                return {
                    "error": f"Invalid GitHub URL: {repo_url}",
                    "code_quality": 0,
                    "celo_integration": False
                }
            
            repo_owner = repo_parts[-2]
            repo_name = repo_parts[-1]
            
            # Get repository
            repo = self.github.get_repo(f"{repo_owner}/{repo_name}")
            
            # Check if repository is private
            if repo.private:
                return {
                    "error": "Repository is private and cannot be accessed",
                    "code_quality": 0,
                    "celo_integration": False
                }
                
            # Get repository details
            repo_details = {
                "name": repo.name,
                "description": repo.description,
                "url": repo.html_url,
                "stars": repo.stargazers_count,
                "forks": repo.forks_count,
                "open_issues": repo.open_issues_count,
                "last_update": repo.updated_at.isoformat(),
                "language": repo.language
            }
            
            # Analyze code quality
            code_quality = self._analyze_code_quality(repo)
            
            # Check for Celo integration
            celo_integration = self._check_celo_integration(repo)
            
            # Compile results
            results = {
                "repo_details": repo_details,
                "code_quality": code_quality,
                "celo_integration": celo_integration
            }
            
            return results
            
        except GithubException as e:
            return {
                "error": f"GitHub API error: {str(e)}",
                "code_quality": 0,
                "celo_integration": False
            }
        except Exception as e:
            return {
                "error": f"Error analyzing repository: {str(e)}",
                "code_quality": 0,
                "celo_integration": False
            }
            
    def _analyze_code_quality(self, repo) -> Dict[str, Any]:
        """
        Analyze the code quality of a repository.
        
        Args:
            repo: GitHub repository object
            
        Returns:
            Dictionary containing code quality scores
        """
        try:
            # Get repository contents
            contents = repo.get_contents("")
            file_count = 0
            test_file_count = 0
            doc_file_count = 0
            comment_lines = 0
            code_lines = 0
            
            # Process files recursively
            files_to_process = list(contents)
            processed_paths = set()
            
            while files_to_process:
                content = files_to_process.pop(0)
                if content.path in processed_paths:
                    continue
                
                processed_paths.add(content.path)
                
                if content.type == "dir":
                    try:
                        dir_contents = repo.get_contents(content.path)
                        if isinstance(dir_contents, list):
                            files_to_process.extend(dir_contents)
                        else:
                            files_to_process.append(dir_contents)
                    except GithubException:
                        # Handle cases where directory access fails
                        continue
                        
                elif content.type == "file":
                    file_count += 1
                    
                    # Check if it's a test file
                    if "test" in content.path.lower() or "spec" in content.path.lower():
                        test_file_count += 1
                        
                    # Check if it's a documentation file
                    if content.path.lower().endswith((".md", ".rst", ".txt", ".doc", ".docx")):
                        doc_file_count += 1
                        
                    # Analyze code file content
                    if content.path.lower().endswith((".js", ".ts", ".jsx", ".tsx", ".py", ".java", ".sol", ".go", ".rb", ".php", ".c", ".cpp", ".cs")):
                        try:
                            file_content = repo.get_contents(content.path).decoded_content.decode('utf-8')
                            lines = file_content.split('\n')
                            code_lines += len(lines)
                            
                            # Count comment lines (simple heuristic)
                            comment_lines += sum(1 for line in lines if line.strip().startswith(('//', '#', '/*', '*', '"""', "'''", '<!--')))
                            
                        except (GithubException, UnicodeDecodeError):
                            # Skip files that can't be decoded
                            continue
            
            # Calculate scores (simple heuristics, can be improved)
            readability_score = min(1.0, comment_lines / max(1, code_lines) * 5)  # Aim for ~20% comments
            standards_score = min(1.0, doc_file_count / max(1, file_count) * 10)  # Aim for ~10% docs
            testing_score = min(1.0, test_file_count / max(1, file_count) * 5)  # Aim for ~20% tests
            
            # Complexity is hard to measure without deep code analysis, use a placeholder
            complexity_score = 0.7  # Default score
            
            # Calculate weighted score
            overall_score = (
                self.weights["readability"] * readability_score +
                self.weights["standards"] * standards_score +
                self.weights["complexity"] * complexity_score +
                self.weights["testing"] * testing_score
            ) * 100
            
            return {
                "overall_score": round(overall_score, 2),
                "readability": round(readability_score * 100, 2),
                "standards": round(standards_score * 100, 2),
                "complexity": round(complexity_score * 100, 2),
                "testing": round(testing_score * 100, 2),
                "metrics": {
                    "file_count": file_count,
                    "test_file_count": test_file_count,
                    "doc_file_count": doc_file_count,
                    "code_lines": code_lines,
                    "comment_lines": comment_lines
                }
            }
            
        except Exception as e:
            # Return zero scores on error
            return {
                "error": f"Error analyzing code quality: {str(e)}",
                "overall_score": 0,
                "readability": 0,
                "standards": 0,
                "complexity": 0,
                "testing": 0,
                "metrics": {}
            }
    
    def _check_celo_integration(self, repo) -> Dict[str, Any]:
        """
        Check if a repository uses Celo blockchain technology.
        
        Args:
            repo: GitHub repository object
            
        Returns:
            Dictionary containing Celo integration information
        """
        integration_evidence = []
        
        try:
            # Check specific important files first
            for file_path in self.celo_files:
                try:
                    content = repo.get_contents(file_path)
                    if content and content.type == "file":
                        content_str = base64.b64decode(content.content).decode('utf-8')
                        for keyword in self.celo_keywords:
                            if keyword.lower() in content_str.lower():
                                integration_evidence.append({
                                    "file": file_path,
                                    "keyword": keyword
                                })
                except GithubException:
                    # File doesn't exist, skip
                    continue
            
            # Search for keywords in README files
            try:
                readme_files = [
                    "README.md", "README", "Readme.md", "readme.md",
                    "docs/README.md", "docs/Readme.md", "documentation/README.md"
                ]
                
                for readme_file in readme_files:
                    try:
                        content = repo.get_contents(readme_file)
                        if content and content.type == "file":
                            content_str = base64.b64decode(content.content).decode('utf-8')
                            for keyword in self.celo_keywords:
                                if keyword.lower() in content_str.lower():
                                    integration_evidence.append({
                                        "file": readme_file,
                                        "keyword": keyword
                                    })
                    except GithubException:
                        # File doesn't exist, skip
                        continue
            except Exception:
                # Couldn't find or parse README
                pass
            
            # Check code search API for Celo keywords
            # Note: GitHub's search API has rate limits
            # This is a simplified implementation
            try:
                # Search for Celo keywords in code
                for keyword in self.celo_keywords:
                    query = f"repo:{repo.full_name} {keyword}"
                    results = self.github.search_code(query)
                    count = min(results.totalCount, 10)  # Limit to avoid excessive API calls
                    
                    if count > 0:
                        for i in range(count):
                            try:
                                item = results[i]
                                integration_evidence.append({
                                    "file": item.path,
                                    "keyword": keyword
                                })
                            except GithubException:
                                # Skip errors in processing individual results
                                continue
            except GithubException:
                # Search API may return errors or rate limit exceeded
                pass
                
            # Determine integration status
            is_integrated = len(integration_evidence) > 0
            
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