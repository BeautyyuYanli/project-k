from pathlib import Path

from k.agent.memory.paths import memory_root_from_fs_base


def test_memory_root_from_fs_base_uses_kapybara_subdir(tmp_path: Path) -> None:
    assert memory_root_from_fs_base(tmp_path) == (
        tmp_path.resolve() / ".kapybara" / "memories"
    )


def test_memory_root_from_fs_base_expands_home(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    assert memory_root_from_fs_base("~/workspace") == (
        (home / "workspace").resolve() / ".kapybara" / "memories"
    )
