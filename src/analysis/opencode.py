import asyncio
import json
import logging
import shlex
import shutil

from src.analysis.llm_base import LLMProvider

logger = logging.getLogger(__name__)


def _resolve_opencode_bin() -> str:
    """Resolve the opencode CLI binary path."""
    return shutil.which("opencode") or "opencode"


class OpencodeCLI(LLMProvider):
    """Wrapper around the Opencode CLI for LLM analysis."""

    def __init__(self, cmd_template: str | None = None):
        # Default command template for opencode with JSON output
        self.cmd_template = cmd_template or "opencode run {prompt} --format json"

    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to Opencode CLI and parse the JSON response."""
        try:
            cmd_str = self.cmd_template
            input_data = None
            if "{prompt}" in cmd_str:
                cmd_str = cmd_str.replace("{prompt}", shlex.quote(prompt))
            else:
                input_data = prompt.encode()

            args = shlex.split(cmd_str)
            if not args:
                raise ValueError("Opencode command resolved to an empty command")

            opencode_bin = _resolve_opencode_bin()
            if args[0] == "opencode":
                args[0] = opencode_bin

            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE if input_data is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate(input_data)

            if proc.returncode != 0:
                logger.error(
                    "Opencode CLI error (rc=%s): stderr=%r stdout=%r",
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
                        "error": "Opencode JSON stream did not contain valid JSON in text message",
                        "raw_text": stream_text,
                        "parse_error": True,
                    }
            return self._parse_response(stream_text)
        except FileNotFoundError:
            logger.error("Opencode CLI not found. Is it installed?")
            return {"error": "Opencode CLI not found"}
        except Exception as exc:
            logger.error("Opencode CLI exception: %s", exc)
            return {"error": str(exc)}

    def _extract_json_stream_text(self, text: str) -> tuple[str, bool]:
        """Handle Opencode --format output by extracting the text message content."""
        if not text:
            return text, False

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return text, False

        last_text_content = None
        is_stream = False
        for line in lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Check for streaming format
            if payload.get("type") in {"step_start", "text", "step_finish"}:
                is_stream = True

            # Extract text content from "text" type messages
            if payload.get("type") == "text":
                part = payload.get("part", {})
                if "text" in part:
                    last_text_content = part["text"]

        if is_stream:
            if last_text_content is not None:
                return last_text_content.strip(), True
            return "", True
        return text, False
