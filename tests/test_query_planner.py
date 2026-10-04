from app.models import GameIdea
from app.query_planner import distinctive_tokens, plan_coverage_query, plan_queries


def test_plan_queries_extracts_tokens_not_raw_pitch_only():
    idea = GameIdea(
        title="Rush Bay",
        pitch="unblock colorful buses, match passengers, clear island parking bays",
        keywords="bus parking sort puzzle",
    )
    queries = plan_queries(idea)
    assert 2 <= len(queries) <= 3
    assert queries[0] == "Rush Bay"
    # Must not be only the raw pitch sentence.
    assert idea.pitch not in queries
    joined = " ".join(queries).lower()
    assert "bus" in joined or "parking" in joined or "sort" in joined


def test_distinctive_tokens_drop_stopwords():
    toks = distinctive_tokens("the colorful buses and the parking")
    assert "the" not in toks
    assert "and" not in toks
    assert "colorful" in toks
    assert "buses" in toks or "parking" in toks


def test_coverage_query_mentions_play():
    idea = GameIdea(title="Rush Bay", pitch="bus parking sort", keywords="puzzle")
    q = plan_coverage_query(idea)
    assert "Google Play" in q or "mobile game" in q
