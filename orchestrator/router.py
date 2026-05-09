from orchestrator.config import GovernanceConfig

LEVEL_ROLE_MAP = {
    "epic": "product_owner",
    "feature": "architect",
}

STATUS_ROLE_MAP = {
    "in_review": "reviewer",
    "testing": "qa",
}


class Router:
    def __init__(self, governance: GovernanceConfig):
        self.governance = governance

    def route_task(self, level: str, status: str) -> str:
        if status in STATUS_ROLE_MAP:
            return STATUS_ROLE_MAP[status]
        if level in LEVEL_ROLE_MAP:
            return LEVEL_ROLE_MAP[level]
        return "developer"

    def get_rapid_roles(self, decision_type: str) -> dict[str, str]:
        return self.governance.rapid[decision_type]

    def get_accountable(self, activity: str) -> str:
        return self.governance.raci[activity]["accountable"]

    def get_consulted(self, activity: str) -> list[str]:
        consulted = self.governance.raci[activity].get("consulted", [])
        return consulted if isinstance(consulted, list) else [consulted]

    def needs_consensus(self, decision_type: str, vetoed: bool) -> bool:
        return vetoed

    def get_decider(self, decision_type: str) -> str:
        return self.governance.rapid[decision_type]["decide"]
