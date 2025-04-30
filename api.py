import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware 
from pydantic import BaseModel
import subprocess
from typing import Optional
from datetime import datetime

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-nextjs-app.vercel.app"],  # Your Next.js frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

class AnalysisRequest(BaseModel):
    github_urls: str
    prompt: str = "prompts/default.txt"
    model: Optional[str] = None
    temperature: Optional[float] = None
    json: bool = False

def find_latest_report_dir(base_dir="reports"):
    """Find the most recently created report directory"""
    dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
    dirs.sort(key=lambda x: os.path.getmtime(os.path.join(base_dir, x)), reverse=True)
    return os.path.join(base_dir, dirs[0]) if dirs else None

@app.post("/analyze")
async def analyze_code(request: AnalysisRequest):
    try:
        # Run the analysis
        cmd = [
            "uv", "run", "main.py",
            "--github-urls", request.github_urls,
            "--prompt", request.prompt,
        ]
        if request.model:
            cmd.extend(["--model", request.model])
        if request.temperature:
            cmd.extend(["--temperature", str(request.temperature)])
        if request.json:
            cmd.append("--json")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        # Verify the command succeeded
        if result.returncode != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Analysis failed: {result.stderr}"
            )

        # Find and read the generated reports
        report_dir = find_latest_report_dir()
        if not report_dir:
            raise HTTPException(
                status_code=500,
                detail="Report directory not found"
            )

        # Get all .md files in the directory
        report_files = [f for f in os.listdir(report_dir) if f.endswith(".md")]
        reports = {}
        for file in report_files:
            with open(os.path.join(report_dir, file), "r", encoding="utf-8") as f:
                reports[file] = f.read()

        return {
            "success": True,
            "reports": reports,
            "report_dir": report_dir
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )
    try:
        cmd = [
            "uv", "run", "main.py",
            "--github-urls", request.github_urls,
            "--prompt", request.prompt,
        ]
        if request.model:
            cmd.extend(["--model", request.model])
        if request.temperature:
            cmd.extend(["--temperature", str(request.temperature)])
        if request.json:
            cmd.append("--json") 

        # Add encoding and error handling to subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Force UTF-8 encoding
            errors="replace",  # Replace undecodable characters with a placeholder
            check=True
        )

        return {
            "success": True,
            "output": result.stdout,
            "report_path": "reports/"  # Update with your actual path logic
        }
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis failed: {e.stderr}"
        )
    """Endpoint to analyze GitHub repositories."""
    try:
        # Build the command to run your existing script
        cmd = [
            "uv", "run", "main.py",
            "--github-urls", request.github_urls,
            "--prompt", request.prompt,
        ]
        
        # Add optional arguments
        if request.model:
            cmd.extend(["--model", request.model])
        if request.temperature:
            cmd.extend(["--temperature", str(request.temperature)])
        if request.json:
            cmd.append("--json")

        # Run the subprocess (your existing CLI logic)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Return the output (modify based on your needs)
        return {
            "success": True,
            "output": result.stdout,
            "report_path": "reports/"  # Update with actual path logic
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis failed: {e.stderr}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}"
        )