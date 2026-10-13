"""Small pure KPI helpers used by dashboards and reports."""

def precision(confirmed: int, proposed: int) -> float:
    return confirmed / proposed if proposed else 0.0


def reach(delivered: int, targeted: int) -> float:
    return delivered / targeted if targeted else 0.0
