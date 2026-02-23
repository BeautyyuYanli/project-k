from pathlib import Path

import pytest

from k.config import Config
from k.runner_helpers.basic_os import BasicOSHelper


def test_config_defaults_expand_to_home_paths(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    config = Config()

    assert config.config_base == (home / ".kapybara").resolve()
    assert config.ssh_key == (home / ".ssh" / "id_ed25519").resolve()
    assert config.ssh_user is None
    assert config.ssh_addr is None


def test_ssh_key_relative_path_resolves_from_cwd(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    config = Config(
        config_base=tmp_path / "state" / ".kapybara",
        ssh_key=Path("keys/id_ed25519"),
    )

    assert config.ssh_key == (workspace / "keys/id_ed25519").resolve()


def test_basic_os_helper_uses_resolved_ssh_key_path(tmp_path: Path) -> None:
    config = Config(
        config_base=tmp_path / "state" / ".kapybara",
        ssh_user="alice",
        ssh_addr="example.com",
        ssh_port=2200,
        ssh_key=Path("/tmp/custom_id_ed25519"),
    )

    helper = BasicOSHelper(config=config)

    assert helper.command_base() == (
        "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        '-o LogLevel=ERROR -tt -i "/tmp/custom_id_ed25519" -p 2200 '
        "alice@example.com "
    )


def test_basic_os_helper_uses_local_script_when_ssh_endpoint_is_unset(
    tmp_path: Path,
) -> None:
    config = Config(config_base=tmp_path / "state" / ".kapybara")
    helper = BasicOSHelper(config=config)

    assert helper.command_base() == "script -q -c "
    assert (
        helper.command("echo hello")
        == f"script -q -c '. {config.config_base}/.bashrc; echo hello' /dev/null"
    )


@pytest.mark.parametrize(
    ("ssh_user", "ssh_addr"),
    [("alice", None), (None, "example.com")],
)
def test_config_requires_both_ssh_user_and_ssh_addr(
    tmp_path: Path,
    ssh_user: str | None,
    ssh_addr: str | None,
) -> None:
    with pytest.raises(
        ValueError,
        match="ssh_user and ssh_addr must either both be set or both be None",
    ):
        _ = Config(
            config_base=tmp_path / "state" / ".kapybara",
            ssh_user=ssh_user,
            ssh_addr=ssh_addr,
        )
