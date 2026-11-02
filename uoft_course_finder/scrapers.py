"""Fetch and parse search results from each campus calendar."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, Optional

from . import httpclient as http
from .calendars import ALL_CAMPUSES, CALENDARS, Calendar
from .models import CampusError, Course, SearchResult
from .parser import ParseError, find_next_page, parse_results

Fetcher = Callable[..., str]

DEFAULT_MAX_PAGES = 5


def search_campus(
    calendar: Calendar,
    keyword: str,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = http.DEFAULT_TIMEOUT,
    allow_insecure_ssl: bool = False,
    fetcher: Optional[Fetcher] = None,
) -> List[Course]:
    """Return every course one calendar lists for ``keyword``.

    Follows "next page" links up to ``max_pages`` pages. Raises
    :class:`CampusError` if the site cannot be reached or its HTML no longer
    parses; the underlying exception is attached as ``__cause__``.
    """
    fetch = fetcher or http.fetch
    courses: List[Course] = []
    seen = set()
    url: Optional[str] = calendar.build_search_url(keyword)
    pages = 0
    while url and pages < max_pages:
        try:
            page = fetch(url, timeout=timeout, allow_insecure_ssl=allow_insecure_ssl)
        except http.FetchError as exc:
            raise CampusError(calendar.key, str(exc)) from exc
        try:
            found = parse_results(page, calendar)
        except ParseError as exc:
            raise CampusError(calendar.key, str(exc)) from exc
        for course in found:
            if course.code not in seen:
                seen.add(course.code)
                courses.append(course)
        pages += 1
        url = find_next_page(page, url)
    return courses


def resolve_campuses(campuses: Optional[Iterable[str]]) -> List[Calendar]:
    """Turn user-supplied campus keys (or ``None``/``"all"``) into calendars."""
    if not campuses:
        keys: List[str] = list(ALL_CAMPUSES)
    else:
        keys = []
        for raw_key in campuses:
            key = raw_key.lower()
            if key == "all":
                keys.extend(k for k in ALL_CAMPUSES if k not in keys)
            elif key not in CALENDARS:
                raise ValueError(
                    f"unknown campus {key!r}; choose from {', '.join(ALL_CAMPUSES)} or all"
                )
            elif key not in keys:
                keys.append(key)
    return [CALENDARS[key] for key in keys]


def search(
    keyword: str,
    campuses: Optional[Iterable[str]] = None,
    *,
    max_pages: int = DEFAULT_MAX_PAGES,
    timeout: float = http.DEFAULT_TIMEOUT,
    allow_insecure_ssl: bool = False,
    fetcher: Optional[Fetcher] = None,
) -> SearchResult:
    """Search one or more calendars; failures never hide other campuses.

    Campuses are fetched concurrently. The returned courses are in calendar
    order (unranked); use :func:`uoft_course_finder.matching.rank` to sort.
    """
    calendars = resolve_campuses(campuses)
    result = SearchResult()

    def run(calendar: Calendar) -> List[Course]:
        return search_campus(
            calendar,
            keyword,
            max_pages=max_pages,
            timeout=timeout,
            allow_insecure_ssl=allow_insecure_ssl,
            fetcher=fetcher,
        )

    with ThreadPoolExecutor(max_workers=max(1, len(calendars))) as pool:
        futures = [(calendar, pool.submit(run, calendar)) for calendar in calendars]
        for calendar, future in futures:
            try:
                result.courses.extend(future.result())
            except CampusError as exc:
                result.errors.append(exc)
            except Exception as exc:  # keep other campuses alive
                error = CampusError(calendar.key, f"unexpected error: {type(exc).__name__}: {exc}")
                error.__cause__ = exc
                result.errors.append(error)
    return result
