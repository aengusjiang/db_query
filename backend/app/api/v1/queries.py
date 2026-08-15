"""Query execution API endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.database import DatabaseConnection
from app.models.query import QueryHistory, QuerySource
from app.models.schemas import (
    ExportRequest,
    GeneratedSqlResponse,
    NaturalLanguageInput,
    QueryHistoryEntry,
    QueryInput,
    QueryResult,
)
from app.services.exporter import build_export_filename, result_to_csv, result_to_json
from app.services.metadata import get_cached_metadata
from app.services.nl2sql import nl2sql_service
from app.services.query import get_query_history
from app.services.query_wrapper import execute_query_with_service
from app.services.sql_validator import SqlValidationError

router = APIRouter(prefix="/api/v1/dbs", tags=["queries"])


def _get_connection_or_404(session: Session, name: str) -> DatabaseConnection:
    """Look up a database connection or raise 404.

    Args:
        session: Database session
        name: Database connection name

    Returns:
        The matching DatabaseConnection

    Raises:
        HTTPException: 404 if the connection does not exist
    """
    statement = select(DatabaseConnection).where(DatabaseConnection.name == name)
    connection = session.exec(statement).first()
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database connection '{name}' not found",
        )
    return connection


def to_history_entry(history: QueryHistory) -> QueryHistoryEntry:
    """Convert QueryHistory to QueryHistoryEntry schema."""
    assert history.id is not None  # persisted rows always have an id
    return QueryHistoryEntry(
        id=history.id,
        databaseName=history.database_name,
        sqlText=history.sql_text,
        executedAt=history.executed_at,
        executionTimeMs=history.execution_time_ms,
        rowCount=history.row_count,
        success=history.success,
        errorMessage=history.error_message,
        querySource=history.query_source.value,
    )


@router.post("/{name}/query", response_model=QueryResult)
async def execute_sql_query(
    name: str,
    input_data: QueryInput,
    session: Session = Depends(get_session),
) -> QueryResult:
    """
    Execute SQL query against a database.

    Args:
        name: Database connection name
        input_data: Query input with SQL
        session: Database session

    Returns:
        Query result with columns and rows
    """
    connection = _get_connection_or_404(session, name)

    # Execute query
    try:
        result = await execute_query_with_service(
            session,
            name,
            connection.db_type,
            connection.url,
            input_data.sql,
            QuerySource.MANUAL,
        )
        return result
    except SqlValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}",
        )


@router.post("/{name}/export")
async def export_query_result(
    name: str,
    input_data: ExportRequest,
    session: Session = Depends(get_session),
) -> Response:
    """
    Execute a query and return the result as a downloadable CSV/JSON file.

    Reuses the standard query pipeline (SELECT-only validation, auto LIMIT,
    query history), so an export also shows up in the connection's history.

    Args:
        name: Database connection name
        input_data: Export input with SQL and target format
        session: Database session

    Returns:
        File response with Content-Disposition attachment header

    Raises:
        HTTPException: 404 if connection not found, 400 on invalid SQL,
            500 on execution failure (422 on invalid format via Pydantic)
    """
    connection = _get_connection_or_404(session, name)

    # Execute query through the standard pipeline
    try:
        result = await execute_query_with_service(
            session,
            name,
            connection.db_type,
            connection.url,
            input_data.sql,
            QuerySource.MANUAL,
        )
    except SqlValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}",
        )

    # Format and return as a downloadable file
    if input_data.format == "csv":
        body = result_to_csv(result)
        media_type = "text/csv"
    else:
        body = result_to_json(result)
        media_type = "application/json"

    filename = build_export_filename(name, input_data.format)
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Row-Count": str(result.row_count),
        },
    )


@router.get("/{name}/history", response_model=list[QueryHistoryEntry])
async def get_query_history_for_database(
    name: str,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> list[QueryHistoryEntry]:
    """
    Get query history for a database.

    Args:
        name: Database connection name
        limit: Maximum number of queries to return
        session: Database session

    Returns:
        List of query history entries
    """
    _get_connection_or_404(session, name)

    # Get history
    history_list = await get_query_history(session, name, limit)
    return [to_history_entry(h) for h in history_list]


@router.post("/{name}/query/natural", response_model=GeneratedSqlResponse)
async def natural_language_to_sql(
    name: str,
    input_data: NaturalLanguageInput,
    session: Session = Depends(get_session),
) -> GeneratedSqlResponse:
    """
    Convert natural language to SQL query using OpenAI.

    Args:
        name: Database connection name
        input_data: Natural language prompt
        session: Database session

    Returns:
        Generated SQL query with explanation
    """
    connection = _get_connection_or_404(session, name)

    # Get metadata for context
    try:
        metadata_obj = await get_cached_metadata(session, connection.name)
        if not metadata_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Metadata not found for database '{name}'. Please refresh metadata first.",
            )
        metadata = json.loads(metadata_obj.metadata_json)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load metadata: {str(e)}",
        )

    # Generate SQL
    try:
        result = await nl2sql_service.generate_sql(input_data.prompt, metadata, connection.db_type)
        return GeneratedSqlResponse(
            sql=result["sql"],
            explanation=result["explanation"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate SQL: {str(e)}",
        )
