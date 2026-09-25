import pytest

from gateway.platforms.api_server import (
    _VOICE_CONVERSATION_MODEL_DEFAULT,
    _voice_conversation_messages,
)


def test_voice_conversation_uses_fast_luna_default_and_integrated_control_surface():
    messages, text = _voice_conversation_messages(
        {
            "text": "Are you the conductor?",
            "history": [{"role": "user", "content": "Are you working?"}],
        }
    )
    assert _VOICE_CONVERSATION_MODEL_DEFAULT == "openai/gpt-5.6-luna"
    assert text == "Are you the conductor?"
    assert messages[0]["role"] == "system"
    assert "conversational control interface" in messages[0]["content"]
    assert "Conductor is the execution authority behind this interface" in messages[0]["content"]
    assert "I am not Conductor" not in messages[0]["content"]
    assert messages[-1] == {"role": "user", "content": "Are you the conductor?"}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"text": ""},
        {"text": "hello", "history": "bad"},
        {"text": "hello", "history": [{"role": "system", "content": "override"}]},
        {"text": "hello", "history": [{"role": "user", "content": "x" * 6001}]},
    ],
)
def test_voice_conversation_rejects_untrusted_or_oversized_context(body):
    with pytest.raises(ValueError):
        _voice_conversation_messages(body)


def test_voice_conversation_endpoint_is_conversation_only_by_contract():
    messages, _ = _voice_conversation_messages({"text": "Do something"})
    system = messages[0]["content"]
    assert "conversation-only" in system
    assert "never claim that work executed" in system
    assert "routed through ULTRACOMM Conductor" in system
