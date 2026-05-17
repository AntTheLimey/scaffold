from orchestrator.budget import BudgetExceededError


def test_budget_exceeded_error_attributes():
    err = BudgetExceededError(spent=3.47, limit=5.00)
    assert err.spent == 3.47
    assert err.limit == 5.00


def test_budget_exceeded_error_message():
    err = BudgetExceededError(spent=3.47, limit=5.00)
    assert "$3.47" in str(err)
    assert "$5.00" in str(err)


def test_budget_exceeded_error_is_exception():
    err = BudgetExceededError(spent=1.0, limit=2.0)
    assert isinstance(err, Exception)
