/**
 * Inline SQL exercise block for embedding inside Markdown theory content.
 *
 * Usage in markdown (theory_content):
 * ```sql-exercise
 * {"schema":"CREATE TABLE users(id INT, name TEXT);","seed":"INSERT INTO users VALUES(1,'Alice'),(2,'Bob');","initial":"SELECT ","hint":"Try SELECT * FROM users"}
 * ```
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
  const sqlite = useSqlite();
  const [query, setQuery] = useState(config.initial ?? '');
  const [result, setResult] = useState<LocalQueryResult | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [initialized, setInitialized] = useState(false);

  async function ensureInit() {
    if (!initialized) {
      await sqlite.initDatabase(config.schema ?? '', config.seed ?? '');
      setInitialized(true);
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
    <div className="my-4 border rounded-lg overflow-hidden not-prose">
      <div className="bg-muted/50 px-3 py-2 flex items-center justify-between border-b">
        <span className="text-sm font-medium">Try it yourself</span>
        <div className="flex items-center gap-1">
          {config.hint && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowHint(!showHint)}
              className="gap-1 h-7 text-xs"
            >
              <Lightbulb className="h-3 w-3" />
              Hint
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReset}
            className="gap-1 h-7 text-xs"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </Button>
        </div>
      </div>

      {showHint && config.hint && (
        <div className="px-3 py-2 bg-yellow-50 dark:bg-yellow-950 border-b text-sm">
          {config.hint}
        </div>
      )}

      <SqlEditor
        value={query}
        onChange={setQuery}
        height="80px"
        onExecute={handleRun}
        placeholder="-- Write your query and press Ctrl+Enter"
      />

      <div className="px-3 py-2 border-t flex justify-end">
        <Button size="sm" onClick={handleRun} className="gap-1 h-7">
          <Play className="h-3 w-3" />
          Run
        </Button>
      </div>

      {result && (
        <div className="border-t">
          {result.error_message && (
            <Alert variant="destructive" className="rounded-none border-0">
              <AlertDescription className="font-mono text-xs">
                {result.error_message}
              </AlertDescription>
            </Alert>
          )}
          {result.success && result.columns.length > 0 && (
            <div className="overflow-auto max-h-48">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    {result.columns.map((col, i) => (
                      <th key={i} className="px-2 py-1 text-left font-medium border-b text-xs">
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.rows.slice(0, 20).map((row, i) => (
                    <tr key={i} className="border-b">
                      {(row as unknown[]).map((cell, j) => (
                        <td key={j} className="px-2 py-1 font-mono text-xs">
                          {cell === null ? (
                            <span className="text-muted-foreground italic">NULL</span>
                          ) : (
                            String(cell)
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {result.success && result.columns.length === 0 && result.affected_rows > 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">
              {result.affected_rows} row(s) affected
            </div>
          )}
          {result.success && (
            <div className="px-3 py-1 border-t">
              <Badge variant="outline" className="text-xs">
                {result.execution_time_ms}ms
              </Badge>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
