import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger


DEFAULT_CODEX_CLI_MODEL = "gpt-5.5"
DEFAULT_CODEX_CLI_PATH = "codex"
DEFAULT_CODEX_CLI_TIMEOUT = 300


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def is_codex_cli_enabled() -> bool:
    return _as_bool(get_settings().get("CODEX.USE_CLI", False))


class CodexCLIAIHandler(BaseAiHandler):
    """
    AI handler that delegates completions to the authenticated local Codex CLI.

    This is intended for local/self-hosted GitHub App runs where a ChatGPT Codex seat is available through
    `codex exec`, but direct HTTP calls to the ChatGPT Codex backend are not suitable for unattended
    service use.
    """

    def __init__(self):
        settings = get_settings()
        self.cli_path = settings.get("CODEX.CLI_PATH", DEFAULT_CODEX_CLI_PATH)
        self.cli_model = settings.get("CODEX.CLI_MODEL", DEFAULT_CODEX_CLI_MODEL)
        self.cli_reasoning_effort = settings.get("CODEX.CLI_REASONING_EFFORT", "")
        self.cli_timeout = int(settings.get("CODEX.CLI_TIMEOUT", DEFAULT_CODEX_CLI_TIMEOUT))

    @property
    def deployment_id(self):
        return None

    async def chat_completion(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        img_path: str = None,
    ):
        if img_path:
            get_logger().warning(
                f"Image path is not supported for CodexCLIAIHandler. Ignoring image path: {img_path}"
            )

        prompt = self._format_prompt(system, user)
        response = await asyncio.to_thread(self._run_codex_exec, prompt)
        return response, "stop"

    @staticmethod
    def _format_prompt(system: str, user: str) -> str:
        return (
            "You are acting as a completion backend for PR-Agent. Follow the instructions below, and return only "
            "the requested final response.\n\n"
            f"<system>\n{system or ''}\n</system>\n\n"
            f"<user>\n{user or ''}\n</user>\n"
        )

    def _run_codex_exec(self, prompt: str) -> str:
        with tempfile.NamedTemporaryFile(prefix="pr-agent-codex-", suffix=".txt", delete=False) as output_file:
            output_path = Path(output_file.name)

        try:
            cmd = [
                self.cli_path,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "-m",
                self.cli_model,
            ]
            if self.cli_reasoning_effort:
                cmd.extend(["-c", f'model_reasoning_effort="{self.cli_reasoning_effort}"'])
            cmd.extend(["-o", str(output_path), "-"])

            result = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=self.cli_timeout,
                check=False,
            )
            if result.returncode != 0:
                error = (result.stderr or "").strip()[-1000:]
                raise RuntimeError(f"Codex CLI exited with code {result.returncode}: {error}")

            response = output_path.read_text(encoding="utf-8").strip()
            if not response:
                raise RuntimeError("Codex CLI produced an empty response")
            return response
        finally:
            output_path.unlink(missing_ok=True)
