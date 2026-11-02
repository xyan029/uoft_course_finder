"""Parse course entries out of a calendar search-results page.

All three calendars run the same Drupal "views" theme, so one parser serves
every campus. Each course on a results page looks like::

    <div class="views-row">
      <h3 class="js-views-accordion-group-header">
        <div aria-label="CSC108H1 - Introduction to Computer Programming">
          CSC108H1 - Introduction to Computer Programming
        </div>
      </h3>
      <div class="views-row">
        <div class="views-field views-field-body"> ...description... </div>
        <span class="views-field views-field-field-prerequisite">
          <strong class="views-label">Prerequisite: </strong>
          <span class="field-content">...</span>
        </span>
        ...
      </div>
    </div>

The parser is deliberately tolerant: it keys off the heading class and the
``views-field-*`` class names rather than exact tag nesting, and only raises
:class:`ParseError` when a page has none of the landmarks we expect, which is
the signal that the site layout changed.
"""

from __future__ import annotations

import html
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from .calendars import Calendar
from .models import Course

COURSE_CODE_RE = re.compile(r"\b[A-Z]{3}[A-Z0-9]\d{2}[HY]\d\b")
HEADING_RE = re.compile(
    r"<h3\b[^>]*\bclass=\"[^\"]*js-views-accordion-group-header[^\"]*\"[^>]*>"
    r"(?P<inner>.*?)</h3>",
    re.IGNORECASE | re.DOTALL,
)
ARIA_LABEL_RE = re.compile(r"aria-label=\"(?P<label>[^\"]*)\"", re.IGNORECASE)
FIELD_RE = re.compile(r"class=\"views-field views-field-(?P<name>[\w-]+)\"")
LABEL_RE = re.compile(
    r"<strong\b[^>]*\bclass=\"[^\"]*views-label[^\"]*\"[^>]*>(?P<label>.*?)</strong>",
    re.IGNORECASE | re.DOTALL,
)
HREF_RE = re.compile(r"href=\"(?P<href>[^\"]*)\"", re.IGNORECASE)
NEXT_LINK_RE = re.compile(r"<a\b[^>]*\brel=\"next\"[^>]*>", re.IGNORECASE)
BODY_END_RE = re.compile(r"<(?:nav|footer)\b", re.IGNORECASE)
HEADING_SEPARATORS = ("-", "\u2022", "\u2013", "\u2014", "|", ":")  # - bullet en/em dash

# Field names (minus the ``field-`` prefix) that hold the course description.
DESCRIPTION_FIELDS = frozenset({"body", "desc", "description"})
# Field names that never carry useful text.
IGNORED_FIELDS = frozenset({"nothing", "nothing-1", "nothing-2"})

LANDMARKS = ("view-content", "view-empty", "views-exposed-form", "views-row")


class ParseError(Exception):
    """The page did not look like a calendar search-results page."""


def strip_tags(fragment: str) -> str:
    """Convert an HTML fragment to whitespace-normalised plain text."""
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", fragment)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def normalize(text: str) -> str:
    """Collapse all whitespace in ``text`` to single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def split_heading(text: str) -> Tuple[str, str]:
    """Split ``"CSC108H1 - Introduction to ..."`` into ``(code, title)``.

    Returns an empty code when no course code is present.
    """
    text = normalize(html.unescape(text))
    match = COURSE_CODE_RE.search(text)
    if not match:
        return "", text
    code = match.group(0)
    title = normalize(text[: match.start()] + " " + text[match.end() :])
    while title and title[0] in HEADING_SEPARATORS:
        title = title[1:].lstrip()
    return code, title


def _parse_heading(inner: str) -> Tuple[str, str]:
    """Prefer the visible heading text, fall back to the aria-label.

    The calendars occasionally emit a truncated ``aria-label`` (titles that
    contain a colon lose everything before it), so the visible text wins.
    """
    code, title = split_heading(strip_tags(inner))
    if code:
        return code, title
    aria = ARIA_LABEL_RE.search(inner)
    if aria:
        code, aria_title = split_heading(aria.group("label"))
        if code:
            return code, aria_title or title
    return "", title


def _parse_fields(body: str) -> Tuple[str, Dict[str, str]]:
    """Return ``(description, details)`` for one course body."""
    description_parts: List[str] = []
    details: Dict[str, str] = {}
    matches = list(FIELD_RE.finditer(body))
    for index, match in enumerate(matches):
        # The class attribute sits inside an opening tag: start the segment
        # after that tag closes and stop before the tag holding the next field.
        start = body.find(">", match.end())
        start = len(body) if start == -1 else start + 1
        if index + 1 < len(matches):
            end = body.rfind("<", 0, matches[index + 1].start())
        else:
            end = len(body)
        segment = body[start:end] if end > start else ""
        name = match.group("name")
        if name.startswith("field-"):
            name = name[len("field-") :]
        if name in IGNORED_FIELDS:
            continue

        label_match = LABEL_RE.search(segment)
        label = ""
        if label_match:
            label = strip_tags(label_match.group("label")).rstrip(": ").strip()
            segment = segment[: label_match.start()] + segment[label_match.end() :]

        if name in DESCRIPTION_FIELDS:
            text = strip_tags(segment)
            if text:
                description_parts.append(text)
            continue

        if name == "timetable-link":
            href = HREF_RE.search(segment)
            value = href.group("href").strip() if href else strip_tags(segment)
            key = label or "Timetable"
        else:
            value = normalize(strip_tags(segment))
            key = label or name.replace("-", " ").strip().title()

        if value:
            details[key] = value
    return "\n\n".join(description_parts), details


def parse_results(page_html: str, calendar: Calendar) -> List[Course]:
    """Extract every course listed on one search-results page."""
    if not any(landmark in page_html for landmark in LANDMARKS):
        raise ParseError(
            f"{calendar.name} search page has an unexpected layout "
            "(no course list, empty-result marker or search form found); "
            "the calendar site may have changed"
        )

    courses: List[Course] = []
    headings = list(HEADING_RE.finditer(page_html))
    for index, heading in enumerate(headings):
        code, title = _parse_heading(heading.group("inner"))
        if not code:
            # Not a course heading (e.g. a sidebar block that shares the class).
            continue
        body_end = headings[index + 1].start() if index + 1 < len(headings) else len(page_html)
        body = page_html[heading.end() : body_end]
        cutoff = BODY_END_RE.search(body)
        if cutoff:
            body = body[: cutoff.start()]
        description, details = _parse_fields(body)
        courses.append(
            Course(
                campus=calendar.key,
                code=code,
                title=title,
                url=f"{calendar.base_url}/course/{code}",
                description=description,
                details=details,
            )
        )
    return courses


def find_next_page(page_html: str, current_url: str) -> Optional[str]:
    """Return the absolute URL of the next results page, if there is one."""
    link = NEXT_LINK_RE.search(page_html)
    if not link:
        return None
    href = HREF_RE.search(link.group(0))
    if not href:
        return None
    return urljoin(current_url, html.unescape(href.group("href")))
