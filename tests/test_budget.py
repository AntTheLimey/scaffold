import pytest

from orchestrator.budget import BudgetExceededError, cost_for_tokens


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


class TestCostForTokens:
    def test_known_model_sonnet_full_million(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=1_000_000, token_out=1_000_000)
        assert cost == pytest.approx(18.0)

    def test_known_model_opus_full_million(self):
        cost = cost_for_tokens("claude-opus-4-7", token_in=1_000_000, token_out=1_000_000)
        assert cost == pytest.approx(90.0)

    def test_known_model_haiku(self):
        cost = cost_for_tokens("claude-haiku-4-5", token_in=1_000_000, token_out=1_000_000)
        assert cost == pytest.approx(4.8)

    def test_fractional_tokens_sonnet(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=500_000, token_out=500_000)
        assert cost == pytest.approx(9.0)

    def test_input_only_tokens(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=1_000_000, token_out=0)
        assert cost == pytest.approx(3.0)

    def test_output_only_tokens(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=0, token_out=1_000_000)
        assert cost == pytest.approx(15.0)

    def test_unknown_model_returns_zero(self):
        cost = cost_for_tokens("unknown-model-xyz", token_in=100_000, token_out=100_000)
        assert cost == 0.0

    def test_zero_tokens_returns_zero(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=0, token_out=0)
        assert cost == 0.0

    def test_small_token_count(self):
        cost = cost_for_tokens("claude-sonnet-4-6", token_in=1000, token_out=500)
        assert cost == pytest.approx(0.003 + 0.0075)

    def test_opus_4_6_same_price_as_opus_4_7(self):
        cost_46 = cost_for_tokens("claude-opus-4-6", token_in=1_000_000, token_out=1_000_000)
        cost_47 = cost_for_tokens("claude-opus-4-7", token_in=1_000_000, token_out=1_000_000)
        assert cost_46 == pytest.approx(cost_47)
