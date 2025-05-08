#!/usr/bin/env python3
"""
AI Project Analyzer API - Analyze GitHub projects using LLMs
"""

import sys
import io
import os
import logging
import time
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors="replace")

# Import your existing modules
from src.config import (
    setup_logging,
    get_default_model,
    get_default_temperature,
    get_github_token,
)
from src.fetcher import fetch_single_repository
from src.analyzer import analyze_single_repository, AVAILABLE_MODELS

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://gitspect.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalysisRequest(BaseModel):
    github_urls: str
    prompt: str = "prompts/default.txt"
    model: Optional[str] = None
    temperature: Optional[float] = None
    json: bool = False
    no_metrics: bool = False

class AnalysisResponse(BaseModel):
    success: bool
    analyses: Dict[str, Any]
    total_repos: int
    completed_repos: int
    execution_time: float
    error: Optional[str] = None

@app.post("/analyze", response_model=AnalysisResponse)
async def analyze_code(request: AnalysisRequest):
    """Endpoint to analyze GitHub repositories"""
    start_time = time.time()
    
    # Setup logging
    setup_logging("INFO")  # Or use a configurable log level
    
    try:
        # Parse GitHub URLs
        github_urls = [url.strip() for url in request.github_urls.split(",")] if request.github_urls else []
        if not github_urls:
            return {
                "success": False,
                "analyses": {},
                "total_repos": 0,
                "completed_repos": 0,
                "execution_time": time.time() - start_time,
                "error": "No GitHub URLs provided"
            }

        # Set defaults
        model = request.model or get_default_model()
        temperature = request.temperature or get_default_temperature()
        github_token = get_github_token()
        include_metrics = not request.no_metrics
        
        logging.info(f"Starting analysis with model: {model}, temperature: {temperature}")
        if request.json:
            logging.info("Using JSON output format")

        # Track progress
        total_repos = len(github_urls)
        completed_repos = 0
        all_analyses = {}

        # Process each repository
        for url in github_urls:
            try:
                logging.info(f"Processing repository {completed_repos + 1}/{total_repos}: {url}")
                
                # Fetch repository content
                repo_name, repo_data = fetch_single_repository(
                    url, 
                    include_metrics=include_metrics, 
                    github_token=github_token
                )
                
                if not repo_data or not repo_data["content"] or repo_data["content"].startswith("Error:"):
                    logging.error(f"Failed to fetch repository: {url}")
                    continue
                
                # Analyze repository
                analysis = analyze_single_repository(
                    repo_name,
                    repo_data["content"],
                    request.prompt,
                    model_name=model,
                    temperature=temperature,
                    output_json=request.json,
                    metrics_data=repo_data.get("metrics", {}),
                )
                
                completed_repos += 1
                all_analyses[repo_name] = analysis
                
            except Exception as e:
                logging.error(f"Error processing {url}: {str(e)}")
                continue

        execution_time = time.time() - start_time
        logging.info(f"Completed {completed_repos}/{total_repos} repositories in {execution_time:.2f} seconds")
        
        if completed_repos == 0:
            return {
                "success": False,
                "analyses": {},
                "total_repos": total_repos,
                "completed_repos": 0,
                "execution_time": execution_time,
                "error": "No repositories were successfully analyzed"
            }
        
        return {
            "success": True,
            "analyses": all_analyses,
            "total_repos": total_repos,
            "completed_repos": completed_repos,
            "execution_time": execution_time,
            "error": None
        }
        
    except Exception as e:
        return {
            "success": False,
            "analyses": {},
            "total_repos": 0,
            "completed_repos": 0,
            "execution_time": time.time() - start_time,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)