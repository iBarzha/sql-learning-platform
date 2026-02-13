/**
 * sql.js (SQLite compiled to WebAssembly) singleton loader.
 *
 * Loads the WASM binary once per session and provides helpers
 * that return the same QueryResult shape as the server API.
 */

import initSqlJsModule, { type Database, type SqlJsStatic } from 'sql.js';

let sqlPromise: Promise<SqlJsStatic> | null = null;

/** Load the sql.js WASM module (cached after first call). */
export function initSqlJs(): Promise<SqlJsStatic> {
  if (!sqlPromise) {
    sqlPromise = Promise.race([
      initSqlJsModule({
        locateFile: () => '/sql-wasm.wasm',
      }),
      new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error('SQL.js WASM load timeout (15s)')), 15000)
      ),
    ]);
  }
  return sqlPromise;
}

export interface LocalQueryResult {
  success: boolean;
  columns: string[];
  rows: unknown[][];
  row_count: number;
  affected_rows: number;
  execution_time_ms: number;
  error_message: string;
}

/** Create an in-memory database, optionally initialized with schema + seed SQL. */
export async function createDatabase(
  schemaSql?: string,
  seedSql?: string,
): Promise<Database> {
  const SQL = await initSqlJs();
  const db = new SQL.Database();

  if (schemaSql?.trim()) {
    db.run(schemaSql);
  }
  if (seedSql?.trim()) {
    db.run(seedSql);
  }

  return db;
}

/** Execute a query and return a result matching the server API shape. */
export function executeQuery(db: Database, query: string): LocalQueryResult {
  const start = performance.now();

  try {
    const results = db.exec(query);
    const elapsed = Math.round(performance.now() - start);

    if (results.length === 0) {
      // DDL or DML with no result set (CREATE TABLE, INSERT, etc.)
      const changes = db.getRowsModified();
      return {
        success: true,
        columns: [],
        rows: [],
        row_count: 0,
        affected_rows: changes,
        execution_time_ms: elapsed,
        error_message: '',
      };
    }

    // Return the last result set (handles multi-statement queries)
    const last = results[results.length - 1];
    return {
      success: true,
      columns: last.columns,
      rows: last.values,
      row_count: last.values.length,
      affected_rows: 0,
      execution_time_ms: elapsed,
      error_message: '',
    };
  } catch (err) {
    const elapsed = Math.round(performance.now() - start);
    return {
      success: false,
      columns: [],
      rows: [],
      row_count: 0,
      affected_rows: 0,
      execution_time_ms: elapsed,
      error_message: err instanceof Error ? err.message : String(err),
    };
  }
}
