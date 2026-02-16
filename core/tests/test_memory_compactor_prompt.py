from pathlib import Path


def _compactor_py() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "core" / "src" / "k" / "agent" / "memory" / "compactor.py"


def test_compactor_prompt_emphasizes_high_fidelity_details() -> None:
    text = _compactor_py().read_text(encoding="utf-8")

    # Guardrails for memory quality: preserve what the agent received, tried,
    # observed, and responded (including failures when they matter).
    assert "High-fidelity rule (most important)" in text
    assert "received (inputs/constraints/context)" in text
    assert "tried (actions, commands, edits, tool calls)" in text
    assert "observed (tool outputs, errors, test results, confirmations)" in text
    assert "responded (messages delivered to the user and artifacts produced)" in text
    assert "Include failed attempts" in text
    assert "Received → Tried → Observed → Responded" in text
