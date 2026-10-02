"""Optional live DeepSeek smoke test; never required for normal test runs."""

import os

import pytest

from task_decomposition import decompose
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider

from test_provider_application import request


@pytest.mark.integration
def test_live_deepseek_provider():
    if not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY is not configured")
    result = decompose(request(), DeepSeekDecompositionProvider())
    assert len(result.provider_provenance) == 3
    assert result.accounting.w0 == 100
