"""KeyValueStore em arquivos JSON: um arquivo por namespace em `data_dir`."""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._data: dict[str, dict[str, Any]] = {}

    def _file(self, namespace: str) -> Path:
        return self._dir / f"{namespace}.json"

    def _load(self, namespace: str) -> dict[str, Any]:
        if namespace not in self._data:
            path = self._file(namespace)
            self._data[namespace] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return self._data[namespace]

    def get(self, namespace: str, key: str) -> Any | None:
        return self._load(namespace).get(key)

    def has(self, namespace: str, key: str) -> bool:
        return key in self._load(namespace)

    def set(self, namespace: str, key: str, value: Any) -> None:
        data = self._load(namespace)
        data[key] = value
        self._dir.mkdir(parents=True, exist_ok=True)
        # escrita atômica: um cron interrompido não corrompe o arquivo
        fd, tmp = tempfile.mkstemp(dir=self._dir, prefix=f".{namespace}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, self._file(namespace))
