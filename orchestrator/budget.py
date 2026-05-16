class BudgetExceededError(Exception):
    def __init__(self, spent: float, limit: float):
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget exceeded: ${spent:.2f} spent, ${limit:.2f} limit")
