"""python -m citeverify"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="citeverify", description="引文核实桌面工具")
    parser.add_argument(
        "--browser",
        action="store_true",
        help="用浏览器打开，而不是独立窗口",
    )
    args = parser.parse_args(argv)

    from citeverify.app import run_app

    run_app(browser=args.browser)
    return 0


if __name__ == "__main__":
    sys.exit(main())
