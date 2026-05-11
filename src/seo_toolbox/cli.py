import argparse
import sys

from seo_toolbox.commands import cluster as cluster_cmd
from seo_toolbox.commands import init as init_cmd
from seo_toolbox.commands import rank_check as rank_check_cmd


def main() -> int:
    parser = argparse.ArgumentParser(prog="seo", description="SEO toolbox CLI")
    parser.add_argument("--version", action="version", version="0.1.0")
    sub = parser.add_subparsers(dest="command", required=True)
    init_cmd.add_subparser(sub)
    rank_check_cmd.add_subparser(sub)
    cluster_cmd.add_subparser(sub)

    args = parser.parse_args()
    handler = getattr(args, "handler", None)
    if not handler:
        parser.error(f"no handler for command {args.command}")
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
