import subprocess

import pytest

from pr_agent.config_loader import get_settings


CODEX_KEYS = [
    "CODEX.CLI_MODEL",
    "CODEX.CLI_PATH",
    "CODEX.CLI_REASONING_EFFORT",
    "CODEX.CLI_TIMEOUT",
    "CODEX.USE_CLI",
]


@pytest.fixture
def codex_settings():
    settings = get_settings()
    original = {key: settings.get(key, None) for key in CODEX_KEYS}
    yield settings
    for key, value in original.items():
        settings.set(key, value)


@pytest.mark.asyncio
async def test_codex_cli_handler_invokes_codex_exec(monkeypatch, codex_settings):
    from pr_agent.algo.ai_handlers.codex_cli_ai_handler import CodexCLIAIHandler

    codex_settings.set("CODEX.CLI_PATH", "codex-test")
    codex_settings.set("CODEX.CLI_MODEL", "gpt-5.5")
    codex_settings.set("CODEX.CLI_REASONING_EFFORT", "high")
    codex_settings.set("CODEX.CLI_TIMEOUT", 123)
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        output_path = cmd[cmd.index("-o") + 1]
        with open(output_path, "w", encoding="utf-8") as output_file:
            output_file.write("ok\n")
        return subprocess.CompletedProcess(cmd, 0, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    response, finish_reason = await CodexCLIAIHandler().chat_completion(
        model="ignored-by-cli",
        system="system prompt",
        user="user prompt",
    )

    assert response == "ok"
    assert finish_reason == "stop"
    assert len(calls) == 1

    cmd, kwargs = calls[0]
    assert cmd[:2] == ["codex-test", "exec"]
    assert "-m" in cmd
    assert cmd[cmd.index("-m") + 1] == "gpt-5.5"
    assert "-c" in cmd
    assert cmd[cmd.index("-c") + 1] == 'model_reasoning_effort="high"'
    assert cmd[-1] == "-"
    assert kwargs["input"].count("system prompt") == 1
    assert kwargs["input"].count("user prompt") == 1
    assert kwargs["timeout"] == 123
    assert kwargs["stdout"] is subprocess.DEVNULL


def test_pr_agent_uses_codex_cli_handler_when_enabled(codex_settings):
    from pr_agent.agent.pr_agent import PRAgent
    from pr_agent.algo.ai_handlers.codex_cli_ai_handler import CodexCLIAIHandler

    codex_settings.set("CODEX.USE_CLI", True)

    assert PRAgent().ai_handler is CodexCLIAIHandler
