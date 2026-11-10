"""
Unit tests for PostgreSQL schema-based isolation.
"""

import pytest

from memable.backends.postgres import _add_schema_to_conn_string


class TestAddSchemaToConnString:
    """Tests for the schema helper function."""

    def test_simple_connection_string(self):
        """Test adding schema to a simple connection string."""
        conn = "postgresql://user:pass@host/db"
        result = _add_schema_to_conn_string(conn, "customer_123")

        assert "options=" in result
        assert "search_path" in result
        assert "customer_123" in result

    def test_connection_string_with_port(self):
        """Test adding schema to connection string with port."""
        conn = "postgresql://user:pass@host:5432/db"
        result = _add_schema_to_conn_string(conn, "tenant_abc")

        assert "options=" in result
        assert "search_path" in result
        assert "tenant_abc" in result
        assert ":5432" in result

    def test_connection_string_with_existing_params(self):
        """Test adding schema to connection string with existing query params."""
        conn = "postgresql://user:pass@host/db?sslmode=require"
        result = _add_schema_to_conn_string(conn, "schema_1")

        assert "sslmode=require" in result
        assert "search_path" in result
        assert "schema_1" in result

    def test_connection_string_with_existing_options(self):
        """Test merging with existing options parameter."""
        conn = "postgresql://user:pass@host/db?options=-c%20statement_timeout%3D5000"
        result = _add_schema_to_conn_string(conn, "my_schema")

        assert "search_path" in result
        assert "my_schema" in result
        # Should preserve existing option
        assert "statement_timeout" in result

    def test_schema_name_with_underscore(self):
        """Test schema names with underscores."""
        conn = "postgresql://user:pass@host/db"
        result = _add_schema_to_conn_string(conn, "customer_data_2024")

        assert "customer_data_2024" in result

    def test_libpq_reads_the_option_as_written(self):
        """libpq decodes %XX in a URI but keeps "+" literally, so a space
        encoded as "+" reaches Postgres as "-c+search_path=..." and the
        server rejects the unknown parameter "+search_path"."""
        from psycopg.conninfo import conninfo_to_dict

        conn = "postgresql://user:pass@host/db?sslmode=require"
        result = _add_schema_to_conn_string(conn, "mapping_memory")

        assert "+" not in result
        params = conninfo_to_dict(result)
        assert params["options"] == "-c search_path=mapping_memory"
        assert params["sslmode"] == "require"

    def test_existing_options_survive_as_libpq_reads_them(self):
        """Merging keeps the existing option and joins with a real space."""
        from psycopg.conninfo import conninfo_to_dict

        conn = "postgresql://user:pass@host/db?options=-c%20statement_timeout%3D5000"
        result = _add_schema_to_conn_string(conn, "my_schema")

        assert conninfo_to_dict(result)["options"] == (
            "-c statement_timeout=5000 -c search_path=my_schema"
        )

    def test_postgres_scheme(self):
        """Test with postgres:// (shorter alias) scheme."""
        conn = "postgres://user:pass@host/db"
        result = _add_schema_to_conn_string(conn, "tenant_1")

        assert result.startswith("postgres://")
        assert "search_path" in result
        assert "tenant_1" in result


class TestSchemaParameterIntegration:
    """Tests for schema parameter in build functions."""

    def test_build_store_accepts_schema_param(self):
        """Test that build_store accepts schema parameter (smoke test)."""
        from memable import build_store

        # Just verify the function accepts the parameter without error
        # We can't actually test PostgreSQL without a connection
        import inspect
        sig = inspect.signature(build_store)
        assert "schema" in sig.parameters

    def test_build_postgres_store_accepts_schema_param(self):
        """Test that build_postgres_store accepts schema parameter (smoke test)."""
        from memable import build_postgres_store

        import inspect
        sig = inspect.signature(build_postgres_store)
        assert "schema" in sig.parameters


