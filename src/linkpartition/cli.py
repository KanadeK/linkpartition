import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import InputError, audit


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare hardlink partitions in two stable local trees"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        report = audit(args.source, args.target)
    except (InputError, OSError) as exc:
        detail = str(exc) if isinstance(exc, InputError) else "filesystem_observation_failed"
        print("Input error: " + detail, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for witness in report["witnesses"]:
            print(witness["kind"] + ": " + json.dumps(witness["paths"], ensure_ascii=True))
        print(
            f"{report['status'].upper()}: lost pairs={report['lost_hardlink_pairs']}, "
            f"gained pairs={report['gained_hardlink_pairs']}, "
            f"missing={report['missing_count']}, added={report['added_count']}"
        )
        print("File contents were not checked.")
    return 0 if report["status"] == "passed" else 1
