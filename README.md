# linkpartition

Verify that a local backup preserves the **hardlink relationships** of its source.
Detect both split links (extra storage and changed alias behavior) and unintended
merges (previously separate files now alias each other). It reads metadata only
and never copies, relinks, deletes, or reads file contents.

The [rsync manual](https://github.com/RsyncProject/rsync/blob/master/rsync.1.md)
documents that `-H` does not necessarily reproduce the exact destination link
pattern. Deduplicators such as
[util-linux hardlink](https://github.com/util-linux/util-linux/blob/master/misc-utils/hardlink.1.adoc)
create links. linkpartition instead asserts that the two observed path partitions
already agree, even when inode numbers differ across volumes.

## Install and run

Python 3.11+, no runtime dependencies:

```sh
git clone https://github.com/KanadeK/linkpartition.git
cd linkpartition
python -m venv .venv
```

Activate `.venv\Scripts\Activate.ps1` on PowerShell or `. .venv/bin/activate` on
Linux/macOS, then:

```sh
python -m pip install .
python scripts/smoke.py
```

The demo creates disposable trees using real hardlinks, checks a preserved
partition, deliberately breaks one link, and then introduces an unintended merge.
It verifies expected exits `0`, `1`, `1` and cleans up its temporary files.

Check your own **stable** source and backup directories:

```sh
linkpartition source-tree restored-tree --json > topology-report.json
```

Or install the release wheel directly:

```sh
python -m pip install https://github.com/KanadeK/linkpartition/releases/download/v0.1.0/linkpartition-0.1.0-py3-none-any.whl
```

Exit `0`: regular-file path sets and hardlink partitions agree. Exit `1`: paths
are missing/added or links split/merged. Exit `2`: observations are incomplete,
unsupported, unreadable, unstable, or exceed limits. Invalid observations never
become a partial passing result.

## Evidence and meaning

The report gives exact `lost_hardlink_pairs`, `gained_hardlink_pairs` and
`preserved_hardlink_pairs` among paths present in both trees. Missing and added
files are separate failures. It provides one representative path pair per split
or merged group. Detail lists are capped at 100, with explicit truncation;
aggregate counts are exact. Relative names are printed, so review reports before
sharing them. Absolute roots and file contents are not included.

Partition SHA-256 receipts hash canonical relative-path groups, not file contents
or inode numbers. Identical topology on different filesystems yields the same
receipt. `content_checked` is always `false`: run a content verifier separately.
A file whose bytes changed can still pass this topology-only check.

## Boundaries

- Requires reliable `(device, inode/file ID, link count)` observations. Windows
  uses fresh `lstat`, since directory-enumeration stat fields can be zero.
- Symlinks, junctions/reparse points, device files, pipes and sockets cause an
  input error. They are never silently omitted or intentionally followed.
- Maximum 100,000 total entries per tree and depth 64. Empty directories do not
  participate in the partition; each tree must contain at least one regular file.
- Relative names are matched exactly, without case/Unicode normalization. This
  is not a filename-portability, permissions, reflink, sparse-file or content audit.
- Only hardlinks whose names are inside the supplied tree participate. Aliases
  outside it are not searched. Permission errors fail closed.
- Every observed entry is restatted to catch common changes during each scan.
  This is not an atomic filesystem snapshot or a security sandbox against races.
  Stop writers or supply immutable snapshots; sequential scans cannot prove a
  changing source/target pair existed simultaneously.

## Development, validation and cleanup

```sh
python -m pip install -e ".[dev]"
python scripts/verify.py
```

The gate runs Ruff, branch-aware coverage (minimum 90%), unit/integration tests,
wheel/sdist builds and an independent clean-wheel CLI demo. CI runs Linux
3.11/3.13 plus Windows/macOS 3.13 and checks complete commit authorship history.
[VALIDATION.md](VALIDATION.md) records local results. The test oracle enumerates
all path pairs for 300 seeded small partition comparisons independently of the
production intersection-count algorithm.

Uninstall: `python -m pip uninstall linkpartition`. Deactivate and remove the
`.venv` you created to clean up the isolated installation. The checker stores no
cache or inventory on disk; keep or delete reports you redirect yourself.

## 中文说明

linkpartition 检查备份前后同名文件的硬链接关系是否保持一致，可发现硬链接被拆成
普通副本，或原本独立的文件意外合并。只读元数据，输出精确的链接对变化数量及代表
路径，不读取文件内容，也不修复文件。必须对静止目录或快照运行；符号链接、重解析点
和无法完整读取的目录会报错，避免遗漏后误判通过。演示：`python scripts/smoke.py`。

MIT. See [THIRD_PARTY.md](THIRD_PARTY.md), [CONTRIBUTING.md](CONTRIBUTING.md),
[SECURITY.md](SECURITY.md) and [AGENTS.md](AGENTS.md).
