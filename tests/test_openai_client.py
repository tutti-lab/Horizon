"""Tests for OpenAI AI client."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.ai.client import OpenAIClient
from src.models import AIConfig, AIProvider


def _make_config(**overrides) -> AIConfig:
    defaults = {
        "provider": AIProvider.OPENAI,
        "model": "gpt-5.5",
        "base_url": "https://allincode.top",
        "api_key_env": "OPENAI_API_KEY",
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    defaults.update(overrides)
    return AIConfig(**defaults)


def test_responses_wire_uses_responses_api(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = OpenAIClient(
        _make_config(
            wire_api="responses",
            reasoning_effort="xhigh",
            disable_response_storage=True,
        )
    )

    mock_response = SimpleNamespace(
        output_text='{"ok": true}',
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )

    with patch.object(client.client.responses, "create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_response
        result = asyncio.run(client.complete(system="system prompt", user="user prompt"))

    assert result == '{"ok": true}'
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-5.5"
    assert call_kwargs["instructions"] == "system prompt"
    assert call_kwargs["input"] == "user prompt"
    assert call_kwargs["max_output_tokens"] == 4096
    assert call_kwargs["reasoning"] == {"effort": "xhigh"}
    assert call_kwargs["store"] is False
    assert call_kwargs["text"] == {"format": {"type": "json_object"}}
