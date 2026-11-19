import json
from dataclasses import asdict
from pathlib import Path

from busca_vagas.application.ports.inbound import SearchReport


class JsonFileNotifier:
    """Grava o relatório completo da última execução num arquivo JSON."""

    def __init__(self, path: Path):
        self._path = Path(path)

    def notify(self, report: SearchReport) -> None:
        payload = {
            "generated_at": report.generated_at.isoformat(),
            "total_fetched": report.total_fetched,
            "errors": report.errors,
            "results": [
                {**asdict(r), "key": r.posting.key, "is_new": r.posting.key in report.new_keys}
                for r in report.results
            ],
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
