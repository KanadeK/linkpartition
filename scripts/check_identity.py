"""Enforce the owner's explicit commit-identity policy on complete Git history."""

import re
import subprocess

OWNER = "KanadeK"
EMAIL = "121669563+KanadeK@users.noreply.github.com"
history = subprocess.run(
    ["git", "log", "--all", "--format=%an%x09%ae%x09%cn%x09%ce"],
    capture_output=True,
    text=True,
    check=True,
).stdout.splitlines()
if not history or any(row.split("\t") != [OWNER, EMAIL, OWNER, EMAIL] for row in history):
    raise SystemExit("Unexpected Author or Committer identity")
messages = subprocess.run(
    ["git", "log", "--all", "--format=%B"], capture_output=True, text=True, check=True
).stdout
if re.search(r"co-authored-by\s*:", messages, re.I):
    raise SystemExit("Co-author trailer is prohibited by owner policy")
print("Owner-only Author/Committer history checked; no co-author trailers.")
