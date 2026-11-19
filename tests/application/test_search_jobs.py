from datetime import datetime

import pytest

from busca_vagas.application.ports.inbound import SearchRequest
from busca_vagas.application.use_cases.match_jobs import MatchJobs
from busca_vagas.application.use_cases.search_jobs import SearchJobsService, SourceSpec
from busca_vagas.domain.models import Level
from busca_vagas.domain.rules import SearchProfile
from tests.application.fakes import FakeLLM, FakeNotifier, FakeSource, InMemoryStore
from tests.conftest import make_posting

PROFILE = SearchProfile(levels=frozenset({Level.SENIOR}))


def service(rules, postings=None, *, store=None, llm=None, sources=None, notifier=None, reporter=None):
    store = store if store is not None else InMemoryStore()
    sources = sources or [SourceSpec(FakeSource(postings or []), PROFILE)]
    matcher = MatchJobs(llm, store, "{title}\n{curriculo}", "cv") if llm else None
    return SearchJobsService(
        sources=sources,
        rules=rules,
        store=store,
        reporters=[reporter] if reporter else [],
        notifiers=[notifier] if notifier else [],
        matcher=matcher,
        clock=lambda: datetime(2026, 11, 19, 8, 0),
    )


def test_end_to_end_with_fixture(rules, profile, ciandt_postings):
    svc = service(rules, sources=[SourceSpec(FakeSource(ciandt_postings), profile)])
    report = svc.run(SearchRequest())
    assert report.total_fetched == 107
    assert [r.score for r in report.results] == [35, 34, 20, 16, 15]


def test_new_only_and_seen_tracking(rules):
    store = InMemoryStore()
    first = [make_posting(id="1")]
    assert len(service(rules, first, store=store).run(SearchRequest(new_only=True)).results) == 1

    both = [make_posting(id="1"), make_posting(id="2", url="u2")]
    report = service(rules, both, store=store).run(SearchRequest(new_only=True))
    assert [r.posting.id for r in report.results] == ["2"]
    assert report.new_keys == {"fake:acme:2"}
    assert store.get("seen", "fake:acme:1") == {"first_seen": "2026-11-19T08:00:00"}


def test_without_new_only_reports_everything_but_flags_new(rules):
    store = InMemoryStore()
    service(rules, [make_posting(id="1")], store=store).run(SearchRequest())
    report = service(rules, [make_posting(id="1"), make_posting(id="2")], store=store).run(SearchRequest())
    assert len(report.results) == 2
    assert [r.posting.id for r in report.new_results] == ["2"]


def test_failed_match_is_not_marked_seen(rules):
    store = InMemoryStore()
    report = service(rules, [make_posting()], store=store, llm=FakeLLM(fail=True)).run(
        SearchRequest(match=True, new_only=True)
    )
    assert report.results[0].match.error == "timeout"
    assert report.errors
    assert not store.has("seen", "fake:acme:1")  # será retentada no próximo cron


def test_match_attaches_result(rules):
    report = service(rules, [make_posting()], llm=FakeLLM()).run(SearchRequest(match=True))
    assert report.results[0].match.score == 80


def test_match_without_matcher_is_an_error(rules):
    with pytest.raises(ValueError):
        service(rules, [make_posting()]).run(SearchRequest(match=True))


def test_source_failure_does_not_stop_other_sources(rules):
    sources = [
        SourceSpec(FakeSource([], name="fake:down", fail=True), PROFILE),
        SourceSpec(FakeSource([make_posting()]), PROFILE),
    ]
    report = service(rules, sources=sources).run(SearchRequest())
    assert len(report.results) == 1
    assert report.errors == ["fake:down: fora do ar"]


def test_dedupe_across_sources(rules):
    p = make_posting()
    sources = [SourceSpec(FakeSource([p], name="a"), PROFILE), SourceSpec(FakeSource([p], name="b"), PROFILE)]
    assert len(service(rules, sources=sources).run(SearchRequest()).results) == 1


def test_notifiers_only_with_notify_reporters_always(rules):
    reporter, notifier = FakeNotifier(), FakeNotifier()
    svc = service(rules, [make_posting()], reporter=reporter, notifier=notifier)
    svc.run(SearchRequest())
    assert len(reporter.reports) == 1 and notifier.reports == []
    svc.run(SearchRequest(notify=True))
    assert len(reporter.reports) == 2 and len(notifier.reports) == 1
