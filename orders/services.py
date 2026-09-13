from .models import Order, OrderStatus

FULL_STATUS_SEQUENCE = [
    OrderStatus.DRAFT,
    OrderStatus.PENDING_PAYMENT,
    OrderStatus.CONFIRMED,
    OrderStatus.ROUTED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.ASSIGNED,
    OrderStatus.PICKED_UP,
    OrderStatus.DELIVERED,
]

TRACKED_STAGES = [
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.PICKED_UP,
    OrderStatus.DELIVERED,
]


def bottleneck_status(statuses: list[str]) -> str:
    """The least-advanced status among a batch's order lines, i.e. the status the whole batch has reached."""
    if OrderStatus.CANCELLED in statuses:
        return OrderStatus.CANCELLED
    indexed = [FULL_STATUS_SEQUENCE.index(s) for s in statuses if s in FULL_STATUS_SEQUENCE]
    if not indexed:
        return statuses[0]
    return FULL_STATUS_SEQUENCE[min(indexed)]


def batch_progression(orders: list[Order]):
    """Visitor-facing timeline for a batch: a stage is only 'completed' once every line has reached it."""
    per_order_dates = []
    for order in orders:
        dates = {}
        for record in order.history.order_by('history_date'):
            if record.status in TRACKED_STAGES and record.status not in dates:
                dates[record.status] = record.history_date
        per_order_dates.append(dates)

    progression = []
    overall_status = TRACKED_STAGES[0]
    for stage in TRACKED_STAGES:
        stage_dates = [d[stage] for d in per_order_dates if stage in d]
        completed = bool(orders) and len(stage_dates) == len(orders)
        progression.append({
            'status': stage,
            'timestamp': max(stage_dates) if completed else None,
            'completed': completed,
        })
        if completed:
            overall_status = stage
    return overall_status, progression
