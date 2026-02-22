from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path
from typing import ClassVar

import pytest


def _load_generate_nai_chat_module(monkeypatch: pytest.MonkeyPatch):
    """Load the script module with minimal stubs for optional runtime deps."""
    # `generate_nai_chat` depends on `novelai_python`, which is intentionally not
    # part of the core test environment.
    novelai_python = types.ModuleType("novelai_python")

    class _GenerateImageInfer:
        @staticmethod
        def build_generate(**_: object) -> object:
            raise RuntimeError("not used in prompt override tests")

    class _ApiCredential:
        def __init__(self, **_: object) -> None:
            pass

    novelai_python.GenerateImageInfer = _GenerateImageInfer
    novelai_python.ApiCredential = _ApiCredential

    sdk_mod = types.ModuleType("novelai_python.sdk")
    ai_mod = types.ModuleType("novelai_python.sdk.ai")
    generate_image_mod = types.ModuleType("novelai_python.sdk.ai.generate_image")

    class _Model:
        NAI_DIFFUSION_4_5_FULL = object()

    class _Sampler:
        K_DPMPP_2M_SDE = object()

    class _UCPreset:
        TYPE0 = object()

    generate_image_mod.Model = _Model
    generate_image_mod.Sampler = _Sampler
    generate_image_mod.UCPreset = _UCPreset

    params_mod = types.ModuleType("novelai_python.sdk.ai.generate_image.params")

    class _Params:
        model_fields: ClassVar[dict[str, object]] = {}

    params_mod.Params = _Params

    pil_mod = types.ModuleType("PIL")
    pil_mod.Image = object()

    monkeypatch.setitem(sys.modules, "novelai_python", novelai_python)
    monkeypatch.setitem(sys.modules, "novelai_python.sdk", sdk_mod)
    monkeypatch.setitem(sys.modules, "novelai_python.sdk.ai", ai_mod)
    monkeypatch.setitem(
        sys.modules, "novelai_python.sdk.ai.generate_image", generate_image_mod
    )
    monkeypatch.setitem(
        sys.modules, "novelai_python.sdk.ai.generate_image.params", params_mod
    )
    monkeypatch.setitem(sys.modules, "PIL", pil_mod)

    repo_root = Path(__file__).resolve().parents[2]
    script_path = (
        repo_root
        / "data"
        / "fs"
        / ".kapybara"
        / "skills"
        / "media"
        / "novelai-image"
        / "generate_nai_chat"
    )

    module_name = "test_generate_nai_chat_script"
    sys.modules.pop(module_name, None)
    loader = importlib.machinery.SourceFileLoader(module_name, str(script_path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_resolve_prompt_overrides_inherits_only_when_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_generate_nai_chat_module(monkeypatch)

    result = module._resolve_prompt_overrides(
        wearing_override=None,
        state_override=None,
        negative_override=None,
        current_wearing="wearing-prev",
        current_state="state-prev",
        current_negative="negative-prev",
    )

    assert result == ("wearing-prev", "state-prev", "negative-prev")


def test_resolve_prompt_overrides_treats_blank_as_explicit_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_generate_nai_chat_module(monkeypatch)

    result = module._resolve_prompt_overrides(
        wearing_override="new wearing",
        state_override="",
        negative_override="   ",
        current_wearing="wearing-prev",
        current_state="state-prev",
        current_negative="negative-prev",
    )

    assert result == ("new wearing", "", "")


def test_resolve_current_lineage_state_uses_wearing_default_without_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_generate_nai_chat_module(monkeypatch)
    wearing_path = tmp_path / "WEARING.txt"
    wearing_path.write_text("wearing-from-file", encoding="utf-8")

    result = module._resolve_current_lineage_state(
        latest_path=None,
        wearing_path=wearing_path,
    )

    assert result == ("wearing-from-file", "", "")


def test_resolve_current_lineage_state_fails_when_latest_sidecar_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_generate_nai_chat_module(monkeypatch)
    latest_path = tmp_path / "nai_lineage_test_v3.jpg"
    latest_path.write_bytes(b"fake image")

    with pytest.raises(FileNotFoundError):
        module._resolve_current_lineage_state(
            latest_path=latest_path,
            wearing_path=tmp_path / "WEARING.txt",
        )


def test_resolve_current_lineage_state_reads_latest_sidecar_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = _load_generate_nai_chat_module(monkeypatch)
    latest_path = tmp_path / "nai_lineage_test_v4.jpg"
    latest_path.write_bytes(b"fake image")
    latest_path.with_suffix(".txt").write_text(
        "WEARING: latest-wearing\nSTATE: latest-state\nNEGATIVE: latest-neg\n",
        encoding="utf-8",
    )

    result = module._resolve_current_lineage_state(
        latest_path=latest_path,
        wearing_path=tmp_path / "WEARING.txt",
    )

    assert result == ("latest-wearing", "latest-state", "latest-neg")