class TestDirectEndpointRewrite:
    """Schema isolation rides on a `search_path` startup option, which
    transaction poolers refuse to forward. A pooled host must be rewritten to
    its direct equivalent before the option is applied."""

    def _direct(self, conn: str) -> str:
        from memable.backends.postgres import _to_direct_conn_string

        return _to_direct_conn_string(conn)

    def test_neon_pooler_host_rewritten(self):
        assert self._direct(
            "postgresql://u:p@ep-shy-hat-a43ca03l-pooler.us-east-1.aws.neon.tech/db"
        ) == "postgresql://u:p@ep-shy-hat-a43ca03l.us-east-1.aws.neon.tech/db"

    def test_port_and_query_preserved(self):
        assert self._direct(
            "postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech:5432/db?sslmode=require"
        ) == "postgresql://u:p@ep-x.us-east-1.aws.neon.tech:5432/db?sslmode=require"

    def test_encoded_credentials_preserved_verbatim(self):
        conn = "postgresql://user:p%40ss%2Fword@ep-x-pooler.us-east-1.aws.neon.tech/db"
        assert self._direct(conn) == (
            "postgresql://user:p%40ss%2Fword@ep-x.us-east-1.aws.neon.tech/db"
        )

    def test_direct_host_untouched(self):
        conn = "postgresql://u:p@ep-x.us-east-1.aws.neon.tech/db"
        assert self._direct(conn) == conn

    def test_ordinary_host_untouched(self):
        conn = "postgresql://u:p@localhost:5432/db"
        assert self._direct(conn) == conn

    def test_pooler_in_password_not_rewritten(self):
        conn = "postgresql://u:a-pooler.b@localhost:5432/db"
        assert self._direct(conn) == conn

    def test_non_url_conn_string_untouched(self):
        conn = "host=localhost dbname=db user=u"
        assert self._direct(conn) == conn


class TestPooledDetection:
    def _is_pooled(self, conn: str) -> bool:
        from memable.backends.postgres import _is_pooled_conn_string

        return _is_pooled_conn_string(conn)

    def test_detects_pooler_host(self):
        assert self._is_pooled(
            "postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/db"
        )

    def test_direct_host_is_not_pooled(self):
        assert not self._is_pooled("postgresql://u:p@ep-x.us-east-1.aws.neon.tech/db")

    def test_pooler_in_credentials_is_not_pooled(self):
        assert not self._is_pooled("postgresql://u:a-pooler.b@localhost/db")


class TestBackendRewritesPooledConnection:
    """The rewrite must happen only when `schema` is actually in play."""

    def _backend(self, conn: str, schema: str | None):
        from memable.backends.postgres import PostgresBackend

        return PostgresBackend(conn, embeddings=object(), schema=schema)

    def test_pooled_conn_with_schema_is_rewritten(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            backend = self._backend(
                "postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/db",
                "mapping_memory",
            )

        assert "-pooler." not in backend._conn_str
        assert "search_path" in backend._conn_str
        assert "direct" in caplog.text.lower()

    def test_pooled_conn_without_schema_is_left_alone(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            backend = self._backend(
                "postgresql://u:p@ep-x-pooler.us-east-1.aws.neon.tech/db", None
            )

        # No search_path option, so pooling is perfectly fine here.
        assert "-pooler." in backend._conn_str
        assert caplog.text == ""

    def test_direct_conn_with_schema_logs_nothing(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            self._backend(
                "postgresql://u:p@ep-x.us-east-1.aws.neon.tech/db", "mapping_memory"
            )

        assert caplog.text == ""


class TestUnrecognisedPoolerError:
    """A pooler we cannot spot by hostname still fails — but legibly."""

    def _backend_raising(self, monkeypatch, exc: Exception, schema: str | None):
        from memable.backends import postgres as pg

        def _boom(*_args, **_kwargs):
            raise exc

        monkeypatch.setattr(pg.PostgresStore, "from_conn_string", _boom)
        backend = pg.PostgresBackend(
            "postgresql://u:p@proxy.internal/db", embeddings=object(), schema=schema
        )
        return backend

    def test_startup_parameter_rejection_is_explained(self, monkeypatch):
        backend = self._backend_raising(
            monkeypatch,
            RuntimeError("unsupported startup parameter in options: search_path"),
            "mapping_memory",
        )
        with pytest.raises(ConnectionError) as excinfo:
            backend._ensure_connected()

        message = str(excinfo.value)
        assert "mapping_memory" in message
        assert "unpooled" in message
        # The original driver error stays reachable for debugging.
        assert isinstance(excinfo.value.__cause__, RuntimeError)

    def test_unrelated_connection_errors_pass_through(self, monkeypatch):
        backend = self._backend_raising(
            monkeypatch, RuntimeError("password authentication failed"), "s"
        )
        with pytest.raises(RuntimeError, match="password authentication failed"):
            backend._ensure_connected()

    def test_no_schema_means_no_rewriting_of_the_error(self, monkeypatch):
        backend = self._backend_raising(
            monkeypatch,
            RuntimeError("unsupported startup parameter in options: whatever"),
            None,
        )
        with pytest.raises(RuntimeError, match="unsupported startup parameter"):
            backend._ensure_connected()
