# U of T Course Finder

Search the three official University of Toronto academic calendars by keyword
from the command line and get the matching courses as a table, JSON or CSV.

- UTSG Faculty of Arts & Science: <https://artsci.calendar.utoronto.ca/search-courses>
- UTM: <https://utm.calendar.utoronto.ca/course-search>
- UTSC: <https://utsc.calendar.utoronto.ca/search-courses>

The tool uses only the Python standard library at runtime (Python 3.9+), so it
has no dependencies to install.

## Installation

```bash
pipx install git+https://github.com/xyan029/uoft_course_finder   # isolated, recommended
# or
pip install git+https://github.com/xyan029/uoft_course_finder
```

Both give you a `uoft-course-finder` command. You can also run it without
installing anything: clone the repository and use `python3 uoft_course_finder.py`
(or `python3 -m uoft_course_finder`) from the checkout.

## Usage

```
uoft-course-finder [--campus CAMPUS] [-n N] [--format {table,json,csv}]
                   [--timeout SECONDS] [--max-pages N] [--allow-insecure-ssl]
                   keyword [keyword ...]
```

| Option | Meaning |
| --- | --- |
| `keyword` | Word or phrase to search for. Several words are joined into one phrase, so quoting is optional. |
| `--campus`, `-c` | `artsci`, `utm`, `utsc` or `all` (default). Repeat the flag to pick several. |
| `-n`, `--limit` | Show at most N courses after ranking across all campuses. |
| `--format`, `-f` | `table` (default), `json` or `csv`. |
| `--timeout` | Per-request timeout in seconds (default 30). |
| `--max-pages` | Follow at most N result pages per campus (default 5, 30 courses per page). |
| `--allow-insecure-ssl` | Skip TLS certificate verification. Only for machines whose Python cannot verify the U of T certificates. |

### Examples

```bash
uoft-course-finder algorithm
uoft-course-finder machine learning --campus artsci -n 5
uoft-course-finder "machine learning" -c utm -c utsc --format json
uoft-course-finder geography --format csv > geography.csv

# From a checkout, without installing:
python3 uoft_course_finder.py algorithm --allow-insecure-ssl
```

Results are ranked locally: a hit in the course code or title comes first,
then hits in the description, then everything else the calendar returned.
Nothing the calendar returned is dropped.

### Output formats

**table** prints one aligned line per course with the campus, code, title and
a shortened description.

**json** prints a list of objects with every field:

```json
{
  "campus": "utsc",
  "code": "CSCC11H3",
  "title": "Introduction to Machine Learning and Data Mining",
  "url": "https://utsc.calendar.utoronto.ca/course/CSCC11H3",
  "description": "An introduction to methods for automated learning ...",
  "details": {
    "Prerequisite": "[MATB23H3 or MATB24H3] and MATB41H3 and STAB52H3 ...",
    "Breadth Requirements": "Quantitative Reasoning",
    "Timetable": "https://ttb.utoronto.ca/cp/CSCC11H3"
  },
  "score": 70
}
```

`details` holds whatever labelled fields the calendar shows for the course
(prerequisites, exclusions, hours, breadth or distribution requirement, mode
of delivery, and so on). The labels differ slightly between campuses.

**csv** has the columns `campus, code, title, url, description, details, score`,
with `details` flattened to `Label: value | Label: value`.

### Exit status

| Code | Meaning |
| --- | --- |
| 0 | Every requested campus answered (even if no course matched). |
| 1 | Every requested campus failed; nothing was printed to stdout. |
| 2 | Usage error. |
| 3 | Some campuses failed. Their errors are on stderr; the others' results are on stdout. |

Each failing campus gets one line on stderr, for example
`error: UTM (utm): timed out fetching https://utm.calendar.utoronto.ca/...`.

## How the scrapers work

Each campus calendar is a Drupal site whose course search accepts a
`course_keyword` query parameter and renders results server-side, so no
JavaScript or API key is needed. For every campus the tool:

1. fetches `<search page>?course_keyword=<keyword>` with a `User-Agent`
   header and a timeout, retrying once on timeouts, connection errors and
   5xx/429 responses (`uoft_course_finder/httpclient.py`);
2. parses each `<h3 class="js-views-accordion-group-header">` heading into a
   course code and title, and each `views-field-*` block under it into the
   description or a labelled detail (`uoft_course_finder/parser.py`);
3. follows the `rel="next"` pager link up to `--max-pages` pages
   (`uoft_course_finder/scrapers.py`).

The three campuses are fetched concurrently and independently, so one site
being down never hides the others.

### When a calendar site changes

If a campus starts returning `search page has an unexpected layout`, or
courses come back with missing titles or details, the HTML has changed.

1. Run `make fixtures` (or `python3 scripts/refresh_fixtures.py`) to fetch
   fresh pages and rewrite the trimmed fixtures under `tests/fixtures/`.
   Review the diff to see what moved.
2. Adjust the regular expressions and field handling in
   `uoft_course_finder/parser.py` until `pytest tests/test_parser.py` passes
   against the new fixtures. The parser keys off class names rather than
   exact nesting, so small changes usually need no code change at all.
3. If the search form itself changed, update the URL or parameter name in
   `uoft_course_finder/calendars.py`.

## Development

```bash
git clone https://github.com/xyan029/uoft_course_finder
cd uoft_course_finder
make dev        # pip install -e ".[dev]"  (pytest + ruff)
make test       # offline pytest suite
make lint       # ruff check + ruff format --check
make check      # both, which is what CI runs
```

The test suite never touches the network: every HTTP call is replaced by the
trimmed real pages in `tests/fixtures/`. CI (`.github/workflows/ci.yml`) runs
ruff and the suite on Python 3.9 through 3.13.

Keep the runtime standard-library only. Development tools go in the `dev`
extra in `pyproject.toml`, never in `dependencies`.

## Layout

```
uoft_course_finder.py          thin shim so `python3 uoft_course_finder.py` keeps working
uoft_course_finder/
  cli.py                       argument parsing, exit codes, main()
  calendars.py                 the three campus sites and their search URLs
  httpclient.py                urllib wrapper: User-Agent, timeout, one retry
  parser.py                    HTML -> Course records
  scrapers.py                  per-campus search, pagination, concurrency
  matching.py                  keyword scoring and ranking
  formatters.py                table / json / csv
scripts/refresh_fixtures.py    regenerate tests/fixtures from the live sites
tests/                         offline pytest suite and fixtures
```
