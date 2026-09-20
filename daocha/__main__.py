"""python -m daocha"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daocha", description="倒插文献桌面工具")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="用浏览器打开，而不是独立窗口",
    )
    args = parser.parse_args(argv)

    from daocha.app import run_app

    run_app(browser=args.browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
