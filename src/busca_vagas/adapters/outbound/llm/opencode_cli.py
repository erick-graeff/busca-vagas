"""LLMClient via CLI do opencode (`opencode run`)."""

import json
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from typing import Any

from busca_vagas.application.ports.llm import LLMError

DEFAULT_MODEL = "opencode/deepseek-v4.1-flash-free"


class OpencodeCLI:
    def __init__(self, model: str = DEFAULT_MODEL, timeout: float = 180, binary: str = "opencode"):
        self.model = model
        self.timeout = timeout
        self.binary = binary

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> "OpencodeCLI":
        return cls(
            model=options.get("model") or DEFAULT_MODEL,
            timeout=options.get("timeout", 180),
            binary=options.get("binary", "opencode"),
        )

    @property
    def model_id(self) -> str:
        return self.model

    def complete(self, prompt: str) -> str:
        if shutil.which(self.binary) is None:
            raise LLMError(f"'{self.binary}' não encontrado no PATH")
        cmd = [self.binary, "run", "--model", self.model, "--format", "json", "--archived", prompt]
        # cwd temporário: o agente do opencode não enxerga os arquivos do projeto.
        with tempfile.TemporaryDirectory() as cwd:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout, cwd=cwd)
            except subprocess.TimeoutExpired as e:
                raise LLMError(f"opencode excedeu {self.timeout}s") from e
        if proc.returncode != 0:
            raise LLMError(proc.stderr.strip() or f"opencode saiu com código {proc.returncode}")
        text = self._extract_text(proc.stdout)
        if not text:
            raise LLMError("opencode não retornou texto")
        return text

    @staticmethod
    def _extract_text(stdout: str) -> str:
        """`--format json` emite um evento JSON por linha; o texto vem nos eventos 'text'."""
        texts = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and event.get("type") == "text":
                texts.append(event.get("part", {}).get("text", ""))
        return "".join(texts).strip()
