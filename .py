#!/usr/bin/env python3
"""Find University of Toronto Academic Calendar courses by content keyword."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import textwrap
from dataclasses import asdict, dataclass
from typing import Iterable
from urllib.error import URLError
from urllib.parse import urlencode, urljoin
import ssl
from urllib.request import Request, urlopen


CALENDARS = {
    "artsci": {
        "name": "UTSG Arts & Science",
        "base_url": "https://artsci.calendar.utoronto.ca",
        "search_path": "/search-courses",
    },
    "utm": {
        "name": "UTM",
        "base_url": "https://utm.calendar.utoronto.ca",
        "search_path": "/course-search",
    },
    "utsc": {
        "name": "UTSC",
        "base_url": "https://utsc.calendar.utoronto.ca",
        "search_path": "/search-courses",
    },
}


COURSE_CODE_RE = re.compile(r"\b[A-Z]{3,4}\d{2,3}[HY][135]\b")
HEADING_RE = re.compile(
    r"<h3\b[^>]*>\s*<div\b[^>]*aria-label=\"(?P<label>[^\"]+)\"[^>]*>.*?</div>\s*</h3>",
    re.IGNORECASE | re.DOTALL,
)

KEYWORD_ALIASES = {
    "algorithm": [
        ("data structures", 55),
        ("data structure", 55),
        ("complexity", 35),
        ("analysis", 25),
        ("abstract data types", 35),
    ],
    "algorithms": [
        ("data structures", 55),
        ("data structure", 55),
        ("complexity", 35),
        ("analysis", 25),
        ("abstract data types", 35),
    ],
    "ai": [("artificial intelligence", 80), ("machine learning", 35)],
    "nlp": [("natural language processing", 80), ("text", 15), ("language", 15)],
}


@dataclass
class Course:
    campus: str
    code: str
    title: str
    url: str
    description: str
    details: dict[str, str]
    score: int


def fetch(url: str, allow_insecure_ssl: bool = False) -> str:
    req = Request(url, headers={"User-Agent": "uoft-course-finder/1.0"})
    context = ssl._create_unverified_context() if allow_insecure_ssl else None
    with urlopen(req, timeout=30, context=context) as response:
        return response.read().decode("utf-8", errors="replace")


def strip_tags(fragment: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_heading(label: str) -> tuple[str, str]:
    label = normalize(html.unescape(label))
    match = COURSE_CODE_RE.search(label)
    if not match:
        return "", label
