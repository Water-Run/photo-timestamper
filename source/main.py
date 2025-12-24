"""
Photo-Timestamper Entry Point&入口点
"""

import sys
from pathlib import Path

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from source.ui import run_app


def main():
    """Program main entry&程序主入口"""
    run_app()


if __name__ == "__main__":
    main()
    