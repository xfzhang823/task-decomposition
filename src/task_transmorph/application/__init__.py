"""Provider-independent application orchestration."""

from task_transmorph.application.normalized_estimation import estimate_transformation
from task_transmorph.application.provider_service import decompose
from task_transmorph.application.task_decomposition import decompose_task
from task_transmorph.application.transformation_decomposition import (
    decompose_transformation,
)

__all__ = [
    "decompose",
    "decompose_task",
    "decompose_transformation",
    "estimate_transformation",
]
