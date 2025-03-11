"""
Legacy entry point for backward compatibility.
This file now redirects to the refactored implementation.
"""

import sys
from src.main import main

if __name__ == "__main__":
    print("Note: This entry point is maintained for backward compatibility.")
    print("For new projects, use 'python run.py' instead.")
    sys.exit(main())