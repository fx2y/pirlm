from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIX = "utm_"


def normalize_url(url: str) -> str:
    split = urlsplit(url)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(split.query, keep_blank_values=True)
        if not key.lower().startswith(_TRACKING_PREFIX)
    ]
    query = urlencode(sorted(filtered_query), doseq=True)
    path = split.path or "/"
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, query, ""))


__all__ = ["normalize_url"]
