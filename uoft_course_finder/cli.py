"""Command-line entry point for ``uoft-course-finder``."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence, TextIO

from ._version import __version__
from .calendars import ALL_CAMPUSES, CALENDARS
from .formatters import FORMATS, format_courses
from .httpclient import DEFAULT_TIMEOUT
from .matching import rank
from .scrapers import DEFAULT_MAX_PAGES, resolve_campuses, search

EXIT_OK = 0
EXIT_ALL_FAILED = 1
EXIT_USAGE = 2
EXIT_PARTIAL = 3


def build_parser() -> argparse.ArgumentParser:
    campus_list = ", ".join(f"{key} ({cal.name})" for key, cal in CALENDARS.items())
    parser = argparse.ArgumentParser(
        prog="uoft-course-finder",
        description=(
            "Search the official University of Toronto academic calendars by "
            "keyword and print matching courses."
        ),
        epilog=(
            f"Campuses: {campus_list}. Exit status is {EXIT_OK} on success, "
            f"{EXIT_ALL_FAILED} if every campus failed, {EXIT_PARTIAL} if some "
            f"campuses failed, and {EXIT_USAGE} for a usage error."
        ),
    )
    parser.add_argument(
        "keyword",
        nargs="+",
        help="word or phrase to search for (several words are joined into one phrase)",
    )
    parser.add_argument(
        "--campus",
        "-c",
        action="append",
        choices=(*ALL_CAMPUSES, "all"),
        metavar="CAMPUS",
        help=("calendar to search: artsci, utm, utsc or all (default: all). May be repeated."),
    )
    parser.add_argument(
        "-n",
        "--limit",
        type=int,
        metavar="N",
        help="show at most N courses (after ranking across campuses)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=FORMATS,
        default="table",
        help="output format (default: table)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"per-request timeout in seconds (default: {DEFAULT_TIMEOUT:g})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        metavar="N",
        help=f"follow at most N result pages per campus (default: {DEFAULT_MAX_PAGES})",
    )
    parser.add_argument(
        "--allow-insecure-ssl",
        action="store_true",
        help=(
            "skip TLS certificate verification (only if your Python cannot verify "
            "U of T's certificates)"
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.keyword = " ".join(args.keyword).strip()
    if not args.keyword:
        parser.error("keyword must not be empty")
    if args.limit is not None and args.limit < 0:
        parser.error("-n/--limit must be zero or greater")
    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return args


def main(
    argv: Optional[Sequence[str]] = None,
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """Run the CLI and return the process exit status."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = parse_args(argv)

    result = search(
        args.keyword,
        args.campus,
        max_pages=args.max_pages,
        timeout=args.timeout,
        allow_insecure_ssl=args.allow_insecure_ssl,
    )

    for error in result.errors:
        calendar = CALENDARS.get(error.campus)
        name = calendar.name if calendar else error.campus
        print(f"error: {name} ({error.campus}): {error.message}", file=err)

    searched = {calendar.key for calendar in resolve_campuses(args.campus)}
    failed = {error.campus for error in result.errors}
    if failed and searched <= failed:
        print("error: every campus failed; no results available", file=err)
        return EXIT_ALL_FAILED

    courses = rank(result.courses, args.keyword, args.limit)
    if not courses and not result.errors:
        print(f"No courses found for {args.keyword!r}.", file=err)

    output = format_courses(courses, args.format)
    out.write(output)
    if output and not output.endswith("\n"):
        out.write("\n")
    out.flush()
    return EXIT_PARTIAL if result.errors else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
