"""Optional live Gemini smoke test; never required for normal test runs."""

import os

import pytest

from task_decomposition import decompose
from task_decomposition.providers.gemini import GeminiDecompositionProvider

from test_provider_application import account_input, request


@pytest.mark.integration
def test_live_gemini_provider():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY is not configured")
    result = decompose(
        request(),
        GeminiDecompositionProvider(),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert len(result.provider_provenance) == 3
    assert result.accounting.w0 == 100
