import { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Spinner } from '@/components/ui/spinner';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from '@/components/ui/select';
import {
  Table as TableUI,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
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

/** Generate a UUID that works on HTTP (non-secure) contexts. */
function generateSessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return generateSessionId();
  }
  // Fallback for HTTP: use crypto.getRandomValues
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

interface QuickExample {
  labelKey: string;
  schema: string;
  seed: string;
  query: string;
}

const QUICK_EXAMPLES: Record<string, QuickExample[]> = {
  sqlite: [
    {
      labelKey: 'basicSelect',
      schema: 'CREATE TABLE users (\n  id INTEGER PRIMARY KEY,\n  name TEXT NOT NULL,\n  email TEXT UNIQUE\n);',
      seed: "INSERT INTO users (id, name, email) VALUES\n  (1, 'Alice', 'alice@example.com'),\n  (2, 'Bob', 'bob@example.com'),\n  (3, 'Charlie', 'charlie@example.com');",
      query: 'SELECT * FROM users;',
    },
    {
      labelKey: 'groupBy',
      schema: 'CREATE TABLE products (\n  id INTEGER PRIMARY KEY,\n  name TEXT,\n  price DECIMAL(10,2),\n  category TEXT\n);',
      seed: "INSERT INTO products (id, name, price, category) VALUES\n  (1, 'Laptop', 999.99, 'Electronics'),\n  (2, 'Phone', 599.99, 'Electronics'),\n  (3, 'Desk', 199.99, 'Furniture'),\n  (4, 'Chair', 149.99, 'Furniture');",
      query: 'SELECT category, COUNT(*) as count, AVG(price) as avg_price\nFROM products\nGROUP BY category;',
    },
    {
      labelKey: 'join',
      schema: 'CREATE TABLE orders (\n  id INTEGER PRIMARY KEY,\n  customer_id INTEGER,\n  total DECIMAL(10,2)\n);\n\nCREATE TABLE customers (\n  id INTEGER PRIMARY KEY,\n  name TEXT\n);',
      seed: "INSERT INTO customers (id, name) VALUES (1, 'Alice'), (2, 'Bob');\nINSERT INTO orders (id, customer_id, total) VALUES (1, 1, 100), (2, 1, 200), (3, 2, 150);",
      query: 'SELECT c.name, SUM(o.total) as total_spent\nFROM customers c\nJOIN orders o ON c.id = o.customer_id\nGROUP BY c.id, c.name;',
    },
  ],
  postgresql: [
    {
      labelKey: 'basicSelect',
      schema: 'CREATE TABLE users (\n  id SERIAL PRIMARY KEY,\n  name VARCHAR(100) NOT NULL,\n  email VARCHAR(255) UNIQUE\n);',
      seed: "INSERT INTO users (name, email) VALUES\n  ('Alice', 'alice@example.com'),\n  ('Bob', 'bob@example.com'),\n  ('Charlie', 'charlie@example.com');",
      query: 'SELECT * FROM users;',
    },
    {
      labelKey: 'windowFunctions',
      schema: 'CREATE TABLE employees (\n  id SERIAL PRIMARY KEY,\n  name VARCHAR(100),\n  department VARCHAR(50),\n  salary NUMERIC(10,2)\n);',
      seed: "INSERT INTO employees (name, department, salary) VALUES\n  ('Alice', 'Engineering', 95000),\n  ('Bob', 'Engineering', 105000),\n  ('Charlie', 'Sales', 70000),\n  ('Diana', 'Sales', 80000),\n  ('Eve', 'Engineering', 110000);",
      query: 'SELECT name, department, salary,\n  RANK() OVER (PARTITION BY department ORDER BY salary DESC) as dept_rank\nFROM employees;',
    },
    {
      labelKey: 'jsonQueries',
      schema: "CREATE TABLE events (\n  id SERIAL PRIMARY KEY,\n  name VARCHAR(100),\n  payload JSONB\n);",
      seed: "INSERT INTO events (name, payload) VALUES\n  ('signup', '{\"user\": \"alice\", \"plan\": \"pro\"}'),\n  ('purchase', '{\"user\": \"bob\", \"amount\": 49.99}'),\n  ('signup', '{\"user\": \"charlie\", \"plan\": \"free\"}');",
      query: "SELECT name,\n  payload->>'user' AS user_name,\n  payload->>'plan' AS plan\nFROM events\nWHERE payload ? 'plan';",
    },
  ],
  mariadb: [
    {
      labelKey: 'basicSelect',
      schema: 'CREATE TABLE users (\n  id INT AUTO_INCREMENT PRIMARY KEY,\n  name VARCHAR(100) NOT NULL,\n  email VARCHAR(255) UNIQUE\n);',
      seed: "INSERT INTO users (name, email) VALUES\n  ('Alice', 'alice@example.com'),\n  ('Bob', 'bob@example.com'),\n  ('Charlie', 'charlie@example.com');",
      query: 'SELECT * FROM users;',
    },
    {
      labelKey: 'groupBy',
      schema: 'CREATE TABLE products (\n  id INT AUTO_INCREMENT PRIMARY KEY,\n  name VARCHAR(100),\n  price DECIMAL(10,2),\n  category VARCHAR(50)\n);',
      seed: "INSERT INTO products (name, price, category) VALUES\n  ('Laptop', 999.99, 'Electronics'),\n  ('Phone', 599.99, 'Electronics'),\n  ('Desk', 199.99, 'Furniture'),\n  ('Chair', 149.99, 'Furniture');",
      query: 'SELECT category, COUNT(*) as count, AVG(price) as avg_price\nFROM products\nGROUP BY category;',
    },
    {
      labelKey: 'subquery',
      schema: 'CREATE TABLE products (\n  id INT AUTO_INCREMENT PRIMARY KEY,\n  name VARCHAR(100),\n  price DECIMAL(10,2)\n);\n\nCREATE TABLE orders (\n  id INT AUTO_INCREMENT PRIMARY KEY,\n  product_id INT,\n  quantity INT\n);',
      seed: "INSERT INTO products (name, price) VALUES\n  ('Laptop', 999.99),\n  ('Phone', 599.99),\n  ('Tablet', 399.99);\nINSERT INTO orders (product_id, quantity) VALUES\n  (1, 2), (1, 1), (3, 5);",
      query: 'SELECT name, price\nFROM products\nWHERE id IN (\n  SELECT product_id FROM orders\n);',
    },
  ],
  mongodb: [
    {
      labelKey: 'find',
      schema: '',
      seed: "db.users.insertMany([\n  { name: 'Alice', age: 30, city: 'Kyiv' },\n  { name: 'Bob', age: 25, city: 'Lviv' },\n  { name: 'Charlie', age: 35, city: 'Kyiv' }\n]);",
      query: 'db.users.find({ city: "Kyiv" });',
    },
    {
      labelKey: 'aggregate',
      schema: '',
      seed: "db.orders.insertMany([\n  { customer: 'Alice', amount: 100, status: 'completed' },\n  { customer: 'Alice', amount: 200, status: 'completed' },\n  { customer: 'Bob', amount: 150, status: 'pending' },\n  { customer: 'Bob', amount: 50, status: 'completed' }\n]);",
      query: 'db.orders.aggregate([\n  { $group: {\n    _id: "$customer",\n    totalSpent: { $sum: "$amount" },\n    orderCount: { $sum: 1 }\n  }}\n]);',
    },
    {
      labelKey: 'update',
      schema: '',
      seed: "db.products.insertMany([\n  { name: 'Laptop', price: 999, inStock: true },\n  { name: 'Phone', price: 599, inStock: true },\n  { name: 'Tablet', price: 399, inStock: false }\n]);",
      query: 'db.products.updateMany(\n  { price: { $gt: 500 } },\n  { $set: { premium: true } }\n);',
    },
  ],
  redis: [
    {
      labelKey: 'strings',
      schema: '',
      seed: 'SET user:1 "Alice"\nSET user:2 "Bob"\nSET user:3 "Charlie"',
      query: 'MGET user:1 user:2 user:3',
    },
    {
      labelKey: 'lists',
      schema: '',
      seed: 'LPUSH tasks "Write docs"\nLPUSH tasks "Fix bug"\nRPUSH tasks "Deploy"',
      query: 'LRANGE tasks 0 -1',
    },
    {
      labelKey: 'sortedSets',
      schema: '',
      seed: 'ZADD leaderboard 100 "Alice"\nZADD leaderboard 85 "Bob"\nZADD leaderboard 95 "Charlie"',
      query: 'ZRANGE leaderboard 0 -1 WITHSCORES',
    },
  ],
};

