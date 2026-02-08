import asyncio
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# Common locations for claude CLI installed via nvm
_NVM_SEARCH_PATHS = list(Path.home().glob(".nvm/versions/node/*/bin/claude"))


def _find_claude() -> str:
    """Find the claude CLI binary, checking PATH and common nvm locations."""
    found = shutil.which("claude")
    if found:
        return found
    for path in _NVM_SEARCH_PATHS:
        if path.is_file():
            return str(path)
    return "claude"  # fallback, will raise FileNotFoundError if missing


CLAUDE_BIN = _find_claude()


class ClaudeCLI:
    """Wrapper around the Claude Code CLI for LLM analysis."""

    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to Claude CLI and parse the JSON response."""
        try:
            env = {**__import__("os").environ, "CLAUDE_CONFIG_DIR": str(Path.home() / ".claude-zz")}
            proc = await asyncio.create_subprocess_exec(
                CLAUDE_BIN, "--print", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Claude CLI error (rc={proc.returncode}): stderr={stderr.decode()!r} stdout={stdout.decode()[:500]!r}")
                return {"error": stderr.decode() or stdout.decode()}

            response_text = stdout.decode().strip()
            return self._parse_response(response_text)
        except FileNotFoundError:
            logger.error("Claude CLI not found. Is it installed?")
            return {"error": "Claude CLI not found"}
        except Exception as e:
            logger.error(f"Claude CLI exception: {e}")
            return {"error": str(e)}

    def _parse_response(self, text: str) -> dict:
        """Extract JSON from Claude's response, handling markdown code blocks."""
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        # Return as narrative if not JSON
        return {"narrative": text, "parse_error": True}
