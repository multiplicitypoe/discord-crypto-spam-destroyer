"""The OpenAI request carries the right parameters for each model family, and
the prompt describes the scams this server actually receives.

Most of the scam images are screenshots of casino and betting sites, withdrawal
confirmations, and exchange or chat screenshots. Seen alone, a casino bonus page
or a "withdrawal successful" screen looks harmless, so the prompt has to name
them or the model passes them.
"""
from types import SimpleNamespace

import pytest

from discord_crypto_spam_destroyer.vision import openai_client
from discord_crypto_spam_destroyer.vision.openai_client import (
    SYSTEM_PROMPT,
    build_vision_request,
    classify_images,
    completion_options,
)


@pytest.fixture(autouse=True)
def no_effort_override(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_REASONING_EFFORT", raising=False)


def test_gpt4_models_take_a_temperature_of_zero() -> None:
    assert completion_options("gpt-4.1-mini") == {"temperature": 0}


def test_gpt5_and_gpt6_models_run_with_reasoning_off() -> None:
    assert completion_options("gpt-6-luna") == {"reasoning_effort": "none"}
    assert completion_options("gpt-5.6-luna") == {"reasoning_effort": "none"}


def test_reasoning_effort_can_be_changed(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_REASONING_EFFORT", "low")
    assert completion_options("gpt-6-luna") == {"reasoning_effort": "low"}
    assert completion_options("gpt-4.1-mini") == {"temperature": 0}


def test_the_prompt_names_the_scams_seen_in_the_server() -> None:
    for phrase in ("casino", "withdrawal", "rakeback", "profit and loss", "tweet", "Telegram", "Path of Exile"):
        assert phrase in SYSTEM_PROMPT


def test_the_request_has_the_prompt_one_image_and_its_detail() -> None:
    messages = build_vision_request(["data:image/jpeg;base64,AAAA"], "low")
    assert messages[0] == {"role": "system", "content": SYSTEM_PROMPT}
    image = messages[1]["content"][1]
    assert image == {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,AAAA", "detail": "low"}}


def test_classify_images_sends_the_model_options_and_reads_the_verdict(monkeypatch) -> None:
    sent = {}

    class FakeCompletions:
        def create(self, **kwargs):
            sent.update(kwargs)
            content = '{"is_crypto_scam": true, "confidence": 0.93, "reasons": ["casino bonus page"], "indicators": {}}'
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
                usage=None,
                id="req",
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    monkeypatch.setattr(openai_client, "OpenAI", lambda api_key: fake_client)

    result = classify_images("key", "gpt-6-luna", ["data:image/jpeg;base64,AAAA"], "low")

    assert sent["model"] == "gpt-6-luna"
    assert sent["reasoning_effort"] == "none"
    assert "temperature" not in sent
    assert sent["response_format"] == {"type": "json_object"}
    assert result.is_crypto_scam is True and result.confidence == 0.93
