"""Shared fixtures: offline HTML pages and a scripted fetcher."""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Union

import pytest

from uoft_course_finder.calendars import CALENDARS
from uoft_course_finder.httpclient import FetchError

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_fixture(name: str) -> str:
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(scope="session")
def pages() -> Dict[str, str]:
    """Trimmed real search-result pages keyed by campus, plus an empty one."""
    return {
        "artsci": load_fixture("artsci_search.html"),
        "utm": load_fixture("utm_search.html"),
        "utsc": load_fixture("utsc_search.html"),
        "empty": load_fixture("empty_search.html"),
    }


Response = Union[str, BaseException, Callable[[str], str]]


class FakeFetcher:
    """Stand-in for :func:`uoft_course_finder.httpclient.fetch`.

    ``routes`` maps a substring of the URL (usually the campus host) to the
    HTML to return, an exception to raise, or a callable producing the HTML.
    Every call is recorded in ``calls`` with its keyword arguments.
    """

    def __init__(self, routes: Dict[str, Response]) -> None:
        self.routes = routes
        self.calls: List[Dict[str, object]] = []

    def __call__(self, url: str, **kwargs: object) -> str:
        self.calls.append({"url": url, **kwargs})
        for needle, response in self.routes.items():
            if needle in url:
                if isinstance(response, BaseException):
                    raise response
                if callable(response):
                    return response(url)
                return response
        raise FetchError(f"no fake route for {url}")

    @property
    def urls(self) -> List[str]:
        return [str(call["url"]) for call in self.calls]


@pytest.fixture
def fake_fetcher(pages: Dict[str, str]) -> FakeFetcher:
    """A fetcher that serves each campus its fixture page (no pagination)."""
    artsci_page_one = pages["artsci"]
    # The Arts & Science fixture carries a real pager pointing at page=1.
    # Serve the empty page for page=1 so searches terminate after two hops.
    return FakeFetcher(
        {
            "page=1": pages["empty"],
            CALENDARS["artsci"].base_url: artsci_page_one,
            CALENDARS["utm"].base_url: pages["utm"],
            CALENDARS["utsc"].base_url: pages["utsc"],
        }
    )


@pytest.fixture
def patch_fetch(monkeypatch: pytest.MonkeyPatch) -> Callable[[FakeFetcher], FakeFetcher]:
    """Install a FakeFetcher as the module-level fetch used by the CLI."""

    def install(fetcher: FakeFetcher) -> FakeFetcher:
        monkeypatch.setattr("uoft_course_finder.httpclient.fetch", fetcher)
        return fetcher

    return install
