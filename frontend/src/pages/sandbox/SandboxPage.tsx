import { useEffect, useState, useCallback, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Label } from '@/components/ui/label';
import {
  Play,
  Database,
  Table,
  Clock,
  CheckCircle,
  XCircle,
  Trash2,
  FileCode,
  RotateCcw,
} from 'lucide-react';
import sandboxApi, {
  type QueryResult,
} from '@/api/sandbox';
import { getApiErrorMessage } from '@/lib/utils';
import { SqlEditor } from '@/components/editor/SqlEditor';
import { useSqlite } from '@/hooks/useSqlite';
import { useDatabaseTypes, useSandboxDatasets } from '@/hooks/queries/useSandbox';

export function SandboxPage() {
  const [selectedDbType, setSelectedDbType] = useState('sqlite');
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [schemaSql, setSchemaSql] = useState('');
  const [seedSql, setSeedSql] = useState('');
  const [query, setQuery] = useState('');
  const [result, setResult] = useState<QueryResult | null>(null);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState('');
  const [showSchema, setShowSchema] = useState(true);

  // React Query for database types and datasets
  const { data: databaseTypes = [], isLoading: loading } = useDatabaseTypes();
  const { data: datasets = [] } = useSandboxDatasets(selectedDbType);

  // Session state (for server-side DBs)
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionInitialized, setSessionInitialized] = useState(false);
  const prevDbTypeRef = useRef(selectedDbType);
  const prevDatasetRef = useRef(selectedDataset);

  // Client-side SQLite (sql.js/WASM)
  const sqlite = useSqlite();
  const [sqliteInitialized, setSqliteInitialized] = useState(false);
  const isSqlite = selectedDbType === 'sqlite';

  // Reset session when DB type changes
  useEffect(() => {
    if (prevDbTypeRef.current !== selectedDbType) {
      resetSessionState();
      prevDbTypeRef.current = selectedDbType;
    }
  }, [selectedDbType]);

  // Reset session when dataset changes
  useEffect(() => {
    if (prevDatasetRef.current !== selectedDataset) {
      resetSessionState();
      prevDatasetRef.current = selectedDataset;
    }
  }, [selectedDataset]);

  function resetSessionState() {
    // Reset server session
    if (sessionId) {
      sandboxApi.resetSession(sessionId).catch(() => {});
    }
    setSessionId(null);
    setSessionInitialized(false);
    // Reset local SQLite
    setSqliteInitialized(false);
  }

  async function handleResetSession() {
    // Reset server session
    if (sessionId) {
      try {
        await sandboxApi.resetSession(sessionId);
      } catch {
        // ignore
      }
    }
    setSessionId(null);
    setSessionInitialized(false);
    // Reset local SQLite
    setSqliteInitialized(false);
    setResult(null);
  }

  function handleDatasetChange(datasetId: string) {
    setSelectedDataset(datasetId);
    if (datasetId) {
      const dataset = datasets.find((d) => d.id === datasetId);
      if (dataset) {
        setSchemaSql(dataset.schema_sql);
        setSeedSql(dataset.seed_sql);
      }
    }
  }

  function handleClearSchema() {
    setSelectedDataset('');
    setSchemaSql('');
    setSeedSql('');
  }

  const handleExecute = useCallback(async () => {
    if (!query.trim()) return;

    try {
      setExecuting(true);
      setError('');
      setResult(null);

      // ── SQLite: execute locally via sql.js/WASM ──────────────
      if (isSqlite) {
        // Initialize DB on first execute (or after reset)
        if (!sqliteInitialized) {
          await sqlite.initDatabase(schemaSql, seedSql);
          setSqliteInitialized(true);
        }
        if (sqlite.initError) {
          setError(sqlite.initError);
          return;
        }
        const localResult = sqlite.execute(query.trim());
        if (localResult) {
          setResult({
            success: localResult.success,
            columns: localResult.columns,
            rows: localResult.rows as unknown[][],
            row_count: localResult.row_count,
            affected_rows: localResult.affected_rows,
            execution_time_ms: localResult.execution_time_ms,
            error_message: localResult.error_message || undefined,
          });
        }
        return;
      }

      // ── Other DBs: execute on server with session ────────────
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        currentSessionId = crypto.randomUUID();
        setSessionId(currentSessionId);
      }

      const needsInit = !sessionInitialized;

      let response = await sandboxApi.executeQuery({
        database_type: selectedDbType,
        query: query.trim(),
        session_id: currentSessionId,
        ...(needsInit ? { schema_sql: schemaSql, seed_sql: seedSql } : {}),
      });

      // Handle session expired on server (idle > 15 min)
      if (!needsInit && response.error_message === 'SESSION_EXPIRED') {
        currentSessionId = crypto.randomUUID();
        setSessionId(currentSessionId);
        response = await sandboxApi.executeQuery({
          database_type: selectedDbType,
          query: query.trim(),
          session_id: currentSessionId,
          schema_sql: schemaSql,
          seed_sql: seedSql,
        });
      }

      const justInitialized = needsInit || response.session_id === currentSessionId;
      if (justInitialized && !response.error_message?.includes('Schema init failed')
          && !response.error_message?.includes('Seed data failed')
          && response.error_message !== 'SESSION_EXPIRED') {
        setSessionInitialized(true);
      }

      setResult(response);
    } catch (err) {
      setError(getApiErrorMessage(err, 'Failed to execute query'));
    } finally {
      setExecuting(false);
    }
  }, [query, selectedDbType, schemaSql, seedSql, sessionId, sessionInitialized, isSqlite, sqlite, sqliteInitialized]);

  // Ctrl+Enter is handled by Monaco editor's onExecute prop

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  const selectedDbInfo = databaseTypes.find((t) => t.value === selectedDbType);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6" />
            SQL Sandbox
          </h1>
          <p className="text-muted-foreground">
            Practice SQL queries in an isolated environment
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sessionId && sessionInitialized && (
            <Badge variant="outline" className="text-green-600 border-green-300">
              Session Active
            </Badge>
          )}
          {sessionId && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetSession}
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              Reset Session
            </Button>
          )}
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left panel: Configuration */}
        <div className="space-y-4">
          {/* Database Type Selection */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Database</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                value={selectedDbType}
                onChange={(e) => {
                  setSelectedDbType(e.target.value);
                  setSelectedDataset('');
                  setSchemaSql('');
                  setSeedSql('');
                  setResult(null);
                }}
                className="w-full px-3 py-2 bg-background border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                {databaseTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
              {selectedDbInfo && (
                <p className="text-xs text-muted-foreground">
                  {selectedDbInfo.description}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Dataset Selection */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Dataset</CardTitle>
                {(schemaSql || seedSql) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearSchema}
                    className="h-7 px-2"
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    Clear
                  </Button>
                )}
              </div>
              <CardDescription>
                Choose a predefined dataset or create your own
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <select
                value={selectedDataset}
                onChange={(e) => handleDatasetChange(e.target.value)}
                className="w-full px-3 py-2 bg-background border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">Custom schema</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}{dataset.course_title ? ` (${dataset.course_title})` : ''}
                  </option>
                ))}
              </select>
            </CardContent>
          </Card>

          {/* Schema Editor */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileCode className="h-4 w-4" />
                  Schema
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSchema(!showSchema)}
                  className="h-7 px-2"
                >
                  {showSchema ? 'Hide' : 'Show'}
                </Button>
              </div>
            </CardHeader>
            {showSchema && (
              <CardContent className="space-y-3">
                <div>
                  <Label className="text-xs text-muted-foreground">
                    CREATE statements
                  </Label>
                  <div className="mt-1">
                    <SqlEditor
                      value={schemaSql}
                      onChange={setSchemaSql}
                      height="112px"
                      placeholder="CREATE TABLE users (  id INTEGER PRIMARY KEY,  name TEXT);"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">
                    Seed data (INSERT statements)
                  </Label>
                  <div className="mt-1">
                    <SqlEditor
                      value={seedSql}
                      onChange={setSeedSql}
                      height="112px"
                      placeholder="INSERT INTO users (name) VALUES ('Alice');"
                    />
                  </div>
                </div>
              </CardContent>
            )}
          </Card>
        </div>

        {/* Right panel: Query and Results */}
        <div className="lg:col-span-2 space-y-4">
          {/* Query Editor */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Query</CardTitle>
              <CardDescription>
                Press Ctrl+Enter to execute. State persists across queries in your session.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <SqlEditor
                value={query}
                onChange={setQuery}
                language={selectedDbType === 'mongodb' ? 'javascript' : selectedDbType === 'redis' ? 'redis' : 'sql'}
                height="160px"
                onExecute={handleExecute}
                placeholder="-- Write your SQL query here\nSELECT * FROM users;"
              />
              <div className="flex items-center justify-end mt-4">
                <Button onClick={handleExecute} disabled={executing || !query.trim()}>
                  {executing ? (
                    <Spinner size="sm" className="mr-2" />
                  ) : (
                    <Play className="h-4 w-4 mr-2" />
                  )}
                  Run Query
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {result && (
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Table className="h-4 w-4" />
                    Results
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {result.success ? (
                      <Badge variant="default" className="bg-green-500">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Success
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        Error
                      </Badge>
                    )}
                    <Badge variant="outline">
                      <Clock className="h-3 w-3 mr-1" />
                      {result.execution_time_ms}ms
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {result.error_message && (
                  <Alert variant="destructive" className="mb-4">
                    <AlertDescription className="font-mono text-xs">
                      {result.error_message}
                    </AlertDescription>
                  </Alert>
                )}

                {result.success && result.columns && result.rows && (
                  <div className="overflow-auto max-h-96 border rounded-md">
                    <table className="w-full text-sm">
                      <thead className="bg-muted sticky top-0">
                        <tr>
                          {result.columns.map((col, i) => (
                            <th
                              key={i}
                              className="px-3 py-2 text-left font-medium border-b"
                            >
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {result.rows.length === 0 ? (
                          <tr>
                            <td
                              colSpan={result.columns.length}
                              className="px-3 py-4 text-center text-muted-foreground"
                            >
                              No rows returned
                            </td>
                          </tr>
                        ) : (
                          result.rows.slice(0, 100).map((row, i) => (
                            <tr key={i} className="border-b hover:bg-muted/50">
                              {row.map((cell, j) => (
                                <td key={j} className="px-3 py-2 font-mono text-xs">
                                  {cell === null ? (
                                    <span className="text-muted-foreground italic">NULL</span>
                                  ) : (
                                    String(cell)
                                  )}
                                </td>
                              ))}
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                )}

                {result.success && result.affected_rows !== undefined && (
                  <p className="text-sm text-muted-foreground">
                    {result.affected_rows} row(s) affected
                  </p>
                )}

                {result.row_count !== undefined && result.row_count > 100 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    Showing 100 of {result.row_count} rows
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Quick examples */}
          {!result && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Quick Start</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  Try these example queries:
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      resetSessionState();
                      setSchemaSql('CREATE TABLE users (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  email TEXT UNIQUE\n);');
                      setSeedSql("INSERT INTO users (name, email) VALUES\n  ('Alice', 'alice@example.com'),\n  ('Bob', 'bob@example.com'),\n  ('Charlie', 'charlie@example.com');");
                      setQuery('SELECT * FROM users;');
                    }}
                  >
                    Basic SELECT
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      resetSessionState();
                      setSchemaSql('CREATE TABLE products (\n  id INTEGER PRIMARY KEY,\n  name TEXT,\n  price DECIMAL(10,2),\n  category TEXT\n);');
                      setSeedSql("INSERT INTO products (name, price, category) VALUES\n  ('Laptop', 999.99, 'Electronics'),\n  ('Phone', 599.99, 'Electronics'),\n  ('Desk', 199.99, 'Furniture'),\n  ('Chair', 149.99, 'Furniture');");
                      setQuery('SELECT category, COUNT(*) as count, AVG(price) as avg_price\nFROM products\nGROUP BY category;');
                    }}
                  >
                    GROUP BY
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      resetSessionState();
                      setSchemaSql('CREATE TABLE orders (\n  id INTEGER PRIMARY KEY,\n  customer_id INTEGER,\n  total DECIMAL(10,2)\n);\n\nCREATE TABLE customers (\n  id INTEGER PRIMARY KEY,\n  name TEXT\n);');
                      setSeedSql("INSERT INTO customers (id, name) VALUES (1, 'Alice'), (2, 'Bob');\nINSERT INTO orders (customer_id, total) VALUES (1, 100), (1, 200), (2, 150);");
                      setQuery('SELECT c.name, SUM(o.total) as total_spent\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nGROUP BY c.id, c.name;');
                    }}
                  >
                    JOIN
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
