import type { CriterionInfo, CriterionKind, ExerciseCriteria } from '@/types';

const DML = /^\s*(insert|update|delete|create|alter|drop|truncate|replace)\b/i;
const RESULT_CRITERIA = new Set(['columns', 'column_names', 'complete', 'precise', 'order']);

// Mirrors the server's applicability rules closely enough for the form; the server
// drops anything it disagrees with at grading time, so a stale choice never breaks grading.
export function detectKind(expectedQuery: string, dbType: string): CriterionKind {
  if (dbType === 'mongodb' || dbType === 'redis') return 'nosql';
  return DML.test(expectedQuery) ? 'dml' : 'select';
}

// Only a top-level ORDER BY counts (the server strips window and subquery ordering),
// so parenthesised parts are removed before looking.
export function hasOrderBy(expectedQuery: string): boolean {
  let text = expectedQuery;
  let previous = '';
  while (previous !== text) {
    previous = text;
    text = text.replace(/\([^()]*\)/g, ' ');
  }
  return /\border\s+by\b/i.test(text);
}

export function applicableCriteria(
  catalog: CriterionInfo[],
  kind: CriterionKind,
  expectedQuery: string,
  hasReference: boolean,
): CriterionInfo[] {
  return catalog.filter((c) => {
    if (!c.kinds.includes(kind)) return false;
    if (RESULT_CRITERIA.has(c.id) && !hasReference) return false;
    if (c.id === 'order' && kind !== 'nosql' && !hasOrderBy(expectedQuery)) return false;
    return true;
  });
}

export function defaultCriteria(applicable: CriterionInfo[]): ExerciseCriteria {
  return {
    enabled: applicable.map((c) => c.id).filter((id) => id !== 'column_names'),
    threshold: 0,
  };
}

export interface DerivedCriterion {
  id: string;
  name: string;
  hint: string;
}

export function derivedCriteria(
  exercise: {
    check_datasets?: { name: string }[];
    required_keywords?: string[];
    forbidden_keywords?: string[];
    expected_query?: string;
  },
  kind: CriterionKind,
): DerivedCriterion[] {
  const out: DerivedCriterion[] = [];
  // Data-changing tasks are graded by table state on the primary data only.
  if (exercise.expected_query?.trim() && kind !== 'dml') {
    (exercise.check_datasets ?? []).forEach((ds, i) =>
      out.push({ id: `dataset:${i + 1}`, name: `Контрольний набір №${i + 1}`, hint: ds.name || '' })
    );
  }
  (exercise.required_keywords ?? [])
    .filter((k) => k.trim())
    .forEach((k) => out.push({ id: `require:${k.trim()}`, name: `Використано ${k.trim()}`, hint: '' }));
  (exercise.forbidden_keywords ?? [])
    .filter((k) => k.trim())
    .forEach((k) => out.push({ id: `forbid:${k.trim()}`, name: `Не використано ${k.trim()}`, hint: '' }));
  return out;
}
