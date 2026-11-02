"""The denylist is two files: a default list that ships with the repository and a
local list the bot writes. Pulling a newer default list must never conflict with
what moderators added, which is why the bot writes only to the local one.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from discord_crypto_spam_destroyer.hashes.store import FileHashStore

SHIPPED_1 = "a5a5a5a5a5a5a5a5"
SHIPPED_2 = "5a5a5a5a5a5a5a5a"
MINE = "c3c3c3c3c3c3c3c3"
WHITE = "8000000000000000"


def lines(path: Path) -> list[str]:
    return path.read_text().split()


@pytest.fixture
def store(tmp_path) -> FileHashStore:
    (tmp_path / "default.txt").write_text(f"{SHIPPED_1}\n")
    return FileHashStore(tmp_path / "local.txt", tmp_path / "default.txt")


def test_matching_uses_both_lists(store) -> None:
    store.add(MINE)
    assert store.load() == {SHIPPED_1, MINE}


def test_a_hash_added_through_discord_goes_only_to_the_local_list(store, tmp_path) -> None:
    default_before = (tmp_path / "default.txt").read_bytes()
    store.add(MINE)
    assert lines(tmp_path / "local.txt") == [MINE]
    assert (tmp_path / "default.txt").read_bytes() == default_before


def test_a_hash_the_default_list_already_has_is_not_copied_into_the_local_list(store, tmp_path) -> None:
    store.add(SHIPPED_1)
    assert not (tmp_path / "local.txt").exists()


def test_a_near_uniform_hash_is_still_refused(store, tmp_path) -> None:
    store.add(WHITE)
    assert not (tmp_path / "local.txt").exists()


def test_either_list_can_be_missing(tmp_path) -> None:
    assert FileHashStore(tmp_path / "local.txt", tmp_path / "default.txt").load() == set()
    only_local = FileHashStore(tmp_path / "local.txt")
    only_local.add(MINE)
    assert only_local.load() == {MINE}


def test_promote_moves_local_hashes_into_the_default_list(store, tmp_path) -> None:
    store.add(MINE)
    assert store.promote() == 1
    assert lines(tmp_path / "default.txt") == sorted([SHIPPED_1, MINE])
    assert lines(tmp_path / "local.txt") == []
    assert store.load() == {SHIPPED_1, MINE}


def test_promote_without_a_default_list_says_so(tmp_path) -> None:
    with pytest.raises(ValueError):
        FileHashStore(tmp_path / "local.txt").promote()


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_pulling_a_newer_default_list_does_not_conflict_with_local_hashes(tmp_path) -> None:
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}

    def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True)

    upstream = tmp_path / "upstream"
    (upstream / "data").mkdir(parents=True)
    git(upstream, "init", "-q")
    (upstream / ".gitignore").write_text("data/bad_hashes.txt\n")
    (upstream / "data" / "default_bad_hashes.txt").write_text(f"{SHIPPED_1}\n")
    git(upstream, "add", "-A")
    git(upstream, "commit", "-q", "-m", "first list")

    clone = tmp_path / "clone"
    git(tmp_path, "clone", "-q", str(upstream), str(clone))
    mine = FileHashStore(clone / "data" / "bad_hashes.txt", clone / "data" / "default_bad_hashes.txt")
    mine.add(MINE)

    (upstream / "data" / "default_bad_hashes.txt").write_text(f"{SHIPPED_1}\n{SHIPPED_2}\n")
    git(upstream, "commit", "-q", "-am", "newer list")
    git(clone, "pull", "-q")

    assert mine.load() == {SHIPPED_1, SHIPPED_2, MINE}
    assert git(clone, "status", "--porcelain").stdout == ""
