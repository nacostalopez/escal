"""Shared attribution-parsing helpers used by connectors that ingest orders."""


def extract_click_id(params: dict[str, str | None]) -> str | None:
    """Build a normalized click_id from platform-specific click identifiers.

    Checks Meta's fbclid before Google's gclid — an order can only realistically
    carry one ad click id, so the first one found wins.
    """
    if params.get("fbclid"):
        return f"fb:{params['fbclid']}"
    if params.get("gclid"):
        return f"g:{params['gclid']}"
    return None
