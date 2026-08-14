from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class OpenAIService:
    """Minimal Responses API adapter with no SDK coupling.

    Process data is sent only when the user explicitly configures an API key.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._load_local_env()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    @staticmethod
    def _load_local_env(path: Path = Path(".env")) -> None:
        """Load the two supported local settings without an additional dependency."""
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() in {"OPENAI_API_KEY", "OPENAI_MODEL"}:
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def structured_turn(
        self, messages: list[dict[str, str]], process: dict[str, Any]
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        instructions = """You are the conversational intake agent for Danone SOP Builder.
Return JSON only with keys assistant_message, updates, and ready_to_generate.
updates maps ProcessDefinition field names to values explicitly supported by the user messages.
process_steps must be an array of objects shaped exactly as {"role": "Role name or TBD", "action": "Action text"}; never return step strings.
Never invent Responsible, Accountable, approvals, validation, records, escalation, or process flow.
Ask at most two short targeted questions, prioritizing the most important missing governance facts.
After governance, collect in-scope, out-of-scope, and document_control_information.written_by before saying the SOP is ready for internal review.
Do not ask for information already present. Purpose must begin 'The purpose of this SOP is to'."""
        payload = {
            "model": self.model,
            "instructions": instructions,
            "input": json.dumps({"conversation": messages, "current_process": process}),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "sop_intake_turn",
                    "strict": False,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "assistant_message": {"type": "string"},
                            "updates": {"type": "object", "additionalProperties": True},
                            "ready_to_generate": {"type": "boolean"},
                        },
                        "required": [
                            "assistant_message",
                            "updates",
                            "ready_to_generate",
                        ],
                    },
                }
            },
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"OpenAI request failed ({exc.code}): {detail[:300]}"
            ) from exc
        output_text = data.get("output_text")
        if not output_text:
            output_text = "".join(
                item.get("text", "")
                for output in data.get("output", [])
                for item in output.get("content", [])
                if item.get("type") == "output_text"
            )
        result = json.loads(output_text)
        if not isinstance(result.get("updates", {}), dict) or not result.get(
            "assistant_message"
        ):
            raise RuntimeError("OpenAI returned an invalid intake response")
        return result
