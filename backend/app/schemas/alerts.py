from pydantic import BaseModel, Field


class AlertPreferencesIn(BaseModel):
    enabled: bool = False
    # None = no CAC alert configured — see StoreAlertPreference's docstring.
    cac_threshold: float | None = None
    roas_threshold: float = 1.0
    roas_days_n: int = Field(3, ge=1, le=14)


class AlertPreferencesOut(AlertPreferencesIn):
    pass


class AlertCheckResult(BaseModel):
    # Each entry is a human-readable description of one CAC alert fired
    # (e.g. "meta: CAC $42.00 > $30.00"), empty if none crossed threshold.
    cac_alerts_sent: list[str]
    roas_alert_sent: bool
