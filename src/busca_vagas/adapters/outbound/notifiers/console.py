import sys
from typing import TextIO

from busca_vagas.application.ports.inbound import SearchReport


class ConsoleNotifier:
    def __init__(self, stream: TextIO | None = None):
        self._stream = stream

    def notify(self, report: SearchReport) -> None:
        out = self._stream or sys.stdout
        n_new = len(report.new_results)
        print(
            f"{len(report.results)} vagas selecionadas de {report.total_fetched} buscadas"
            f" ({n_new} novas)\n",
            file=out,
        )
        for r in report.results:
            p = r.posting
            new = " [NOVA]" if p.key in report.new_keys else ""
            print(f"[{r.score:>3}] {p.title}  ({p.company} / {p.location}){new}", file=out)
            print(f"      match: {', '.join(r.matched)}", file=out)
            print(f"      {p.url}", file=out)
            if r.match:
                if r.match.ok:
                    if r.match.job_summary:
                        print(f"      vaga: {r.match.job_summary}", file=out)
                    print(f"      IA: {r.match.score}/100 - {r.match.summary}", file=out)
                else:
                    print(f"      IA: erro - {r.match.error}", file=out)
        for error in report.errors:
            print(f"AVISO: {error}", file=sys.stderr)
