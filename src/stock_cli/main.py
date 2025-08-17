"""Stock Agent CLI 主入口点"""

from __future__ import annotations

from .cli import app

__all__ = ["app"]

if __name__ == "__main__":
    from .cli import main
    main()