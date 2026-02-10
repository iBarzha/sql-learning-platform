/**
 * Inline SQL exercise block for embedding inside Markdown theory content.
 *
 * Usage in markdown (theory_content):
 * ```sql-exercise
 * {"schema":"CREATE TABLE users(id INT, name TEXT);","seed":"INSERT INTO users VALUES(1,'Alice'),(2,'Bob');","initial":"SELECT ","hint":"Try SELECT * FROM users"}
 * ```
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Play, RotateCcw, Lightbulb } from 'lucide-react';
import { SqlEditor } from './SqlEditor';
import { useSqlite } from '@/hooks/useSqlite';
import type { LocalQueryResult } from '@/lib/sqljs';

interface ExerciseConfig {
  schema?: string;
  seed?: string;
  initial?: string;
  hint?: string;
}

interface SqlExerciseBlockProps {
  config: ExerciseConfig;
}

export function SqlExerciseBlock({ config }: SqlExerciseBlockProps) {
  const { t } = useTranslation('editor');
  const sqlite = useSqlite();
  const [query, setQuery] = useState(config.initial ?? '');
  const [result, setResult] = useState<LocalQueryResult | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [initializing, setInitializing] = useState(false);

  async function ensureInit() {
    if (!initialized && !initializing) {
      setInitializing(true);
      try {
        await sqlite.initDatabase(config.schema ?? '', config.seed ?? '');
        setInitialized(true);
      } finally {
        setInitializing(false);
      }
    }
  }

  async function handleRun() {
    await ensureInit();
    if (!query.trim()) return;
    const res = sqlite.execute(query.trim());
    setResult(res);
  }

  async function handleReset() {
    await sqlite.initDatabase(config.schema ?? '', config.seed ?? '');
    setInitialized(true);
    setQuery(config.initial ?? '');
    setResult(null);
  }

  return (
    <div className="my-4 border border-border/50 rounded-xl overflow-hidden not-prose">
      <div className="bg-muted/50 px-3 py-2 flex items-center justify-between border-b border-border/50">
        <span className="text-sm font-medium">{t('tryItYourself')}</span>
        <div className="flex items-center gap-1">
          {config.hint && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowHint(!showHint)}
              className="gap-1 h-7 text-xs"
            >
              <Lightbulb className="h-3 w-3" />
              {t('hint')}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="gap-1 h-7 text-xs"
          >
            <RotateCcw className="h-3 w-3" />
            {t('reset')}
          </Button>
        </div>
      </div>

      {showHint && config.hint && (
        <div className="px-3 py-2 bg-warning/5 border-b border-warning/20 text-sm text-warning">
          {config.hint}
        </div>
      )}

      <SqlEditor
        value={query}
        onChange={setQuery}
        height="80px"
        onExecute={handleRun}
        placeholder={t('writeQuery')}
      />

      <div className="px-3 py-2 border-t border-border/50 flex justify-end">
        <Button size="sm" onClick={handleRun} disabled={initializing} className="gap-1 h-7">
          <Play className="h-3 w-3" />
          {initializing ? t('loading') : t('run')}
        </Button>
      </div>

      {result && (
        <div className="border-t border-border/50">
          {result.error_message && (
            <Alert variant="destructive" className="rounded-none border-0">
              <AlertDescription className="font-mono text-xs">
                {result.error_message}
              </AlertDescription>
            </Alert>
          )}
          {result.success && result.columns.length > 0 && (
            <div className="overflow-auto max-h-48">
              <Table>
                <TableHeader>
                  <TableRow>
                    {result.columns.map((col, i) => (
                      <TableHead key={i}>{col}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.rows.slice(0, 20).map((row, i) => (
                    <TableRow key={i}>
                      {(row as unknown[]).map((cell, j) => (
                        <TableCell key={j}>
                          {cell === null ? (
                            <span className="text-muted-foreground italic">NULL</span>
                          ) : (
                            String(cell)
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
          {result.success && result.columns.length === 0 && result.affected_rows > 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              {t('rowsAffected', { count: result.affected_rows })}
            </div>
          )}
          {result.success && (
            <div className="px-3 py-1 border-t border-border/50">
              <Badge variant="outline" className="text-xs">
                {t('executionTime', { time: result.execution_time_ms })}
              </Badge>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
