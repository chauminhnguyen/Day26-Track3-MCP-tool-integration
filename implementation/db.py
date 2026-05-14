from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


class SQLiteAdapter:
    """Safe database adapter for tool-backed SQLite queries."""

    SUPPORTED_OPERATORS = {
        "eq": "=",
        "ne": "!=",
        "gt": ">",
        "gte": ">=",
        "lt": "<",
        "lte": "<=",
        "like": "LIKE",
        "in": "IN",
    }
    SUPPORTED_METRICS = {"count", "avg", "sum", "min", "max"}

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        table_name = self._validated_table_name(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_ident(table_name)})").fetchall()
        return [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "default": row["dflt_value"],
                "pk": bool(row["pk"]),
            }
            for row in rows
        ]

    def get_database_schema(self) -> dict[str, list[dict[str, Any]]]:
        return {table: self.get_table_schema(table) for table in self.list_tables()}

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table_name = self._validated_table_name(table)
        known_columns = self._table_columns(table_name)
        selected_columns = columns or sorted(known_columns)
        for column in selected_columns:
            self._validated_column_name(table_name, column)
        if limit <= 0:
            raise ValidationError("limit must be greater than 0")
        if limit > 100:
            raise ValidationError("limit cannot be greater than 100")
        if offset < 0:
            raise ValidationError("offset cannot be negative")

        where_sql, where_params = self._build_filters(table_name, filters)
        order_sql = ""
        if order_by is not None:
            self._validated_column_name(table_name, order_by)
            direction = "DESC" if descending else "ASC"
            order_sql = f" ORDER BY {self._quote_ident(order_by)} {direction}"

        column_sql = ", ".join(self._quote_ident(c) for c in selected_columns)
        sql = (
            f"SELECT {column_sql} FROM {self._quote_ident(table_name)}"
            f"{where_sql}{order_sql} LIMIT ? OFFSET ?"
        )
        params = [*where_params, limit, offset]
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            "table": table_name,
            "columns": selected_columns,
            "row_count": len(rows),
            "limit": limit,
            "offset": offset,
            "rows": [dict(row) for row in rows],
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table_name = self._validated_table_name(table)
        if not values:
            raise ValidationError("values cannot be empty")

        for column in values:
            self._validated_column_name(table_name, column)

        columns = list(values.keys())
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"INSERT INTO {self._quote_ident(table_name)} "
            f"({', '.join(self._quote_ident(c) for c in columns)}) VALUES ({placeholders})"
        )
        with self.connect() as conn:
            cursor = conn.execute(sql, [values[c] for c in columns])
            conn.commit()
            inserted_id = cursor.lastrowid

        payload = dict(values)
        if inserted_id is not None:
            payload["id"] = inserted_id
        return {"table": table_name, "inserted": payload}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict[str, Any]] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        table_name = self._validated_table_name(table)
        metric_name = metric.lower()
        if metric_name not in self.SUPPORTED_METRICS:
            raise ValidationError(
                f"unsupported metric '{metric}'. Use one of: {sorted(self.SUPPORTED_METRICS)}"
            )

        if metric_name == "count":
            metric_expr = "COUNT(*)"
            source_column = "*"
        else:
            if not column:
                raise ValidationError(f"metric '{metric_name}' requires a column")
            self._validated_column_name(table_name, column)
            metric_expr = f"{metric_name.upper()}({self._quote_ident(column)})"
            source_column = column

        where_sql, where_params = self._build_filters(table_name, filters)
        group_sql = ""
        select_prefix = ""
        if group_by is not None:
            self._validated_column_name(table_name, group_by)
            quoted_group = self._quote_ident(group_by)
            select_prefix = f"{quoted_group} AS group_key, "
            group_sql = f" GROUP BY {quoted_group}"

        sql = (
            f"SELECT {select_prefix}{metric_expr} AS value "
            f"FROM {self._quote_ident(table_name)}{where_sql}{group_sql}"
        )
        with self.connect() as conn:
            rows = conn.execute(sql, where_params).fetchall()

        return {
            "table": table_name,
            "metric": metric_name,
            "column": source_column,
            "group_by": group_by,
            "rows": [dict(row) for row in rows],
        }

    def _validated_table_name(self, table: str) -> str:
        if table not in self.list_tables():
            raise ValidationError(f"unknown table '{table}'")
        return table

    def _table_columns(self, table: str) -> set[str]:
        return {col["name"] for col in self.get_table_schema(table)}

    def _validated_column_name(self, table: str, column: str) -> str:
        if column not in self._table_columns(table):
            raise ValidationError(f"unknown column '{column}' in table '{table}'")
        return column

    def _build_filters(
        self,
        table: str,
        filters: list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any]]:
        if not filters:
            return "", []

        clauses: list[str] = []
        params: list[Any] = []
        for index, condition in enumerate(filters, start=1):
            if not isinstance(condition, dict):
                raise ValidationError(f"filter #{index} must be an object")
            if "column" not in condition or "value" not in condition:
                raise ValidationError(
                    f"filter #{index} must include 'column' and 'value'"
                )
            column = str(condition["column"])
            operator_key = str(condition.get("op", "eq")).lower()
            value = condition["value"]

            self._validated_column_name(table, column)
            if operator_key not in self.SUPPORTED_OPERATORS:
                raise ValidationError(
                    f"unsupported operator '{operator_key}' in filter #{index}"
                )

            sql_operator = self.SUPPORTED_OPERATORS[operator_key]
            quoted_column = self._quote_ident(column)
            if operator_key == "in":
                if not isinstance(value, list) or len(value) == 0:
                    raise ValidationError(
                        f"filter #{index} with 'in' operator needs a non-empty list value"
                    )
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{quoted_column} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{quoted_column} {sql_operator} ?")
                params.append(value)

        return " WHERE " + " AND ".join(clauses), params

    @staticmethod
    def _quote_ident(identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
