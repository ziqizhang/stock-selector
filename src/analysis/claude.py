import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ClaudeCLI:
    """Wrapper around the Claude Code CLI for LLM analysis."""

    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to Claude CLI and parse the JSON response."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "--print", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Claude CLI error: {stderr.decode()}")
                return {"error": stderr.decode()}

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
