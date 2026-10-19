"""Optional live DeepSeek smoke test; never required for normal test runs."""

import os

import pytest
from test_provider_application import account_input, request

from task_decomposition import decompose
from task_decomposition.providers.deepseek import DeepSeekDecompositionProvider


@pytest.mark.integration
def test_live_deepseek_provider():
    if os.getenv("RUN_LIVE_PROVIDER_TESTS") != "1" or not os.getenv("DEEPSEEK_API_KEY"):
        pytest.skip("set RUN_LIVE_PROVIDER_TESTS=1 and DEEPSEEK_API_KEY to run")
    result = decompose(
        request(),
        DeepSeekDecompositionProvider(),
        transformation_context={"domain": "customer_support"},
        accounting_input=account_input(),
    )
    assert len(result.provider_provenance) == 3
    assert result.accounting.w0 == 100
