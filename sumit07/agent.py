"""The Sumit07 agent: a scoped tool-calling loop over the data-analyst toolset."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

from . import AGENT_NAME, config
from .prompts import REFUSAL_MESSAGE, SCOPE_CLASSIFIER_PROMPT, SYSTEM_PROMPT
from .tools import DataAnalystTools


class Sumit07Agent:
    """Runs the reasoning loop and yields events for a streaming UI."""

    def __init__(
        self,
        tools: DataAnalystTools,
        client: Any = None,
        model: Optional[str] = None,
        max_steps: Optional[int] = None,
        scope_guard: Optional[bool] = None,
    ) -> None:
        self.tools = tools
        self.client = client or config.get_client()
        self.model = model or config.DEFAULT_MODEL
        self.max_steps = max_steps or config.MAX_AGENT_STEPS
        self.scope_guard = config.SCOPE_GUARD if scope_guard is None else scope_guard

    # -- scope enforcement ---------------------------------------------------
    def _in_scope(self, text: str, history: List[Dict[str, str]]) -> bool:
        """Ask the model to classify the request as data-analysis or not."""
        if not self.scope_guard:
            return True
        recent = history[-4:]
        convo = "\n".join(f"{m.get('role')}: {str(m.get('content'))[:400]}" for m in recent)
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SCOPE_CLASSIFIER_PROMPT},
                    {
                        "role": "user",
                        "content": f"Conversation so far:\n{convo}\n\nLatest user request:\n{text}",
                    },
                ],
                temperature=0,
                max_tokens=4,
            )
            verdict = (resp.choices[0].message.content or "").strip().upper()
            return not verdict.startswith("OFF")
        except Exception:  # noqa: BLE001 - never block the user on a guard failure
            return True

    # -- main loop -----------------------------------------------------------
    def run(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """Yield events: tool_call, tool_result, final, error."""
        history = history or []

        if not self._in_scope(user_message, history):
            yield {"type": "final", "content": REFUSAL_MESSAGE}
            return

        messages: List[Dict[str, Any]] = (
            [{"role": "system", "content": SYSTEM_PROMPT}] + history + [{"role": "user", "content": user_message}]
        )

        for _ in range(self.max_steps):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=self.tools.schemas(),
                    tool_choice="auto",
                    temperature=0.2,
                )
            except Exception as exc:  # noqa: BLE001
                yield {"type": "error", "content": f"{type(exc).__name__}: {exc}"}
                return

            message = resp.choices[0].message

            if not message.tool_calls:
                yield {"type": "final", "content": (message.content or "").strip()}
                return

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )

            for tc in message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                yield {"type": "tool_call", "name": name, "args": args}
                result = self.tools.dispatch(name, args)
                yield {"type": "tool_result", "name": name, "content": result}
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        yield {
            "type": "final",
            "content": (
                f"{AGENT_NAME} reached its step limit before finishing. "
                "Try breaking the request into smaller steps (e.g. clean first, then analyse)."
            ),
        }
