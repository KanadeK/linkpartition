# v0.1.0 release evidence

Local environment: Windows, CPython 3.13.16, 2026-10-24.

Core acceptance includes real NTFS hardlinks, preserved/split/merged partitions,
path additions/removals, nested Unicode paths, read-only content tripwires,
unsupported identities, changed-tree rejection and capped evidence. An independent
brute-force oracle checks 300 seeded partition pairs. Platform-specific Unix
symlink/FIFO cases run on Unix CI; the Windows reparse attribute is tested locally.

Review found and fixed zero identity fields in Windows DirEntry.stat by using
fresh lstat. Directory enumeration is bounded before sorting, not after an
unbounded listing. Input errors cannot yield partial success. Output escapes
relative paths for terminal safety and makes no content-integrity claim.

Ruff, >=90% branch-aware coverage, distribution builds and an isolated installed
CLI workflow are mandatory in scripts/verify.py. Consult that command's output
and the release commit's CI for measured counts and platform results.
