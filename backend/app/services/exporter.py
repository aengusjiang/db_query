"""Query result export formatting (CSV/JSON).

Pure functions only: no I/O, no session dependency. Reused by the export
API endpoint and available for future CLI tooling.
"""

import csv
import io
import json
import re
from datetime import UTC, datetime

from app.models.schemas import QueryResult

# UTF-8 BOM so Excel auto-detects the encoding (CJK-safe).
CSV_BOM = "﻿"

# OWASP CSV injection guidance: prefix these leading characters in string cells.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9_-]")


def _sanitize_cell(value: object) -> object:
    """Guard against CSV formula injection by prefixing a single quote.

    Only string values are treated: numeric cells (e.g. a genuine -5) keep
    their native type so the exported number stays usable in spreadsheets.
    """
    if isinstance(value, str) and value.startswith(_FORMULA_PREFIXES):
        return f"'{value}"
    return value


def result_to_csv(result: QueryResult) -> str:
    """Serialize a QueryResult to RFC 4180 CSV with a UTF-8 BOM.

    JSON exports are intentionally NOT sanitized: JSON has no formula
    execution semantics, so values must stay verbatim for downstream tools.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL)  # default \r\n terminator
    writer.writerow([_sanitize_cell(column.name) for column in result.columns])
    for row in result.rows:
        writer.writerow(
            [_sanitize_cell(row.get(column.name, "")) for column in result.columns]
        )
    return CSV_BOM + buffer.getvalue()


def result_to_json(result: QueryResult) -> str:
    """Serialize QueryResult rows to pretty-printed JSON.

    ``ensure_ascii=False`` keeps CJK text readable; ``default=str`` is a
    safety net for datetime/Decimal values an adapter might leak through.
    """
    return json.dumps(result.rows, ensure_ascii=False, indent=2, default=str)


def sanitize_filename(database_name: str) -> str:
    """Reduce a connection name to a filesystem-safe token."""
    token = _FILENAME_SAFE.sub("", database_name)
    return token or "export"


def build_export_filename(database_name: str, fmt: str) -> str:
    """Build '<name>_<UTC timestamp>.<ext>', e.g. 'test_db_20260814T093000.csv'."""
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{sanitize_filename(database_name)}_{timestamp}.{fmt}"
