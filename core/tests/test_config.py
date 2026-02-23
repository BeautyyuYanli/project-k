from pathlib import Path

from k.config import Config
from k.runner_helpers.basic_os import BasicOSHelper


def test_config_defaults_expand_to_home_paths(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    config = Config()

    assert config.config_base == (home / ".kapybara").resolve()
    assert config.basic_os_sshkey == (home / ".ssh" / "id_ed25519").resolve()


def test_basic_os_sshkey_relative_path_resolves_from_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)

    config = Config(
        config_base=tmp_path / "state" / ".kapybara",
        basic_os_sshkey=Path("keys/id_ed25519"),
    )

    assert config.basic_os_sshkey == (workspace / "keys/id_ed25519").resolve()


def test_basic_os_helper_uses_resolved_sshkey_path(tmp_path: Path) -> None:
    config = Config(
        config_base=tmp_path / "state" / ".kapybara",
        basic_os_user="alice",
        basic_os_addr="example.com",
        basic_os_port=2200,
        basic_os_sshkey=Path("/tmp/custom_id_ed25519"),
    )

    helper = BasicOSHelper(config=config)

    assert helper.command_base() == (
        "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
        '-o LogLevel=ERROR -tt -i "/tmp/custom_id_ed25519" -p 2200 '
        "alice@example.com "
    )
