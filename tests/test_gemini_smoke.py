"""Optional live Gemini smoke test; never required for normal test runs."""

import os

import pytest
from test_provider_application import account_input, request

from task_decomposition import decompose
from task_decomposition.providers.gemini import GeminiDecompositionProvider


@pytest.mark.integration
def test_live_gemini_provider():
    if os.getenv("RUN_LIVE_PROVIDER_TESTS") != "1" or not os.getenv("GEMINI_API_KEY"):
        pytest.skip("set RUN_LIVE_PROVIDER_TESTS=1 and GEMINI_API_KEY to run")
    result = decompose(
        request(),
        GeminiDecompositionProvider(),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert len(result.provider_provenance) == 3
    assert result.accounting.w0 == 100
