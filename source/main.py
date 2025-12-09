"""
Photo-Timestamper 入口点
"""

import sys
from pathlib import Path

# 确保可以导入 source 包
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent))

from source.ui import run_app


def main():
    """程序主入口"""
    run_app()


if __name__ == "__main__":
    main()