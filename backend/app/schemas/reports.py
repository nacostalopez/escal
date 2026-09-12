from pydantic import BaseModel


class ReportPreferencesIn(BaseModel):
    enabled: bool = False


class ReportPreferencesOut(ReportPreferencesIn):
    pass


class SendReportNowOut(BaseModel):
    # The generated email body — "Enviar ahora" always sends/previews this,
    # regardless of the saved enabled toggle, so a merchant can see what the
    # weekly email looks like before committing to it.
    body: str
