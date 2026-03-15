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
