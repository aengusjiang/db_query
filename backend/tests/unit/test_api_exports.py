"""Unit tests for query result export API endpoint and exporter helpers."""

import re
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app
from app.models.database import ConnectionStatus, DatabaseConnection
from app.models.query import QuerySource
from app.models.schemas import QueryColumn, QueryResult
from app.services.exporter import (
    build_export_filename,
    result_to_csv,
    result_to_json,
    sanitize_filename,
)
from app.services.sql_validator import SqlValidationError


@pytest.fixture
def test_session():
    """Create an in-memory SQLite session for testing."""

    engine = create_engine(
        "sqlite:///file:test_export_db?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False, "uri": True},
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(test_session):
    """Create TestClient with test database session."""

    def get_test_session():
        return test_session

    app.dependency_overrides[get_session] = get_test_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_connection(test_session):
    """Create a sample database connection."""
    conn = DatabaseConnection(
        name="test_db",
        url="postgresql://user:pass@localhost/testdb",
        description="Test database",
        status=ConnectionStatus.ACTIVE,
        last_connected_at=datetime.now(UTC).replace(tzinfo=None),
    )
    test_session.add(conn)
    test_session.commit()
    test_session.refresh(conn)
    return conn


def make_result(columns=None, rows=None) -> QueryResult:
    """Build a QueryResult with sensible defaults."""
    return QueryResult(
        columns=columns or [QueryColumn(name="id", dataType="integer")],
        rows=rows if rows is not None else [{"id": 1}, {"id": 2}],
        rowCount=len(rows) if rows is not None else 2,
        executionTimeMs=12,
        sql="SELECT id FROM users",
    )


class TestExportCsv:
    """CSV export via POST /{name}/export."""

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_csv_success(self, mock_execute, client, sample_connection):
        """Successful export returns text/csv attachment with BOM."""
        mock_execute.return_value = make_result(
            columns=[
                QueryColumn(name="id", dataType="integer"),
                QueryColumn(name="name", dataType="character varying"),
            ],
            rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        )

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT id, name FROM users", "format": "csv"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["x-row-count"] == "2"
        # UTF-8 BOM so Excel opens CJK text without mojibake
        assert response.content.startswith(b"\xef\xbb\xbf")
        lines = response.text.splitlines()
        assert lines[0] == "﻿id,name"  # BOM + header row
        assert "Alice" in lines[1]

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_csv_escapes_special_characters(self, mock_execute, client, sample_connection):
        """Commas, quotes and newlines are escaped per RFC 4180."""
        mock_execute.return_value = make_result(
            columns=[QueryColumn(name="note", dataType="text")],
            rows=[{"note": 'has "quotes", commas\nand newline'}],
        )

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT note FROM t", "format": "csv"},
        )

        assert response.status_code == 200
        body = response.text.lstrip("﻿")
        assert '"has ""quotes"", commas' in body
        assert 'and newline"' in body

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_csv_formula_injection_guard(self, mock_execute, client, sample_connection):
        """Formula-looking strings get a quote prefix; numbers stay untouched."""
        mock_execute.return_value = make_result(
            columns=[
                QueryColumn(name="formula", dataType="text"),
                QueryColumn(name="delta", dataType="integer"),
            ],
            rows=[{"formula": "=SUM(A1:A9)", "delta": -5}],
        )

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT formula, delta FROM t", "format": "csv"},
        )

        assert response.status_code == 200
        body = response.text.lstrip("﻿")
        assert "'=SUM(A1:A9)" in body  # string cell sanitized
        assert ",-5" in body  # numeric cell untouched

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_csv_chinese_preserved(self, mock_execute, client, sample_connection):
        """CJK cell values round-trip verbatim."""
        mock_execute.return_value = make_result(
            columns=[QueryColumn(name="姓名", dataType="character varying")],
            rows=[{"姓名": "张伟"}],
        )

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT 姓名 FROM employees", "format": "csv"},
        )

        assert response.status_code == 200
        assert "张伟" in response.text


class TestExportJson:
    """JSON export via POST /{name}/export."""

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_json_success(self, mock_execute, client, sample_connection):
        """Successful export returns application/json rows without BOM."""
        mock_execute.return_value = make_result(
            columns=[QueryColumn(name="name", dataType="text")],
            rows=[{"name": "张伟"}, {"name": "王芳"}],
        )

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT name FROM employees", "format": "json"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["content-disposition"].startswith("attachment;")
        assert response.headers["x-row-count"] == "2"
        assert not response.content.startswith(b"\xef\xbb\xbf")
        assert response.json() == [{"name": "张伟"}, {"name": "王芳"}]

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_empty_result(self, mock_execute, client, sample_connection):
        """Empty result set: CSV keeps the header row, JSON is an empty list."""
        mock_execute.return_value = make_result(
            columns=[QueryColumn(name="id", dataType="integer")],
            rows=[],
        )

        csv_response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT id FROM t WHERE 1=0", "format": "csv"},
        )
        json_response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT id FROM t WHERE 1=0", "format": "json"},
        )

        assert csv_response.status_code == 200
        assert csv_response.text == "﻿id\r\n"
        assert json_response.status_code == 200
        assert json_response.json() == []


