import json
import uuid

import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql

from vecport.core.filters import validate_filter
from vecport.core.interface import VectorDatabase
from vecport.core.models import (
    Capabilities,
    SearchResult,
    VectorRecord,
)


class PgVectorDriver(VectorDatabase):

    def __init__(
        self,
        dsn: str = "postgresql://vecport:vecportpass@localhost:5432/vecport",
    ):
        self.conn = psycopg.connect(
            dsn,
            autocommit=True,
        )

        self.conn.execute(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )

        register_vector(self.conn)

    def create_collection(
        self,
        name: str,
        dimension: int,
    ) -> None:

        query = f"""
        CREATE TABLE IF NOT EXISTS "{name}" (
            id TEXT PRIMARY KEY,
            vector VECTOR({dimension}) NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{{}}'
        )
        """

        self.conn.execute(query)

    def delete_collection(
        self,
        name: str,
    ) -> None:

        self.conn.execute(
            f'DROP TABLE IF EXISTS "{name}"'
        )

    def upsert(
        self,
        collection: str,
        records: list[VectorRecord],
    ) -> None:

        query = f"""
        INSERT INTO "{collection}"
            (id, vector, metadata)
        VALUES
            (%s, %s, %s)
        ON CONFLICT (id)
        DO UPDATE SET
            vector = EXCLUDED.vector,
            metadata = EXCLUDED.metadata
        """

        for record in records:
            self.conn.execute(
                query,
                (
                    record.id,
                    record.vector,
                    json.dumps(record.metadata),
                ),
            )

    def get(
        self,
        collection: str,
        ids: list[str],
    ) -> list[VectorRecord]:

        results = []

        for record_id in ids:

            row = self.conn.execute(
                f"""
                SELECT id, vector, metadata
                FROM "{collection}"
                WHERE id = %s
                """,
                (record_id,),
            ).fetchone()

            if row is not None:

                vector_value = row[1]

                if hasattr(
                    vector_value,
                    "to_list",
                ):
                    vector_value = (
                        vector_value.to_list()
                    )
                else:
                    vector_value = list(
                        vector_value
                    )

                results.append(
                    VectorRecord(
                        id=str(row[0]),
                        vector=vector_value,
                        metadata=row[2] or {},
                    )
                )

        return results

    def delete(
        self,
        collection: str,
        ids: list[str],
    ) -> None:

        for record_id in ids:
            self.conn.execute(
                f"""
                DELETE FROM "{collection}"
                WHERE id = %s
                """,
                (record_id,),
            )

    def search(
        self,
        collection: str,
        vector: list[float],
        top_k: int = 10,
        filters: dict | None = None,
    ) -> list[SearchResult]:

        validate_filter(filters)

        where_sql, where_params = (
            self._build_filter(filters)
        )

        where_clause = (
            f"WHERE {where_sql}"
            if where_sql
            else ""
        )

        rows = self.conn.execute(
            f"""
            SELECT
                id,
                metadata,
                1 - (vector <=> %s::vector) AS score
            FROM "{collection}"
            {where_clause}
            ORDER BY vector <=> %s::vector
            LIMIT %s
            """,
            (
                vector,
                *where_params,
                vector,
                top_k,
            ),
        ).fetchall()

        return [
            SearchResult(
                id=str(row[0]),
                score=float(row[2]),
                metadata=row[1] or {},
            )
            for row in rows
        ]

    def capabilities(
        self,
    ) -> Capabilities:

        return Capabilities(
            dense_vector=True,
            metadata_filter=True,
            filter_operators=(
                "$eq",
                "$ne",
                "$gt",
                "$gte",
                "$lt",
                "$lte",
                "$in",
                "$and",
                "$or",
            ),
            sparse_vector=True,
            hybrid_search=True,
            namespaces=False,
            named_vectors=False,
        )
    
    def _build_filter(
        self,
        filters: dict | None,
    ):

        if not filters:
            return "", []

        clauses = []
        params = []

        for key, condition in filters.items():

            if key == "$and":

                child_clauses = []
                child_params = []

                for item in condition:

                    sql, values = self._build_filter(
                        item
                    )

                    child_clauses.append(
                        f"({sql})"
                    )

                    child_params.extend(
                        values
                    )

                return (
                    " AND ".join(child_clauses),
                    child_params,
                )

            if key == "$or":

                child_clauses = []
                child_params = []

                for item in condition:

                    sql, values = self._build_filter(
                        item
                    )

                    child_clauses.append(
                        f"({sql})"
                    )

                    child_params.extend(
                        values
                    )

                return (
                    " OR ".join(child_clauses),
                    child_params,
                )

            for operator, value in condition.items():

                if operator == "$eq":

                    clauses.append(
                        "(metadata ->> %s) = %s"
                    )

                    params.extend(
                        [
                            key,
                            str(value),
                        ]
                    )

                elif operator == "$ne":

                    clauses.append(
                        "(metadata ->> %s) != %s"
                    )

                    params.extend(
                        [
                            key,
                            str(value),
                        ]
                    )

                elif operator in {
                    "$gt",
                    "$gte",
                    "$lt",
                    "$lte",
                }:

                    sql_operator = {
                        "$gt": ">",
                        "$gte": ">=",
                        "$lt": "<",
                        "$lte": "<=",
                    }[operator]

                    clauses.append(
                        "(metadata ->> %s)::double precision "
                        + sql_operator
                        + " %s"
                    )

                    params.extend(
                        [
                            key,
                            value,
                        ]
                    )

                elif operator == "$in":

                    placeholders = ", ".join(
                        ["%s"] * len(value)
                    )

                    clauses.append(
                        f"(metadata ->> %s) IN ({placeholders})"
                    )

                    params.append(key)

                    params.extend(
                        str(item)
                        for item in value
                    )

                else:

                    raise ValueError(
                        f"Unsupported VecPort filter operator: {operator}"
                    )

        return (
            " AND ".join(clauses),
            params,
        )

    def scan(
        self,
        collection: str,
        *,
        batch_size: int = 100,
    ):
        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than 0"
            )

        cursor_name = (
            "vecport_scan_"
            + uuid.uuid4().hex
        )

        with self.conn.transaction(), self.conn.cursor(
            name=cursor_name
        ) as cursor:

            cursor.execute(
                sql.SQL(
                    """
                        SELECT
                            id,
                            vector,
                            metadata
                        FROM {}
                        ORDER BY id
                        """
                ).format(
                    sql.Identifier(
                        collection
                    )
                )
            )

            while True:

                rows = cursor.fetchmany(
                    batch_size
                )

                if not rows:
                    break

                for row in rows:

                    raw_vector = row[1]

                    if hasattr(
                        raw_vector,
                        "to_list",
                    ):
                        vector = (
                            raw_vector.to_list()
                        )

                    else:
                        vector = list(
                            raw_vector
                        )

                    yield VectorRecord(
                        id=str(row[0]),
                        vector=vector,
                        metadata=row[2] or {},
                    )