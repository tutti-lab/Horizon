"""Tests for shared AI response parsing utilities."""

from __future__ import annotations

from src.ai.utils import parse_json_response


def test_parse_json_response_prefers_final_object_after_reasoning_schema():
    response = """
<reasoning>
The requested format is {"items":[{"name":"","summary_zh":""}]}.
</reasoning>

{"items":[{"name":"Kong/insomnia","summary_zh":"开源跨平台 API 客户端"}]}
"""

    result = parse_json_response(response)

    assert result == {
        "items": [
            {
                "name": "Kong/insomnia",
                "summary_zh": "开源跨平台 API 客户端",
            }
        ]
    }
