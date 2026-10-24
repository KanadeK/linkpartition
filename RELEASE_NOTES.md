# v0.1.0

Initial read-only hardlink partition comparison for local backup verification.
Reports exact changed pair counts, representative split/merge witnesses, missing
and added paths, canonical partition receipts and explicit unsupported input.
No runtime dependencies; Python 3.11+; wheel and sdist with SHA-256 checksums.

Validation includes actual hardlink fixtures, 300 independent seeded partition
oracle comparisons, clean-wheel core flow, lint and branch-aware coverage.
See the release commit's CI for Linux, Windows and macOS results.

Limits: metadata/topology only; stable trees required; no content, symlink,
reflink, permissions or atomic-snapshot proof. At most 100,000 entries per tree.
