"""Provider-independent application orchestration."""

from task_decomposition.application.staged_pipeline import run_staged_pipeline
from task_decomposition.application.provider_service import decompose

__all__ = ["decompose", "run_staged_pipeline"]
