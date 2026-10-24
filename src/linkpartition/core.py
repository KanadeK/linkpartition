"""Read-only comparison of hardlink equivalence classes on stable local trees."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from . import __version__

MAX_ENTRIES = 100_000
MAX_DEPTH = 64
DETAIL_LIMIT = 100


class InputError(ValueError):
    """Incomplete or unsupported observations cannot produce a passing result."""


def _signature(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _unsupported(info):
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


@dataclass(frozen=True)
class Inventory:
    groups: dict[str, tuple[str, ...]]
    membership: dict[str, str]
    digest: str


def scan(root: Path) -> Inventory:
    root = root.absolute()
    info = root.lstat()
    if _unsupported(info) or not stat.S_ISDIR(info.st_mode):
        raise InputError("root_must_be_a_plain_directory")
    observed = {root: _signature(info)}
    records = defaultdict(list)
    pending = [(root, 0)]
    entries_seen = 0
    while pending:
        directory, depth = pending.pop()
        with os.scandir(directory) as iterator:
            entries = []
            for entry in iterator:
                if entries_seen + len(entries) >= MAX_ENTRIES:
                    raise InputError("tree_entry_or_depth_limit")
                entries.append(entry)
            entries.sort(key=lambda entry: entry.name)
        for entry in entries:
            entries_seen += 1
            if entries_seen > MAX_ENTRIES or depth >= MAX_DEPTH:
                raise InputError("tree_entry_or_depth_limit")
            path = Path(entry.path)
            # Windows DirEntry.stat may return zero for inode/device/link count.
            # lstat performs a fresh non-following observation with file identity.
            info = path.lstat()
            if _unsupported(info):
                raise InputError("symlink_or_reparse_entry_not_supported")
            if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise InputError("non_regular_entry_not_supported")
            observed[path] = _signature(info)
            if stat.S_ISDIR(info.st_mode):
                pending.append((path, depth + 1))
            else:
                if info.st_ino <= 0 or info.st_nlink < 1:
                    raise InputError("filesystem_file_identity_unavailable")
                records[(info.st_dev, info.st_ino)].append(
                    (path.relative_to(root).as_posix(), info)
                )
    for path, expected in observed.items():
        if _signature(path.lstat()) != expected:
            raise InputError("tree_changed_during_scan")
    if not records:
        raise InputError("tree_has_no_regular_files")
    groups, membership = {}, {}
    for members in records.values():
        names = tuple(sorted(name for name, _ in members))
        reference = _signature(members[0][1])
        if any(_signature(info) != reference for _, info in members) or reference[3] < len(names):
            raise InputError("inconsistent_filesystem_file_identity")
        groups[names[0]] = names
        membership.update((name, names[0]) for name in names)
    ordered = [groups[key] for key in sorted(groups)]
    digest = hashlib.sha256(json.dumps(ordered, ensure_ascii=True).encode("ascii")).hexdigest()
    return Inventory(groups, membership, digest)


def _pairs(count):
    return count * (count - 1) // 2


def compare(source: Inventory, target: Inventory) -> dict:
    common = sorted(source.membership.keys() & target.membership.keys())
    missing = sorted(source.membership.keys() - target.membership.keys())
    added = sorted(target.membership.keys() - source.membership.keys())
    cells = Counter((source.membership[name], target.membership[name]) for name in common)
    left = Counter(source.membership[name] for name in common)
    right = Counter(target.membership[name] for name in common)
    preserved = sum(_pairs(n) for n in cells.values())
    lost = sum(_pairs(n) for n in left.values()) - preserved
    gained = sum(_pairs(n) for n in right.values()) - preserved
    witnesses, witness_count = [], 0
    common_set = set(common)
    for kind, inventory, other in (("split", source, target), ("merge", target, source)):
        for key in sorted(inventory.groups):
            names = [name for name in inventory.groups[key] if name in common_set]
            if not names:
                continue
            first = names[0]
            changed = next(
                (name for name in names[1:] if other.membership[name] != other.membership[first]),
                None,
            )
            if changed is not None:
                witness_count += 1
                if len(witnesses) < DETAIL_LIMIT:
                    witnesses.append({"kind": kind, "paths": [first, changed]})
    return {
        "schema_version": 1,
        "tool_version": __version__,
        "status": "failed" if missing or added or lost or gained else "passed",
        "content_checked": False,
        "source_files": len(source.membership),
        "target_files": len(target.membership),
        "common_files": len(common),
        "missing_count": len(missing),
        "added_count": len(added),
        "lost_hardlink_pairs": lost,
        "gained_hardlink_pairs": gained,
        "preserved_hardlink_pairs": preserved,
        "source_partition_sha256": source.digest,
        "target_partition_sha256": target.digest,
        "missing": missing[:DETAIL_LIMIT],
        "added": added[:DETAIL_LIMIT],
        "witness_count": witness_count,
        "witnesses": witnesses,
        "details_truncated": max(len(missing), len(added), witness_count) > DETAIL_LIMIT,
    }


def audit(source: Path, target: Path) -> dict:
    inventories = []
    for label, path in (("source", source), ("target", target)):
        try:
            inventories.append(scan(path))
        except InputError as exc:
            raise InputError(label + ": " + str(exc)) from None
    return compare(*inventories)
