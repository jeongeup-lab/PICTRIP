"""Tests for the sync_runs audit table (DDL + run lifecycle)."""


def test_ddl_is_idempotent() -> None:
    # TODO: run ensure_table twice against a test DB, assert no error + index exists.
    pass


def test_record_run_marks_terminal_status() -> None:
    # TODO: success path sets status='success'+finished_at; raise sets status='error'.
    pass
