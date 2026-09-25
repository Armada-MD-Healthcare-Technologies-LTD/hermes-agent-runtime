"""Armada Railway compatibility patch for low-latency, conversation-only voice."""
import json
import logging
import os
import re
from typing import Any

from aiohttp import ClientSession, ClientTimeout, web
import gateway.platforms.api_server as api

_LOG = logging.getLogger("armada.voice_patch")
_MODEL_DEFAULT = "openai/gpt-5.6-luna"
_MAX_HISTORY = 10
_MAX_TEXT = 6000
_PROMPT = (
    "You are Hermes, the conversational control interface for Armada MD's ULTRACOMM. "
    "Speak as one integrated operator surface. Conductor is the execution authority behind "
    "this interface; do not volunteer internal component separation or say that you are "
    "disconnected from Conductor. This endpoint is conversation-only: never claim work "
    "executed, never claim a mission was accepted, and never invent runtime capabilities. "
    "If the user asks for execution, say the objective routes through ULTRACOMM Conductor "
    "by this operator interface. Be concise and conversational."
)

def _messages(body: Any) -> list[dict[str, str]]:
    if not isinstance(body, dict):
        raise ValueError("invalid body")
    text = body.get("text")
    history = body.get("history", [])
    if not isinstance(text, str) or not text.strip() or len(text) > _MAX_TEXT:
        raise ValueError("invalid text")
    if not isinstance(history, list) or len(history) > _MAX_HISTORY:
        raise ValueError("invalid history")
    messages = [{"role": "system", "content": _PROMPT}]
    for item in history:
        if not isinstance(item, dict):
            raise ValueError("invalid history")
        role, content = item.get("role"), item.get("content")
        if (
            role not in {"user", "assistant"}
            or not isinstance(content, str)
            or len(content) > _MAX_TEXT
        ):
            raise ValueError("invalid history")
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": text.strip()})
    return messages

@api._require_auth
async def _handle_voice_converse(self, request):
    try:
        messages = _messages(await request.json())
    except Exception:
        return web.json_response(
            {"ok": False, "error": "invalid_voice_conversation"}, status=400
        )
    key = str(os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if not key:
        return web.json_response(
            {"ok": False, "error": "voice_provider_unavailable"}, status=503
        )
    model = str(os.environ.get("HERMES_VOICE_CHAT_MODEL") or _MODEL_DEFAULT).strip()
    if not re.match(r"^[A-Za-z0-9_.:/-]{1,160}$", model):
        model = _MODEL_DEFAULT
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": 500,
    }
    try:
        async with ClientSession(timeout=ClientTimeout(total=15)) as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json=payload,
            ) as upstream:
                raw = await upstream.content.read(65_537)
                if upstream.status != 200 or len(raw) > 65_536:
                    _LOG.warning("voice provider refused status=%s", upstream.status)
                    return web.json_response(
                        {"ok": False, "error": "voice_provider_unavailable"}, status=503
                    )
    except Exception:
        _LOG.warning("voice provider request failed", exc_info=True)
        return web.json_response(
            {"ok": False, "error": "voice_provider_unavailable"}, status=503
        )
    try:
        data = json.loads(raw.decode("utf-8"))
        reply = data["choices"][0]["message"]["content"].strip()
    except Exception:
        return web.json_response(
            {"ok": False, "error": "voice_provider_invalid"}, status=502
        )
    if not reply or len(reply) > _MAX_TEXT:
        return web.json_response(
            {"ok": False, "error": "voice_provider_invalid"}, status=502
        )
    return web.json_response(
        {
            "ok": True,
            "reply": reply,
            "executionEnabled": False,
            "provider": "openrouter",
            "model": model,
        }
    )

_original_routes = api.APIServerAdapter._http_route_table


def _patched_routes(self):
    routes = _original_routes(self)
    if any(path == "/api/voice/converse" for _, path, _ in routes):
        return routes
    row = ("POST", "/api/voice/converse", self._handle_voice_converse)
    index = next(
        (i for i, (_, path, _) in enumerate(routes) if path == "/v1/chat/completions"),
        len(routes),
    )
    return [*routes[:index], row, *routes[index:]]


api.APIServerAdapter._handle_voice_converse = _handle_voice_converse
api.APIServerAdapter._http_route_table = _patched_routes
