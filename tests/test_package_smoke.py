from task_transmorph import account_normalized


def test_public_accounting_smoke():
    assert callable(account_normalized)
