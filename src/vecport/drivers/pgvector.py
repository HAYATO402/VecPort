import json

import psycopg
from pgvector.psycopg import register_vector

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
    ) -> list[SearchResult]:

        rows = self.conn.execute(
            f"""
            SELECT
                id,
                metadata,
                1 - (vector <=> %s::vector) AS score
            FROM "{collection}"
            ORDER BY vector <=> %s::vector
            LIMIT %s
            """,
            (
                vector,
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
            sparse_vector=False,
            hybrid_search=False,
            namespaces=False,
            named_vectors=False,
        )