from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

try:
    from .db import SQLiteAdapter, ValidationError
    from .init_db import DEFAULT_DB_PATH, create_database
except ImportError:
    from db import SQLiteAdapter, ValidationError
    from init_db import DEFAULT_DB_PATH, create_database


def create_server(db_path: str | Path = DEFAULT_DB_PATH) -> FastMCP:
    adapter = SQLiteAdapter(db_path)
    mcp = FastMCP("SQLite Lab MCP Server")

    @mcp.tool(name="search")
    def search(
        table: str,
        filters: list[dict[str, Any]] | None = None,
        columns: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        try:
            return adapter.search(
                table=table,
                columns=columns,
                filters=filters,
                limit=limit,
                offset=offset,
                order_by=order_by,
                descending=descending,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="insert")
    def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
        try:
            return adapter.insert(table=table, values=values)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.tool(name="aggregate")
    def aggregate(
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        try:
            return adapter.aggregate(
                table=table,
                metric=metric,
                column=column,
                filters=filters,
                group_by=group_by,
            )
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    @mcp.resource("schema://database", mime_type="application/json")
    def database_schema() -> str:
        return json.dumps(adapter.get_database_schema(), indent=2)

    @mcp.resource("schema://table/{table_name}", mime_type="application/json")
    def table_schema(table_name: str) -> str:
        try:
            payload = {
                "table": table_name,
                "columns": adapter.get_table_schema(table_name),
            }
            return json.dumps(payload, indent=2)
        except ValidationError as exc:
            raise ValueError(str(exc)) from exc

    return mcp


mcp = create_server()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SQLite FastMCP server.")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "sse", "streamable-http"],
        help="MCP transport mode.",
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="Path to SQLite database file.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for network transports.")
    parser.add_argument("--port", type=int, default=8000, help="Port for network transports.")
    parser.add_argument(
        "--no-reset-db",
        action="store_true",
        help="Keep existing database file without resetting seed data.",
    )
    args = parser.parse_args()

    create_database(args.db_path, reset=not args.no_reset_db)
    server = create_server(args.db_path)
    run_kwargs: dict[str, Any] = {}
    if args.transport != "stdio":
        run_kwargs.update({"host": args.host, "port": args.port})
    server.run(transport=args.transport, **run_kwargs)


if __name__ == "__main__":
    main()
