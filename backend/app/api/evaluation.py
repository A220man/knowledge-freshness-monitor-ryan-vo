"""Evaluation API endpoints providing access to reproducible benchmark metrics."""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from backend.app.core.security import require_viewer
from backend.app.models.entities import UserSession
from backend.app.models.schemas import BenchmarkResultResponse
from backend.evaluation.evaluator import run_benchmark_evaluation

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/run", response_model=BenchmarkResultResponse)
def execute_benchmark(session: UserSession = Depends(require_viewer)) -> BenchmarkResultResponse:
    """Executes the offline deterministic freshness detection benchmark and returns metrics."""
    results = run_benchmark_evaluation()
    return BenchmarkResultResponse(
        dataset_name=results["dataset_name"],
        total_cases=results["total_cases"],
        precision=results["precision"],
        recall=results["recall"],
        f1_score=results["f1_score"],
        mean_latency_ms=results["mean_latency_ms"],
        drift_detection_accuracy=results["drift_detection_accuracy"],
        failure_cases=results["failure_cases"]
    )
