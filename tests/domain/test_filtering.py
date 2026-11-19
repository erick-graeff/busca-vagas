import pytest

from busca_vagas.domain.filtering import passes_profile, rank, score
from busca_vagas.domain.levels import detect_levels
from busca_vagas.domain.models import Level
from busca_vagas.domain.rules import FilterRules, Keyword, SearchProfile, word_pattern
from tests.conftest import make_posting


# --- caracterização: o comportamento do protótipo original foi preservado ----------------


def test_baseline_score_and_profile_for_every_fixture_posting(ciandt_postings, rules, profile, baseline):
    assert len(ciandt_postings) == len(baseline) == 107
    for posting in ciandt_postings:
        expected = baseline[posting.id]
        scored = score(posting, rules)
        assert passes_profile(posting, profile, rules) == expected["passes_profile"], posting.title
        assert (scored.score if scored else None) == expected["score"], posting.title
        assert (scored.matched if scored else None) == expected["matched"], posting.title


def test_baseline_final_ranking(ciandt_postings, rules, profile):
    results = rank(
        [s for p in ciandt_postings if passes_profile(p, profile, rules) and (s := score(p, rules))]
    )
    assert [r.score for r in results] == [35, 34, 20, 16, 15]
    assert "Back End Developer" in results[0].posting.title


# --- unidades ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("terms", "text", "expected"),
    [
        (["sql"], "SQL e PostgreSQL", True),
        (["sql"], "NoSQL e PostgreSQL", False),
        (["java"], "JavaScript", False),
        (["java"], "Java/Spring", True),
        (["c"], "C# e C++", False),
        ([".net"], "React/.NET", True),
        (["back end"], "Back End Developer", True),
        (["python"], "PYTHON", True),
    ],
)
def test_word_pattern(terms, text, expected):
    assert bool(word_pattern(terms).search(text)) is expected


def test_word_pattern_empty_is_none():
    assert word_pattern([]) is None


def test_detect_levels(rules):
    assert detect_levels("Senior/Pleno Developer", rules.level_patterns) == {Level.SENIOR, Level.MID}
    assert detect_levels("AI Lead Software Engineer", rules.level_patterns) == {Level.MASTER}
    assert detect_levels("Software Engineer", rules.level_patterns) == set()


def test_required_keyword_in_title_overrides_stack_exclusion(rules):
    assert score(make_posting(title="Senior Back End Developer (Python/Golang)"), rules) is not None
    assert score(make_posting(title="Senior Golang Developer"), rules) is None


def test_posting_without_required_keyword_is_rejected(rules):
    assert score(make_posting(title="Senior Developer", description="Ruby on Rails"), rules) is None


def test_title_bonus_and_mention_bonus():
    rules = FilterRules(required=(Keyword("Python", ("python",), 10),), title_bonus=2)
    body_only = score(make_posting(title="Dev", description="python python"), rules)
    in_title = score(make_posting(title="Python Dev", description="python"), rules)
    assert body_only.score == 10 + 3  # 1 menção extra
    assert in_title.score == (10 + 3) * 2  # título + descrição = 2 menções, dobrado


def test_profile_unknown_fields_do_not_reject(rules):
    profile = SearchProfile(levels=frozenset({Level.SENIOR}), countries=frozenset({"BR"}), remote_only=True)
    assert passes_profile(make_posting(workplace_type=""), profile, rules)
    assert not passes_profile(make_posting(workplace_type="hybrid"), profile, rules)
    assert not passes_profile(make_posting(country="CO"), profile, rules)
    assert not passes_profile(make_posting(title="Pleno Python Developer"), profile, rules)
    assert passes_profile(make_posting(title="Python Developer"), profile, rules)  # sem nível
