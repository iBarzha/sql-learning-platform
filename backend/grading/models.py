"""Grading service for evaluating SQL submissions."""

import re
from dataclasses import dataclass
from typing import Optional
from decimal import Decimal


@dataclass
class GradingResult:
    """Result of grading a submission."""
    score: Decimal
    max_score: int
    is_correct: bool
    feedback: dict

    @property
    def percentage(self) -> float:
        """Get score as percentage."""
        if self.max_score == 0:
            return 0.0
        return float(self.score / self.max_score * 100)


class GradingService:
    """
    Service for grading SQL query submissions.

    Supports multiple grading criteria:
    - Result comparison (exact or partial match)
    - Keyword validation (required/forbidden)
    - Row order sensitivity
    """

    def grade(
        self,
        student_result: dict,
        expected_result: Optional[dict],
        expected_query: str = '',
        required_keywords: list[str] = None,
        forbidden_keywords: list[str] = None,
        order_matters: bool = False,
        partial_match: bool = False,
        max_score: int = 100,
        student_query: str = '',
    ) -> GradingResult:
        """
        Grade a student's query submission.

        Args:
            student_result: Result from executing student's query
            expected_result: Expected query result (if any)
            expected_query: Expected SQL query (for reference grading)
            required_keywords: Keywords that must be in the query
            forbidden_keywords: Keywords that must not be in the query
            order_matters: Whether row order affects correctness
            partial_match: Allow partial result matches
            max_score: Maximum score for this submission
            student_query: The student's submitted query

        Returns:
            GradingResult with score and feedback
        """
        feedback = {
            'checks': [],
            'hints': [],
        }

        # If query execution failed, score is 0
        if not student_result.get('success', False):
            return GradingResult(
                score=Decimal('0'),
                max_score=max_score,
                is_correct=False,
                feedback={
                    'checks': [{'name': 'Execution', 'passed': False}],
                    'hints': ['Your query has an error. Check the error message.'],
                    'error': student_result.get('error_message', 'Query execution failed'),
                }
            )

        score_parts = []
        total_weight = 0

        # 1. Check forbidden keywords (20% weight)
        if forbidden_keywords:
            forbidden_check = self._check_forbidden_keywords(
                student_query, forbidden_keywords
            )
            score_parts.append((forbidden_check['score'], 20))
            total_weight += 20
            feedback['checks'].append({
                'name': 'Forbidden keywords',
                'passed': forbidden_check['passed'],
            })
            if not forbidden_check['passed']:
                feedback['hints'].append(
                    f"Avoid using: {', '.join(forbidden_check['found'])}"
                )

        # 2. Check required keywords (20% weight)
        if required_keywords:
            required_check = self._check_required_keywords(
                student_query, required_keywords
            )
            score_parts.append((required_check['score'], 20))
            total_weight += 20
            feedback['checks'].append({
                'name': 'Required keywords',
                'passed': required_check['passed'],
            })
            if not required_check['passed']:
                feedback['hints'].append(
                    f"Consider using: {', '.join(required_check['missing'])}"
                )

        # 3. Check result match (60% weight if expected_result provided)
        if expected_result:
            result_check = self._check_result_match(
                student_result,
                expected_result,
                order_matters=order_matters,
                partial_match=partial_match,
            )
            score_parts.append((result_check['score'], 60))
            total_weight += 60
            feedback['checks'].append({
                'name': 'Result match',
                'passed': result_check['passed'],
                'details': result_check.get('details'),
            })
            if not result_check['passed']:
                if result_check.get('column_mismatch'):
                    feedback['hints'].append('Check your column selection.')
                elif result_check.get('row_count_mismatch'):
                    feedback['hints'].append(
                        f"Expected {result_check['expected_rows']} rows, "
                        f"got {result_check['actual_rows']}."
                    )
                else:
                    feedback['hints'].append('Check your query results.')

        # Calculate weighted score
        if total_weight == 0:
            # No grading criteria - just check if query executed
            final_score = Decimal(str(max_score))
            is_correct = True
        else:
            weighted_sum = sum(score * weight for score, weight in score_parts)
            final_score = Decimal(str(round(weighted_sum / total_weight * max_score / 100, 2)))
            is_correct = all(check['passed'] for check in feedback['checks'])

        return GradingResult(
            score=final_score,
            max_score=max_score,
            is_correct=is_correct,
            feedback=feedback,
        )

    def _check_forbidden_keywords(self, query: str, forbidden: list[str]) -> dict:
        """Check for forbidden keywords in query using word boundary matching."""
        query_upper = query.upper()
        found = [kw for kw in forbidden if re.search(rf'\b{re.escape(kw.upper())}\b', query_upper)]

        return {
            'passed': len(found) == 0,
            'score': 100 if len(found) == 0 else 0,
            'found': found,
        }

    def _check_required_keywords(self, query: str, required: list[str]) -> dict:
        """Check for required keywords in query using word boundary matching."""
        query_upper = query.upper()
        missing = [kw for kw in required if not re.search(rf'\b{re.escape(kw.upper())}\b', query_upper)]

        if not required:
            return {'passed': True, 'score': 100, 'missing': []}

        score = (len(required) - len(missing)) / len(required) * 100

        return {
            'passed': len(missing) == 0,
            'score': score,
            'missing': missing,
        }

    def _check_result_match(
        self,
        student_result: dict,
        expected_result: dict,
        order_matters: bool = False,
        partial_match: bool = False,
    ) -> dict:
        """Check if student result matches expected result."""
        student_columns = student_result.get('columns', [])
        expected_columns = expected_result.get('columns', [])
        student_rows = student_result.get('rows', [])
        expected_rows = expected_result.get('rows', [])

        # Normalize column names (case-insensitive)
        student_cols_upper = [c.upper() for c in student_columns]
        expected_cols_upper = [c.upper() for c in expected_columns]

        # Check columns match
        if set(student_cols_upper) != set(expected_cols_upper):
            return {
                'passed': False,
                'score': 0,
                'column_mismatch': True,
                'details': 'Column mismatch',
            }

        # Reorder student rows to match expected column order if needed
        if student_cols_upper != expected_cols_upper:
            col_mapping = [student_cols_upper.index(c) for c in expected_cols_upper]
            student_rows = [[row[i] for i in col_mapping] for row in student_rows]

        # Convert rows to comparable format
        student_rows_normalized = [tuple(self._normalize_value(v) for v in row) for row in student_rows]
        expected_rows_normalized = [tuple(self._normalize_value(v) for v in row) for row in expected_rows]

        # Check row count
        if len(student_rows_normalized) != len(expected_rows_normalized):
            if partial_match:
                # Calculate partial score based on matching rows
                if order_matters:
                    matches = sum(
                        1 for s, e in zip(student_rows_normalized, expected_rows_normalized)
                        if s == e
                    )
                else:
                    student_set = set(student_rows_normalized)
                    expected_set = set(expected_rows_normalized)
                    matches = len(student_set & expected_set)

                score = matches / max(len(expected_rows_normalized), 1) * 100
                return {
                    'passed': False,
                    'score': score,
                    'row_count_mismatch': True,
                    'expected_rows': len(expected_rows_normalized),
                    'actual_rows': len(student_rows_normalized),
                }
            else:
                return {
                    'passed': False,
                    'score': 0,
                    'row_count_mismatch': True,
                    'expected_rows': len(expected_rows_normalized),
                    'actual_rows': len(student_rows_normalized),
                }

        # Check row content
        if order_matters:
            matches = sum(
                1 for s, e in zip(student_rows_normalized, expected_rows_normalized)
                if s == e
            )
        else:
            student_set = set(student_rows_normalized)
            expected_set = set(expected_rows_normalized)
            matches = len(student_set & expected_set)

        total = len(expected_rows_normalized) if expected_rows_normalized else 1
        score = matches / total * 100

        return {
            'passed': matches == total,
            'score': score,
            'details': f'{matches}/{total} rows match',
        }

    def _normalize_value(self, value):
        """Normalize a value for comparison."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            # Round floats for comparison
            if isinstance(value, float):
                return round(value, 6)
            return value
        # Convert to string for other types
        return str(value).strip()


# Global grading service instance
_grading_service: Optional[GradingService] = None


def get_grading_service() -> GradingService:
    """Get the global grading service instance."""
    global _grading_service
    if _grading_service is None:
        _grading_service = GradingService()
    return _grading_service
