from __future__ import annotations

from database.monitoring import MonitoringSheetRepository
from product.monitoring import MonitoringSheetRow


class ForensicMonitoringSheetRepository(MonitoringSheetRepository):
    """Pass 6 public projection with the stored analyst takeaway on every feed row.

    The underlying monitoring repository remains the evidence source of truth. This
    projection is deliberately additive: it exposes the takeaway already persisted on
    AnalystRunRow and does not generate, rewrite or infer any new analysis.
    """

    def _build_row(self, *args, **kwargs) -> MonitoringSheetRow:  # type: ignore[no-untyped-def]
        row = super()._build_row(*args, **kwargs)
        run = kwargs.get("run")
        takeaway = " ".join(str(getattr(run, "takeaway", "") or "").strip().split())
        return row.model_copy(update={"takeaway": takeaway})
