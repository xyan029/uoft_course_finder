# U of T Course Finder

Find courses from the official University of Toronto Academic Calendar by a content keyword.

Examples:

```bash
python3 uoft_course_finder.py algorithm
python3 uoft_course_finder.py "machine learning" --campus artsci -n 5
python3 uoft_course_finder.py algorithm --format json
python3 uoft_course_finder.py algorithm --format csv > courses.csv
```

If your local Python installation cannot verify the U of T site certificates, run:

```bash
python3 uoft_course_finder.py algorithm --allow-insecure-ssl
```

The script searches these official calendars:

- UTSG Faculty of Arts & Science: `https://artsci.calendar.utoronto.ca/search-courses`
- UTM: `https://utm.calendar.utoronto.ca/course-search`
- UTSC: `https://utsc.calendar.utoronto.ca/search-courses`

It uses only the Python standard library, so no package installation is required.
