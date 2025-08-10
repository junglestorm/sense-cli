"""Stock CLI command line interface."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from main import app


def main():
    """Entry point for stock-cli command."""
    app()


if __name__ == "__main__":
    main()
