"""Real file-system acceptance against the installed package."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main(python):
    console = Path(python).with_name("linkpartition.exe" if os.name == "nt" else "linkpartition")
    subprocess.run([str(console), "--version"], check=True)
    with tempfile.TemporaryDirectory(prefix="hardlink-demo-") as temp:
        source, target = Path(temp) / "source", Path(temp) / "target"
        source.mkdir()
        target.mkdir()
        for tree in (source, target):
            (tree / "first.bin").write_bytes(b"synthetic bytes")
            os.link(tree / "first.bin", tree / "second.bin")
        for state, expected in (("preserved", 0), ("split", 1), ("merged", 1)):
            if state == "split":
                (target / "second.bin").unlink()
                (target / "second.bin").write_bytes(b"synthetic bytes")
            if state == "merged":
                (source / "second.bin").unlink()
                (source / "second.bin").write_bytes(b"synthetic bytes")
                (target / "second.bin").unlink()
                os.link(target / "first.bin", target / "second.bin")
            result = subprocess.run(
                [python, "-m", "linkpartition", str(source), str(target), "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
            if result.returncode != expected:
                raise RuntimeError(f"Wrong exit for {state}: {result.stderr}")
            report = json.loads(result.stdout)
            if report["content_checked"] is not False:
                raise RuntimeError("Misleading content-verification claim")
            print(
                f"{state}: exit {expected}; lost={report['lost_hardlink_pairs']}, "
                f"gained={report['gained_hardlink_pairs']}"
            )


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else sys.executable)
