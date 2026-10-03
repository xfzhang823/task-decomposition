"""Provider-independent application orchestration."""

from task_decomposition.application.task_decomposition import decompose_task
from task_decomposition.application.transformation_decomposition import (
    decompose_transformation,
)
from task_decomposition.application.staged_pipeline import run_staged_pipeline
from task_decomposition.application.provider_service import decompose

__all__ = [
    "decompose",
    "decompose_task",
    "decompose_transformation",
    "run_staged_pipeline",
]
