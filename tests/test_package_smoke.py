from task_decomposition import account_normalized


def test_public_accounting_smoke():
    assert callable(account_normalized)
