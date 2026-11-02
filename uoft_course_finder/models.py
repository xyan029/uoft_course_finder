"""Data records shared by the scrapers, matcher and formatters."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class Course:
    """A single course entry scraped from a calendar search page."""

    campus: str
    code: str
    title: str
    url: str
    description: str
    details: Dict[str, str] = field(default_factory=dict)
    score: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def searchable_text(self) -> str:
        """All text of the course joined, used for keyword matching."""
        parts = [self.code, self.title, self.description]
        parts.extend(f"{key}: {value}" for key, value in self.details.items())
        return "\n".join(part for part in parts if part)


class CampusError(Exception):
    """Raised when one campus calendar could not be searched.

    ``campus`` is the calendar key (``artsci``, ``utm`` or ``utsc``) and
    ``__cause__`` carries the underlying network or parse exception when one
    exists.
    """

    def __init__(self, campus: str, message: str) -> None:
        super().__init__(message)
        self.campus = campus
        self.message = message

    def __str__(self) -> str:
        return f"{self.campus}: {self.message}"


@dataclass
class SearchResult:
    """Courses found plus any per-campus failures encountered on the way."""

    courses: List[Course] = field(default_factory=list)
    errors: List[CampusError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def partial(self) -> bool:
        return bool(self.errors) and bool(self.courses)
