"""Tests for deterministic lexical and semantic drift calculation engine."""
from backend.app.services.drift_engine import (
    compute_drift_score,
    classify_drift_magnitude,
    diff_chunks,
    tokenize,
    compute_shingles,
    jaccard_distance
)


def test_drift_identical_text():
    """Identical content must yield exactly 0.0 drift score."""
    text = "The quick brown fox jumps over the lazy dog."
    assert compute_drift_score(text, text) == 0.0
    assert classify_drift_magnitude(0.0) == "none"


def test_drift_completely_divergent_text():
    """Totally divergent texts must yield high drift close to 1.0."""
    t1 = "Kubernetes pods communicate via overlay network interfaces."
    t2 = "Chocolate cake recipe requires eggs flour sugar and cocoa powder."
    score = compute_drift_score(t1, t2)
    assert score >= 0.85
    assert classify_drift_magnitude(score) == "critical_semantic"


def test_drift_cosmetic_edits():
    """Minor punctuation and spacing adjustments should yield low drift."""
    t1 = "Service health check returns HTTP 200 within 50 milliseconds."
    t2 = "Service health check returns HTTP 200, within 50 milliseconds."
    score = compute_drift_score(t1, t2)
    assert score <= 0.10


def test_chunk_diffing_categories():
    """Chunk diffing properly categorizes unchanged, modified, added, and removed chunks."""
    chunks_orig = [
        "Unchanged chunk one.",
        "Modified chunk originally discussing version 1.",
        "Deprecated chunk to be deleted."
    ]
    chunks_rev = [
        "Unchanged chunk one.",
        "Modified chunk updated to discuss version 2.",
        "Brand new chunk introducing telemetry."
    ]

    res = diff_chunks(chunks_orig, chunks_rev)
    assert res["unchanged_count"] == 1
    assert res["modified_count"] == 1
    assert res["removed_count"] == 1
    assert res["added_count"] == 1


def test_shingle_and_jaccard_properties():
    """Shingle and Jaccard distance calculation handles small and empty inputs."""
    tokens = tokenize("alpha beta gamma")
    shingles = compute_shingles(tokens, k=2)
    assert len(shingles) == 2
    assert jaccard_distance(set(), set()) == 0.0
    assert jaccard_distance(shingles, shingles) == 0.0
