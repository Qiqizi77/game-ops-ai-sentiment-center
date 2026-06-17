from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from app.config import VERSIONS


VERSION_BY_ID = {item["version"]: item for item in VERSIONS}
VERSION_PATTERN = re.compile(r"(?:v|V|版本)?\s*([1-3]\.\d)")


def parse_date(value: str | datetime | date | None) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not value:
        return date.today()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()


def detect_game_version(text: str, publish_time: str | datetime | date | None = None) -> str:
    normalized = text or ""
    publish_date = parse_date(publish_time)
    explicit_versions = [match.group(1) for match in VERSION_PATTERN.finditer(normalized)]
    for version in explicit_versions:
        if version in VERSION_BY_ID:
            return version

    for item in sorted(VERSIONS, key=lambda item: item["release_date"], reverse=True):
        release_date = date.fromisoformat(item["release_date"])
        end_date = date.fromisoformat(item["end_date"])
        if release_date <= publish_date <= end_date:
            return item["version"]

    for item in sorted(VERSIONS, key=lambda item: item["release_date"]):
        release_date = date.fromisoformat(item["release_date"])
        if release_date - timedelta(days=7) <= publish_date < release_date:
            return item["version"]

    if publish_date > date.fromisoformat(VERSIONS[0]["end_date"]):
        return VERSIONS[0]["version"]
    return VERSIONS[-1]["version"]


def is_early_feedback(version: str, publish_time: str | datetime | date | None = None) -> bool:
    info = VERSION_BY_ID.get(version)
    if not info:
        return False
    publish_date = parse_date(publish_time)
    release_date = date.fromisoformat(info["release_date"])
    return 0 <= (publish_date - release_date).days <= 6


def days_since_release(version: str, at_date: date | None = None) -> int:
    info = VERSION_BY_ID.get(version)
    if not info:
        return 0
    at_date = at_date or date.today()
    return max((at_date - date.fromisoformat(info["release_date"])).days, 0)


def get_version_phase(version: str, publish_time: str | datetime | date | None = None) -> str:
    info = VERSION_BY_ID.get(version)
    if not info:
        return "稳定期"
    publish_date = parse_date(publish_time)
    release_date = date.fromisoformat(info["release_date"])
    delta = (publish_date - release_date).days
    if -7 <= delta < 0:
        return "预热期"
    if 0 <= delta <= 3:
        return "上线期"
    if 4 <= delta <= 14:
        return "稳定期"
    return "尾声期"


def get_version_days_remaining(version: str, at_date: date | None = None) -> int:
    info = VERSION_BY_ID.get(version)
    if not info:
        return 0
    at_date = at_date or date.today()
    end_date = date.fromisoformat(info["end_date"])
    return max((end_date - at_date).days, 0)


def get_version_duration_days(version: str) -> int:
    info = VERSION_BY_ID.get(version)
    if not info:
        return 0
    release_date = date.fromisoformat(info["release_date"])
    end_date = date.fromisoformat(info["end_date"])
    return max((end_date - release_date).days + 1, 0)


def day_index_since_release(version: str, publish_time: str | datetime | date | None) -> int:
    info = VERSION_BY_ID.get(version)
    if not info:
        return 0
    publish_date = parse_date(publish_time)
    release_date = date.fromisoformat(info["release_date"])
    return max((publish_date - release_date).days + 1, 1)
