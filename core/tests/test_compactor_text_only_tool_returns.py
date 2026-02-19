from __future__ import annotations

from pydantic_ai.messages import (
    BinaryContent,
    FileUrl,
    ImageUrl,
    ModelRequest,
    ToolReturnPart,
    UserPromptPart,
)

from k.agent.memory.compactor import print_detailed


class _DummyFileUrl(FileUrl):
    def format(self) -> object:
        return {"url": self.url}

    def _infer_media_type(self) -> str | None:
        return None


def test_print_detailed_strips_multimodal_from_tool_returns() -> None:
    detailed = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="read_media",
                    content=[
                        ImageUrl(url="https://example.com/image.png"),
                        "ok",
                    ],
                    tool_call_id="call_1",
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "ok" in rendered
    assert "https://example.com/image.png" in rendered


def test_print_detailed_replaces_all_binary_tool_returns_with_placeholder() -> None:
    detailed = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="read_media",
                    content=[
                        BinaryContent(
                            data=b"abc",
                            media_type="application/octet-stream",
                        )
                    ],
                    tool_call_id="call_2",
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "read_media" in rendered
    assert "non-text tool output omitted" in rendered


def test_print_detailed_strips_base64_strings_from_tool_returns() -> None:
    base64_payload = "a" * 200
    detailed = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="some_tool",
                    content=[base64_payload, "ok"],
                    tool_call_id="call_2b",
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "ok" in rendered
    assert base64_payload not in rendered


def test_print_detailed_strips_kind_discriminated_multimodal_dicts_from_tool_returns() -> (
    None
):
    detailed = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="some_tool",
                    content=[
                        {"kind": "image-url", "url": "https://x/y.png"},
                        "ok",
                    ],
                    tool_call_id="call_3b",
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "ok" in rendered
    assert "https://x/y.png" in rendered


def test_print_detailed_strips_file_url_instances_from_tool_returns() -> None:
    detailed = [
        ModelRequest(
            parts=[
                ToolReturnPart(
                    tool_name="some_tool",
                    content=[
                        _DummyFileUrl(url="https://example.com/file.bin"),
                        "ok",
                    ],
                    tool_call_id="call_3c",
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "ok" in rendered
    assert "https://example.com/file.bin" in rendered


def test_print_detailed_strips_multimodal_from_user_prompt_parts() -> None:
    detailed = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[
                        ImageUrl(url="https://example.com/user-image.png"),
                        "please summarize",
                    ]
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "please summarize" in rendered
    assert "https://example.com/user-image.png" in rendered


def test_print_detailed_replaces_all_multimodal_user_prompt_parts_with_placeholder() -> (
    None
):
    detailed = [
        ModelRequest(
            parts=[
                UserPromptPart(
                    content=[ImageUrl(url="https://example.com/only-user-image.png")]
                )
            ]
        )
    ]

    rendered = print_detailed(detailed)
    assert "non-text user content omitted" not in rendered
    assert "https://example.com/only-user-image.png" in rendered