class TestExportErrors:
    """Error handling of the export endpoint."""

    def test_export_connection_not_found(self, client):
        """Unknown connection yields 404."""
        response = client.post(
            "/api/v1/dbs/nonexistent/export",
            json={"sql": "SELECT 1", "format": "csv"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_sql_validation_error(self, mock_execute, client, sample_connection):
        """Non-SELECT SQL yields 400."""
        mock_execute.side_effect = SqlValidationError("Only SELECT queries are allowed")

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "DELETE FROM users", "format": "csv"},
        )

        assert response.status_code == 400
        assert "Only SELECT" in response.json()["detail"]

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_execution_error(self, mock_execute, client, sample_connection):
        """Execution failure yields 500."""
        mock_execute.side_effect = Exception("Table does not exist")

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT * FROM invalid_table", "format": "csv"},
        )

        assert response.status_code == 500
        assert "Query execution failed" in response.json()["detail"]

    def test_export_invalid_format(self, client, sample_connection):
        """Unsupported format yields 422 from Pydantic validation."""
        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT 1", "format": "xlsx"},
        )

        assert response.status_code == 422

    def test_export_missing_fields(self, client, sample_connection):
        """Missing sql or format yields 422."""
        assert (
            client.post("/api/v1/dbs/test_db/export", json={"format": "csv"}).status_code
            == 422
        )
        assert (
            client.post("/api/v1/dbs/test_db/export", json={"sql": "SELECT 1"}).status_code
            == 422
        )


class TestExportPipelineReuse:
    """The export endpoint must reuse the standard query pipeline."""

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_calls_pipeline_with_six_args(self, mock_execute, client, sample_connection):
        """Export delegates to execute_query_with_service with the 6-arg signature."""
        mock_execute.return_value = make_result()

        client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT id FROM users", "format": "csv"},
        )

        mock_execute.assert_called_once()
        call_args = mock_execute.call_args[0]  # Positional args
        # Args: session, database_name, db_type, url, sql, query_source
        assert call_args[1] == "test_db"
        assert call_args[2] == sample_connection.db_type
        assert call_args[3] == "postgresql://user:pass@localhost/testdb"
        assert call_args[4] == "SELECT id FROM users"
        assert call_args[5] == QuerySource.MANUAL

    @patch("app.api.v1.queries.execute_query_with_service")
    def test_export_filename_in_content_disposition(self, mock_execute, client, sample_connection):
        """Filename follows <name>_<timestamp>.<ext> with unsafe chars stripped."""
        mock_execute.return_value = make_result()

        response = client.post(
            "/api/v1/dbs/test_db/export",
            json={"sql": "SELECT id FROM users", "format": "csv"},
        )

        disposition = response.headers["content-disposition"]
        match = re.search(r'filename="(.+)"', disposition)
        assert match is not None
        assert re.fullmatch(r"test_db_\d{8}T\d{6}\.csv", match.group(1))


class TestExporterHelpers:
    """Direct unit tests for the pure export functions."""

    def test_result_to_csv_prepends_bom(self):
        result = make_result()
        assert result_to_csv(result).startswith("﻿")

    def test_result_to_csv_sanitizes_headers(self):
        """Header names are formula-guarded like data cells."""
        result = make_result(
            columns=[QueryColumn(name="=HYPERLINK(x)", dataType="text")],
            rows=[{"=HYPERLINK(x)": "v"}],
        )
        assert result_to_csv(result).splitlines()[0] == "﻿'=HYPERLINK(x)"

    def test_result_to_json_is_pretty_and_cjk_safe(self):
        result = make_result(
            columns=[QueryColumn(name="name", dataType="text")],
            rows=[{"name": "张伟"}],
        )
        text = result_to_json(result)
        assert '"张伟"' in text  # ensure_ascii=False
        assert "\n" in text  # indent=2

    def test_sanitize_filename_strips_unsafe_chars(self):
        assert sanitize_filename("interview-db") == "interview-db"
        assert sanitize_filename("test_db") == "test_db"
        assert sanitize_filename("my db/../evil") == "mydbevil"

    def test_sanitize_filename_fallback_when_empty(self):
        assert sanitize_filename("///") == "export"
        assert sanitize_filename("数据") == "export"  # CJK stripped -> fallback

    def test_build_export_filename_format(self):
        filename = build_export_filename("sample hr", "json")
        assert re.fullmatch(r"samplehr_\d{8}T\d{6}\.json", filename)