export function SandboxPage() {
  const { t } = useTranslation('sandbox');
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
  const abortControllerRef = useRef<AbortController | null>(null);

  // Client-side SQLite (sql.js/WASM)
  const sqlite = useSqlite();
  const [sqliteInitialized, setSqliteInitialized] = useState(false);
  const isSqlite = selectedDbType === 'sqlite';

  // Cleanup abort controller on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

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
    if (datasetId && datasetId !== '__custom__') {
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

    // Cancel any previous in-flight request
    abortControllerRef.current?.abort();
    const controller = new AbortController();
    abortControllerRef.current = controller;
    const timeoutId = setTimeout(() => controller.abort(), 30_000);

    try {
      setExecuting(true);
      setError('');
      setResult(null);

      // ── SQLite: execute locally via sql.js/WASM ──────────────
      if (isSqlite) {
        // Initialize DB on first execute (or after reset)
        if (!sqliteInitialized) {
          const initResult = await sqlite.initDatabase(schemaSql, seedSql);
          if (!initResult.success) {
            setError(initResult.error || 'SQLite initialization failed');
            return;
          }
          setSqliteInitialized(true);
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
        currentSessionId = generateSessionId();
        setSessionId(currentSessionId);
      }

      const needsInit = !sessionInitialized;

      let response = await sandboxApi.executeQuery({
        database_type: selectedDbType,
        query: query.trim(),
        session_id: currentSessionId,
        ...(needsInit ? { schema_sql: schemaSql, seed_sql: seedSql } : {}),
      }, controller.signal);

      // Handle session expired on server (idle > 15 min)
      const expiredMsg = (response.error_message || '').toLowerCase();
      if (!needsInit && expiredMsg === 'session_expired') {
        currentSessionId = generateSessionId();
        setSessionId(currentSessionId);
        response = await sandboxApi.executeQuery({
          database_type: selectedDbType,
          query: query.trim(),
          session_id: currentSessionId,
          schema_sql: schemaSql,
          seed_sql: seedSql,
        }, controller.signal);
      }

      const justInitialized = needsInit || response.session_id === currentSessionId;
      const errMsg = (response.error_message || '').toLowerCase();
      if (justInitialized
          && !errMsg.includes('schema init failed')
          && !errMsg.includes('seed data failed')
          && errMsg !== 'session_expired') {
        setSessionInitialized(true);
      }

      setResult(response);
    } catch (err) {
      if (controller.signal.aborted) {
        setError('Query timed out after 30 seconds');
      } else {
        setError(getApiErrorMessage(err, 'Failed to execute query'));
      }
    } finally {
      clearTimeout(timeoutId);
      abortControllerRef.current = null;
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
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Database className="h-6 w-6" />
            {t('title')}
          </h1>
          <p className="text-muted-foreground">
            {t('subtitle')}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {sessionId && sessionInitialized && (
            <Badge variant="success">
              {t('sessionActive')}
            </Badge>
          )}
          {sessionId && (
            <Button
              variant="outline"
              size="sm"
              onClick={handleResetSession}
            >
              <RotateCcw className="h-3 w-3 mr-1" />
              {t('resetSession')}
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
          <Card variant="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('database')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Select value={selectedDbType} onValueChange={(val) => {
                setSelectedDbType(val);
                setSelectedDataset('');
                setSchemaSql('');
                setSeedSql('');
                setResult(null);
              }}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {databaseTypes.map((type) => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selectedDbInfo && (
                <p className="text-xs text-muted-foreground">
                  {selectedDbInfo.description}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Dataset Selection */}
          <Card variant="glass">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{t('dataset')}</CardTitle>
                {(schemaSql || seedSql) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearSchema}
                    className="h-7 px-2"
                  >
                    <Trash2 className="h-3 w-3 mr-1" />
                    {t('clear')}
                  </Button>
                )}
              </div>
              <CardDescription>
                {t('datasetDescription')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <Select value={selectedDataset || '__custom__'} onValueChange={(val) => handleDatasetChange(val === '__custom__' ? '' : val)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__custom__">{t('customSchema')}</SelectItem>
                  {datasets.map((dataset) => (
                    <SelectItem key={dataset.id} value={dataset.id}>
                      {dataset.name}{dataset.course_title ? ` (${dataset.course_title})` : ''}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>

          {/* Schema Editor */}
          <Card variant="glass">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileCode className="h-4 w-4" />
                  {t('schema')}
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSchema(!showSchema)}
                  className="h-7 px-2"
                >
                  {showSchema ? t('hide') : t('show')}
                </Button>
              </div>
            </CardHeader>
            {showSchema && (
              <CardContent className="space-y-3">
                <div>
                  <Label className="text-xs text-muted-foreground">
                    {t('createStatements')}
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
                    {t('seedData')}
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
          <Card variant="glass">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">{t('query')}</CardTitle>
              <CardDescription>
                {t('queryDescription')}
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
                  {t('runQuery')}
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Results */}
          {result && (
            <Card variant="glass">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base flex items-center gap-2">
                    <Table className="h-4 w-4" />
                    {t('results')}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    {result.success ? (
                      <Badge variant="success">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        {t('success')}
                      </Badge>
                    ) : (
                      <Badge variant="destructive">
                        <XCircle className="h-3 w-3 mr-1" />
                        {t('error')}
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
                  <div className="overflow-auto max-h-96 border border-border/50 rounded-xl">
                    <TableUI>
                      <TableHeader className="sticky top-0">
                        <TableRow>
                          {result.columns.map((col, i) => (
                            <TableHead key={i}>{col}</TableHead>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.rows.length === 0 ? (
                          <TableRow>
                            <TableCell
                              colSpan={result.columns.length}
                              className="text-center text-muted-foreground py-4"
                            >
                              {t('noRows')}
                            </TableCell>
                          </TableRow>
                        ) : (
                          result.rows.slice(0, 100).map((row, i) => (
                            <TableRow key={i}>
                              {row.map((cell, j) => (
                                <TableCell key={j}>
                                  {cell === null ? (
                                    <span className="text-muted-foreground italic">NULL</span>
                                  ) : (
                                    String(cell)
                                  )}
                                </TableCell>
                              ))}
                            </TableRow>
                          ))
                        )}
                      </TableBody>
                    </TableUI>
                  </div>
                )}

                {result.success && result.affected_rows !== undefined && (
                  <p className="text-sm text-muted-foreground">
                    {t('rowsAffected', { count: result.affected_rows })}
                  </p>
                )}

                {result.row_count !== undefined && result.row_count > 100 && (
                  <p className="text-xs text-muted-foreground mt-2">
                    {t('showingRows', { shown: 100, total: result.row_count })}
                  </p>
                )}
              </CardContent>
            </Card>
          )}

          {/* Quick examples */}
          {!result && (
            <Card variant="glass">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">{t('quickStart')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {t('tryExamples')}
                </p>
                <div className="flex flex-wrap gap-2">
                  {(QUICK_EXAMPLES[selectedDbType] || []).map((example) => (
                    <Button
                      key={example.labelKey}
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        resetSessionState();
                        setSchemaSql(example.schema);
                        setSeedSql(example.seed);
                        setQuery(example.query);
                      }}
                    >
                      {t(example.labelKey)}
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
