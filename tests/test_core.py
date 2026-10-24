import builtins
import itertools
import json
import os
import random
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from linkpartition import core
from linkpartition.cli import main
from linkpartition.core import InputError, Inventory, audit, compare, scan


def inventory(labels):
    groups = {}
    for n, label in enumerate(labels):
        groups.setdefault(label, []).append(str(n))
    result = {min(names): tuple(sorted(names)) for names in groups.values()}
    return Inventory(result, {name: key for key, names in result.items() for name in names}, "test")


def test_partition_formula_against_brute_force():
    rng = random.Random(741)
    for n in range(1, 16):
        for _ in range(20):
            left, right = ([rng.randrange(5) for _ in range(n)] for _ in range(2))
            report = compare(inventory(left), inventory(right))
            lost = gained = kept = 0
            for a, b in itertools.combinations(range(n), 2):
                before, after = left[a] == left[b], right[a] == right[b]
                lost += before and not after
                gained += after and not before
                kept += before and after
            assert (
                report["lost_hardlink_pairs"],
                report["gained_hardlink_pairs"],
                report["preserved_hardlink_pairs"],
            ) == (lost, gained, kept)


def make_tree(path):
    path.mkdir()
    (path / "a").write_bytes(b"original")
    os.link(path / "a", path / "b")


def test_real_files_no_content_reads(tmp_path, monkeypatch):
    left, right = tmp_path / "left", tmp_path / "right"
    make_tree(left)
    make_tree(right)

    def forbidden(*args, **kwargs):
        raise AssertionError("Contents must never be read")

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        report = audit(left, right)
    assert report["status"] == "passed" and report["preserved_hardlink_pairs"] == 1
    assert report["source_partition_sha256"] == report["target_partition_sha256"]
    (right / "b").unlink()
    (right / "b").write_bytes(b"original")
    assert audit(left, right)["lost_hardlink_pairs"] == 1
    assert (left / "a").read_bytes() == b"original"


def test_inventory_changes_and_bounded_witnesses(tmp_path, monkeypatch):
    left, right = tmp_path / "left", tmp_path / "right"
    make_tree(left)
    make_tree(right)
    (right / "a").unlink()
    (right / "extra").write_bytes(b"x")
    report = audit(left, right)
    assert report["missing"] == ["a"] and report["added"] == ["extra"]
    assert report["status"] == "failed"
    monkeypatch.setattr(core, "DETAIL_LIMIT", 1)
    assert compare(inventory([0, 0, 1, 1]), inventory([0, 1, 0, 1]))["details_truncated"]


def test_empty_bad_root_limits(tmp_path, monkeypatch):
    with pytest.raises(InputError, match="no_regular"):
        scan(tmp_path)
    file = tmp_path / "file"
    file.touch()
    with pytest.raises(InputError, match="plain_directory"):
        scan(file)
    monkeypatch.setattr(core, "MAX_ENTRIES", 0)
    with pytest.raises(InputError, match="limit"):
        scan(tmp_path)
    monkeypatch.setattr(core, "MAX_ENTRIES", 100)
    monkeypatch.setattr(core, "MAX_DEPTH", 0)
    with pytest.raises(InputError, match="limit"):
        scan(tmp_path)


def test_symlink_detection(tmp_path, monkeypatch):
    # Actual symlinks are tested on Unix; the Windows reparse bit is tested on all OSes.
    assert core._unsupported(SimpleNamespace(st_mode=stat.S_IFREG, st_file_attributes=0x400))
    if os.name != "nt":
        target = tmp_path / "outside"
        target.touch()
        root = tmp_path / "root"
        root.mkdir()
        (root / "link").symlink_to(target)
        with pytest.raises(InputError, match="symlink"):
            scan(root)
        with pytest.raises(InputError, match="plain_directory"):
            scan(root / "link")
        (root / "link").unlink()
        os.mkfifo(root / "pipe")
        with pytest.raises(InputError, match="non_regular"):
            scan(root)


def test_changed_tree_and_unavailable_identity(tmp_path, monkeypatch):
    make_tree(tmp_path / "tree")
    real = Path.lstat
    calls = 0

    def changed(path, *args, **kwargs):
        nonlocal calls
        info = real(path, *args, **kwargs)
        calls += 1
        if calls > 1:
            return SimpleNamespace(
                **{
                    key: getattr(info, key)
                    for key in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_ctime_ns")
                },
                st_mtime_ns=info.st_mtime_ns + 1,
            )
        return info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", changed)
        with pytest.raises(InputError, match="changed"):
            scan(tmp_path / "tree")

    def unavailable(path, *args, **kwargs):
        info = real(path, *args, **kwargs)
        if stat.S_ISREG(info.st_mode):
            attrs = {
                key: getattr(info, key)
                for key in (
                    "st_dev",
                    "st_mode",
                    "st_nlink",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            }
            return SimpleNamespace(**attrs, st_ino=0)
        return info

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", unavailable)
        with pytest.raises(InputError, match="identity_unavailable"):
            scan(tmp_path / "tree")


def test_cli_and_redacted_io_errors(tmp_path, capsys, monkeypatch):
    left, right = tmp_path / "left", tmp_path / "right"
    make_tree(left)
    make_tree(right)
    assert main([str(left), str(right), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "passed"
    (right / "b").unlink()
    (right / "b").touch()
    assert main([str(left), str(right)]) == 1
    assert "split:" in capsys.readouterr().out
    assert main([str(left), str(tmp_path / "missing")]) == 2
    assert str(tmp_path) not in capsys.readouterr().err
    import linkpartition.cli as cli

    monkeypatch.setattr(cli, "audit", lambda *args: (_ for _ in ()).throw(InputError("incomplete")))
    assert main([str(left), str(right)]) == 2
    assert "incomplete" in capsys.readouterr().err


def test_nested_paths_and_fail_closed_empty_target(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    for root in (left, right):
        root.mkdir()
        (root / "nested").mkdir()
        (root / "nested" / "unicode-\u732b").write_bytes(b"one")
        os.link(root / "nested" / "unicode-\u732b", root / "alias")
    assert audit(left, right)["status"] == "passed"
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(InputError, match="target: tree_has_no_regular_files"):
        audit(left, empty)
