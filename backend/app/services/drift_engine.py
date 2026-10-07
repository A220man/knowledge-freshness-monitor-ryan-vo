"""Deterministic offline lexical and semantic drift calculation engine."""
import re
import math
from typing import List, Dict, Tuple, Set, Any


def tokenize(text: str) -> List[str]:
    """Extracts lowercase alphanumeric word tokens."""
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())


def compute_shingles(tokens: List[str], k: int = 2) -> Set[Tuple[str, ...]]:
    """Constructs k-gram shingles from a token list."""
    if len(tokens) < k:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def jaccard_distance(set_a: Set[Any], set_b: Set[Any]) -> float:
    """Computes Jaccard distance: 1.0 - (intersection / union)."""
    if not set_a and not set_b:
        return 0.0
    union = set_a | set_b
    if not union:
        return 0.0
    intersection = set_a & set_b
    return 1.0 - (len(intersection) / len(union))


def compute_tf_vector(tokens: List[str]) -> Dict[str, float]:
    """Calculates term frequency counts for tokens."""
    tf: Dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    return tf


def cosine_distance(tf_a: Dict[str, float], tf_b: Dict[str, float]) -> float:
    """Computes cosine distance (1.0 - cosine similarity) between two frequency vectors."""
    if not tf_a and not tf_b:
        return 0.0
    if not tf_a or not tf_b:
        return 1.0

    dot_product = sum(tf_a[k] * tf_b.get(k, 0.0) for k in tf_a)
    norm_a = math.sqrt(sum(v * v for v in tf_a.values()))
    norm_b = math.sqrt(sum(v * v for v in tf_b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0

    similarity = dot_product / (norm_a * norm_b)
    # Clip between 0.0 and 1.0 due to float precision
    similarity = max(0.0, min(1.0, similarity))
    return 1.0 - similarity


def compute_drift_score(text_original: str, text_revised: str) -> float:
    """Calculates composite normalized drift score between two texts in range [0.0, 1.0]."""
    if text_original.strip() == text_revised.strip():
        return 0.0

    tokens_orig = tokenize(text_original)
    tokens_rev = tokenize(text_revised)

    if not tokens_orig and not tokens_rev:
        return 0.0
    if not tokens_orig or not tokens_rev:
        return 1.0

    # Shingle Jaccard
    shingles_orig = compute_shingles(tokens_orig, k=2)
    shingles_rev = compute_shingles(tokens_rev, k=2)
    j_dist = jaccard_distance(shingles_orig, shingles_rev)

    # Term Frequency Cosine Distance
    tf_orig = compute_tf_vector(tokens_orig)
    tf_rev = compute_tf_vector(tokens_rev)
    c_dist = cosine_distance(tf_orig, tf_rev)

    # Composite weight: 55% Jaccard (structure & phrase ordering) + 45% Cosine (lexical distribution)
    drift = (0.55 * j_dist) + (0.45 * c_dist)
    return round(max(0.0, min(1.0, drift)), 4)


def classify_drift_magnitude(drift_score: float) -> str:
    """Classifies drift severity level."""
    if drift_score <= 0.05:
        return "none"
    elif drift_score < 0.25:
        return "minor"
    elif drift_score < 0.60:
        return "moderate"
    else:
        return "critical_semantic"


def diff_chunks(
    chunks_original: List[str],
    chunks_revised: List[str]
) -> Dict[str, Any]:
    """Compares chunks between revisions to identify modified, added, and retained chunks."""
    matched_orig: Set[int] = set()
    matched_rev: Set[int] = set()
    chunk_diffs: List[Dict[str, Any]] = []

    # First pass: exact matches
    for i, c_orig in enumerate(chunks_original):
        for j, c_rev in enumerate(chunks_revised):
            if j not in matched_rev and c_orig.strip() == c_rev.strip():
                matched_orig.add(i)
                matched_rev.add(j)
                chunk_diffs.append({
                    "orig_index": i,
                    "rev_index": j,
                    "status": "unchanged",
                    "drift_score": 0.0
                })
                break

    # Second pass: compute closest pairings for remaining chunks
    for i, c_orig in enumerate(chunks_original):
        if i in matched_orig:
            continue
        best_j = -1
        min_drift = 1.0
        for j, c_rev in enumerate(chunks_revised):
            if j in matched_rev:
                continue
            d = compute_drift_score(c_orig, c_rev)
            if d < min_drift:
                min_drift = d
                best_j = j

        if best_j != -1 and min_drift < 0.85:
            matched_orig.add(i)
            matched_rev.add(best_j)
            chunk_diffs.append({
                "orig_index": i,
                "rev_index": best_j,
                "status": "modified",
                "drift_score": min_drift
            })
        else:
            chunk_diffs.append({
                "orig_index": i,
                "rev_index": None,
                "status": "removed",
                "drift_score": 1.0
            })

    # Any leftover revised chunks were added
    for j, _ in enumerate(chunks_revised):
        if j not in matched_rev:
            chunk_diffs.append({
                "orig_index": None,
                "rev_index": j,
                "status": "added",
                "drift_score": 1.0
            })

    return {
        "total_original": len(chunks_original),
        "total_revised": len(chunks_revised),
        "diffs": chunk_diffs,
        "unchanged_count": len([d for d in chunk_diffs if d["status"] == "unchanged"]),
        "modified_count": len([d for d in chunk_diffs if d["status"] == "modified"]),
        "removed_count": len([d for d in chunk_diffs if d["status"] == "removed"]),
        "added_count": len([d for d in chunk_diffs if d["status"] == "added"])
    }
