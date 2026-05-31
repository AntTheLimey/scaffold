MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input $/M tokens, output $/M tokens)
    "claude-opus-4-7": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    "claude-haiku-4-5-20251001": (0.80, 4.0),
    "claude-3-opus-20240229": (15.0, 75.0),
    "claude-3-5-sonnet-20241022": (3.0, 15.0),
    "claude-3-5-haiku-20241022": (1.0, 5.0),
    "claude-3-haiku-20240307": (0.25, 1.25),
}


def cost_for_tokens(model: str, token_in: int, token_out: int) -> float:
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        for key in sorted(MODEL_PRICING, key=len, reverse=True):
            if model.startswith(key):
                pricing = MODEL_PRICING[key]
                break
    if pricing is None:
        return 0.0
    input_price, output_price = pricing
    return (token_in * input_price + token_out * output_price) / 1_000_000


class BudgetExceededError(Exception):
    def __init__(self, spent: float, limit: float):
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget exceeded: ${spent:.2f} spent, ${limit:.2f} limit")
