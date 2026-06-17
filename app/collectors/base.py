from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Collector(ABC):
    platform: str
    platform_name: str

    @abstractmethod
    async def fetch(self, keyword: str = "绝区零") -> list[dict[str, Any]]:
        """Return raw posts. The analysis layer normalizes them later."""
