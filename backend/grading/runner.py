"""Adapters between Django models / the sandbox and the pure grading service."""

from __future__ import annotations

from typing import Optional, Sequence

from sandbox.services import execute_query, execute_sequence

from .service import (
    PURPOSE_STUDENT,
    CheckDataset,
    Execution,
    GradingTask,
    RunFn,
    SequenceRunFn,
)

PRIMARY_DATASET_NAME = 'основний'


def _to_execution(result) -> Execution:
    return Execution(
        success=bool(result.success),
        columns=list(result.columns or []),
        rows=[list(row) for row in (result.rows or [])],
        truncated=bool(result.truncated),
        affected_rows=int(result.affected_rows or 0),
        error=result.error_message or '',
        execution_time_ms=int(result.execution_time_ms or 0),
    )


def make_sequence_runner(db_type: str, timeout: int) -> SequenceRunFn:
    """Run a statement followed by state-inspection SELECTs on one sandbox."""

    def run_sequence(sqls, dataset: CheckDataset, purpose: str) -> list[Execution]:
        results = execute_sequence(
            database_type=db_type,
            queries=list(sqls),
            schema_sql=dataset.schema_sql,
            seed_sql=dataset.seed_sql,
            timeout=timeout,
        )
        return [_to_execution(r) for r in results]

    return run_sequence


def make_runner(
    db_type: str,
    timeout: int,
    *,
    user_id=None,
    submission_id=None,
    dataset_id=None,
) -> RunFn:
    """Execute SQL through the sandbox pool; attribute only the student's own run."""

    def run(sql: str, dataset: CheckDataset, purpose: str) -> Execution:
        is_student = purpose == PURPOSE_STUDENT
        response = execute_query(
            database_type=db_type,
            query=sql,
            schema_sql=dataset.schema_sql,
            seed_sql=dataset.seed_sql,
            timeout=timeout,
            user_id=user_id if is_student else None,
            submission_id=submission_id if is_student else None,
            dataset_id=dataset_id if is_student else None,
        )
        result = response.result
        if result is None:
            return Execution(
                success=False,
                error=response.error_message or 'Запит не виконався',
                execution_time_ms=response.execution_time_ms or 0,
            )
        return Execution(
            success=bool(response.success and result.success),
            columns=list(result.columns or []),
            rows=[list(row) for row in (result.rows or [])],
            truncated=bool(result.truncated),
            affected_rows=int(result.affected_rows or 0),
            error=response.error_message or result.error_message or '',
            execution_time_ms=int(result.execution_time_ms or response.execution_time_ms or 0),
        )

    return run


def build_task(
    db_type: str,
    *,
    reference_query: str,
    dataset,
    check_datasets: Optional[Sequence[dict]],
    required_keywords: Optional[Sequence[str]] = None,
    forbidden_keywords: Optional[Sequence[str]] = None,
    order_matters: bool = False,
    max_score: int = 100,
    query_type: str = 'select',
    expected_result: Optional[dict] = None,
    criteria: Optional[dict] = None,
) -> GradingTask:
    schema_sql = dataset.schema_sql if dataset else ''
    seed_sql = dataset.seed_sql if dataset else ''
    primary = CheckDataset(PRIMARY_DATASET_NAME, schema_sql, seed_sql)

    hidden = []
    for index, item in enumerate(check_datasets or []):
        if not isinstance(item, dict):
            continue
        hidden.append(CheckDataset(
            name=str(item.get('name') or f'контрольний {index + 1}'),
            schema_sql=str(item.get('schema_sql') or schema_sql),
            seed_sql=str(item.get('seed_sql') or ''),
            targets=str(item.get('targets') or ''),
        ))

    return GradingTask(
        db_type=db_type,
        reference_query=reference_query or '',
        primary=primary,
        hidden=hidden,
        required_keywords=list(required_keywords or []),
        forbidden_keywords=list(forbidden_keywords or []),
        order_matters=bool(order_matters),
        max_score=int(max_score or 100),
        query_type=query_type or 'select',
        expected_result=expected_result if isinstance(expected_result, dict) else None,
        criteria=criteria if isinstance(criteria, dict) else None,
    )
