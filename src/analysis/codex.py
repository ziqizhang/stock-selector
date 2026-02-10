import asyncio
import json
import logging
import os
import shlex
import shutil

from src.analysis.llm_base import LLMProvider

logger = logging.getLogger(__name__)


def _resolve_codex_bin() -> str:
    """Resolve the codex CLI binary path."""
    return os.environ.get("CODEX_BIN") or shutil.which("codex") or "codex"


class CodexCLI(LLMProvider):
    """Wrapper around the Codex CLI for LLM analysis."""

    def __init__(self, cmd_template: str | None = None):
        # If template contains {prompt}, it will be shell-quoted and substituted.
        # Otherwise the prompt is passed via stdin.
        self.cmd_template = cmd_template or os.environ.get(
            "CODEX_CMD", "codex exec --json {prompt}"
        )

    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to Codex CLI and parse the JSON response."""
        try:
            cmd_str = self.cmd_template
            input_data = None
            if "{prompt}" in cmd_str:
                cmd_str = cmd_str.replace("{prompt}", shlex.quote(prompt))
            else:
                input_data = prompt.encode()

            args = shlex.split(cmd_str)
            if not args:
                raise ValueError("CODEX_CMD resolved to an empty command")

            codex_bin = _resolve_codex_bin()
            if args[0] == "codex":
                args[0] = codex_bin

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE if input_data is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(input_data)

            if proc.returncode != 0:
                logger.error(
                    "Codex CLI error (rc=%s): stderr=%r stdout=%r",
                    proc.returncode,
                    stderr.decode(),
                    stdout.decode()[:500],
                )
                return {"error": stderr.decode() or stdout.decode()}

            response_text = stdout.decode().strip()
            stream_text, stream_used = self._extract_json_stream_text(response_text)
            if stream_used:
                try:
                    return json.loads(stream_text)
                except json.JSONDecodeError:
                    return {
                        "error": "Codex JSON stream did not contain valid JSON in agent message",
                        "raw_text": stream_text,
                        "parse_error": True,
                    }
            return self._parse_response(stream_text)
        except FileNotFoundError:
            logger.error("Codex CLI not found. Is it installed?")
            return {"error": "Codex CLI not found"}
        except Exception as exc:
            logger.error("Codex CLI exception: %s", exc)
            return {"error": str(exc)}

    _STREAM_EVENT_TYPES = frozenset({
        "thread.started", "turn.started", "item.completed", "turn.completed",
    })

    def _extract_json_stream_text(self, text: str) -> tuple[str, bool]:
        """Handle Codex --json output by extracting the final agent message text."""
        if not text:
            return text, False

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return text, False

        last_agent_text = None
        is_stream = False
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            if payload.get("type") in self._STREAM_EVENT_TYPES:
                is_stream = True

            if payload.get("type") == "item.completed":
                item = payload.get("item") or {}
                if item.get("type") == "agent_message":
                    last_agent_text = item.get("text", last_agent_text)

        if is_stream:
            if last_agent_text is not None:
                return last_agent_text.strip(), True
            return "", True
        return text, False
