import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { applicableCriteria, defaultCriteria, type DerivedCriterion } from '@/lib/criteria';
import type { CriterionInfo, CriterionKind, ExerciseCriteria } from '@/types';

interface CriteriaEditorProps {
  value: ExerciseCriteria;
  onChange: (value: ExerciseCriteria) => void;
  catalog: CriterionInfo[];
  kind: CriterionKind;
  expectedQuery: string;
  hasReference: boolean;
  derived: DerivedCriterion[];
}

/**
 * Instructor-facing checklist of grading criteria for one exercise.
 *
 * An empty `enabled` list means "server defaults" (everything applicable except column
 * names) and is shown as such; the list is only materialized once the instructor
 * toggles something. A stored threshold of 0 means "all criteria", so adding a dataset
 * later keeps that meaning; an explicit smaller number is stored as is.
 */
export function CriteriaEditor({
  value,
  onChange,
  catalog,
  kind,
  expectedQuery,
  hasReference,
  derived,
}: CriteriaEditorProps) {
  const applicable = applicableCriteria(catalog, kind, expectedQuery, hasReference);
  const chosen = value.enabled.length > 0 ? value.enabled : defaultCriteria(applicable).enabled;
  const enabled = new Set(chosen.filter((id) => applicable.some((c) => c.id === id)));
  enabled.add('execution');
  const total = enabled.size + derived.length;
  const threshold = value.threshold > 0 && value.threshold <= total ? value.threshold : total;

  function emit(nextEnabled: Set<string>, nextThreshold: number) {
    const nextTotal = nextEnabled.size + derived.length;
    const clamped = Math.max(1, Math.min(nextThreshold, nextTotal));
    onChange({
      enabled: applicable.map((c) => c.id).filter((id) => nextEnabled.has(id)),
      threshold: clamped === nextTotal ? 0 : clamped,
    });
  }

  function toggle(id: string, on: boolean) {
    const next = new Set(enabled);
    if (on) next.add(id);
    else next.delete(id);
    next.add('execution');
    // "All criteria" stays "all" when a criterion is added; an explicit N is kept.
    const keepAll = value.threshold <= 0 || value.threshold >= total;
    emit(next, keepAll ? Number.MAX_SAFE_INTEGER : threshold);
  }

  function setThreshold(raw: string) {
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n)) return;
    emit(enabled, n);
  }

  return (
    <div className="space-y-3" data-testid="criteria-editor">
      <div className="space-y-2">
        {applicable.map((c) => (
          <div key={c.id} className="flex items-start gap-3">
            <Switch
              id={`crit-${c.id}`}
              checked={enabled.has(c.id)}
              disabled={c.id === 'execution'}
              onCheckedChange={(on) => toggle(c.id, on)}
              aria-label={c.name}
            />
            <div>
              <Label htmlFor={`crit-${c.id}`}>{c.name}</Label>
              <p className="text-xs text-muted-foreground">{c.description}</p>
            </div>
          </div>
        ))}
      </div>
      {derived.length > 0 && (
        <div className="space-y-1 border-l-2 pl-3">
          {derived.map((d) => (
            <p key={d.id} className="text-sm">
              {d.name}
              {d.hint && <span className="text-muted-foreground"> ({d.hint})</span>}
              <span className="block text-xs text-muted-foreground">
                Керується списком наборів або ключових слів вище
              </span>
            </p>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <Label htmlFor="criteria-threshold">Достатньо</Label>
        <Input
          id="criteria-threshold"
          type="number"
          min={1}
          max={total}
          className="w-20"
          value={threshold}
          onChange={(e) => setThreshold(e.target.value)}
        />
        <span className="text-sm text-muted-foreground">з {total}</span>
      </div>
    </div>
  );
}
