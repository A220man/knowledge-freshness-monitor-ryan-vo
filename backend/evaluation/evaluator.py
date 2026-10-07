"""Offline evaluation harness comparing drift and citation impact algorithms against labeled benchmarks."""
import json
import time
from pathlib import Path
from typing import Dict, Any, List
from backend.app.services.drift_engine import compute_drift_score, classify_drift_magnitude


def run_benchmark_evaluation(dataset_path: str = None) -> Dict[str, Any]:
    """Evaluates the offline freshness detection pipeline against labeled test cases."""
    if dataset_path is None:
        dataset_path = str(Path(__file__).parent / "benchmark_dataset.json")

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    true_positives = 0
    true_negatives = 0
    false_positives = 0
    false_negatives = 0
    severity_correct = 0

    latencies: List[float] = []
    failure_cases: List[Dict[str, Any]] = []

    for case in cases:
        t0 = time.perf_counter()
        drift = compute_drift_score(case["orig_text"], case["rev_text"])

        # Determine edge impact
        edge_severity = 0.0
        if case["is_expired"]:
            edge_severity = 1.0
        elif drift >= 0.35:
            edge_severity = min(1.0, 0.40 + drift * 0.60)

        role_multiplier = 1.0 if case["is_primary"] else 0.45
        confidence = max(0.2, min(1.0, case["confidence"]))
        edge_impact = edge_severity * role_multiplier * confidence

        # Apply primary escalation if needed
        is_compromised = case["is_expired"] or (case["is_primary"] and drift >= 0.35)
        if case["is_primary"] and is_compromised:
            impact_score = max(edge_impact, 0.75)
        else:
            impact_score = edge_impact

        if case["is_expired"] and case["is_primary"]:
            impact_score = max(impact_score, 0.90)

        # Categorize
        if impact_score >= 0.70 or (case["is_primary"] and case["is_expired"]):
            pred_severity = "critical_stale"
        elif impact_score >= 0.25:
            pred_severity = "stale"
        else:
            pred_severity = "fresh"

        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        pred_revalidate = pred_severity in {"stale", "critical_stale"}
        exp_revalidate = case["expected_revalidate"]

        # Confusion matrix
        if pred_revalidate and exp_revalidate:
            true_positives += 1
        elif not pred_revalidate and not exp_revalidate:
            true_negatives += 1
        elif pred_revalidate and not exp_revalidate:
            false_positives += 1
            failure_cases.append({
                "id": case["id"],
                "description": case["description"],
                "type": "false_positive",
                "drift_score": drift,
                "pred_severity": pred_severity,
                "expected_severity": case["expected_severity"]
            })
        else:
            false_negatives += 1
            failure_cases.append({
                "id": case["id"],
                "description": case["description"],
                "type": "false_negative",
                "drift_score": drift,
                "pred_severity": pred_severity,
                "expected_severity": case["expected_severity"]
            })

        if pred_severity == case["expected_severity"]:
            severity_correct += 1

    total = len(cases)
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0.0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = severity_correct / total if total > 0 else 0.0
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0

    return {
        "dataset_name": "RAG Knowledge Freshness Benchmark (v1.0)",
        "total_cases": total,
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "drift_detection_accuracy": round(accuracy, 4),
        "mean_latency_ms": round(mean_latency, 3),
        "failure_cases": failure_cases
    }


def main():
    results = run_benchmark_evaluation()
    print("==================================================")
    print(" KNOWLEDGE FRESHNESS EVALUATION BENCHMARK RESULTS")
    print("==================================================")
    print(f"Total Test Cases:            {results['total_cases']}")
    print(f"Revalidation Precision:      {results['precision'] * 100:.1f}%")
    print(f"Revalidation Recall:         {results['recall'] * 100:.1f}%")
    print(f"Revalidation F1 Score:       {results['f1_score']:.4f}")
    print(f"Severity Match Accuracy:     {results['drift_detection_accuracy'] * 100:.1f}%")
    print(f"Mean Latency Per Evaluation: {results['mean_latency_ms']:.3f} ms")
    print(f"Failures (Misclassifications): {len(results['failure_cases'])}")
    if results['failure_cases']:
        for fc in results['failure_cases']:
            print(f" - [{fc['id']}] {fc['description']} ({fc['type']}): Pred={fc['pred_severity']} Exp={fc['expected_severity']}")
    print("==================================================")


if __name__ == "__main__":
    main()
