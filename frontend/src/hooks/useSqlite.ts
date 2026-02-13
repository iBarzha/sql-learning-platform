/**
 * React hook for client-side SQLite execution via sql.js/WASM.
 *
 * Manages an in-memory SQLite database lifecycle:
 *   - initDatabase(schema, seed) — creates a fresh DB
 *   - execute(query) — runs a query, returns QueryResult
 *   - reset() — drops and recreates the DB
 *   - Automatically closes DB on unmount
 */

import { useRef, useState, useCallback, useEffect } from 'react';
import type { Database } from 'sql.js';
import {
  createDatabase,
  executeQuery,
  type LocalQueryResult,
} from '@/lib/sqljs';

interface InitResult {
  success: boolean;
  error?: string;
}

interface UseSqliteReturn {
  /** Whether the WASM module and DB are ready. */
  isReady: boolean;
  /** Error during initialization. */
  initError: string | null;
  /** Initialize (or re-initialize) the database with schema + seed. Returns result directly. */
  initDatabase: (schemaSql: string, seedSql: string) => Promise<InitResult>;
  /** Execute a query against the local database. */
  execute: (query: string) => LocalQueryResult | null;
  /** Reset DB: drop everything, re-run stored schema + seed. */
  reset: () => Promise<void>;
}

export function useSqlite(): UseSqliteReturn {
  const dbRef = useRef<Database | null>(null);
  const schemaRef = useRef<string>('');
  const seedRef = useRef<string>('');
  const [isReady, setIsReady] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (dbRef.current) {
        try {
          dbRef.current.close();
        } catch {
          // ignore
        }
        dbRef.current = null;
      }
    };
  }, []);

  const initializingRef = useRef(false);

  const initDatabase = useCallback(async (schemaSql: string, seedSql: string): Promise<InitResult> => {
    if (initializingRef.current) {
      return { success: false, error: 'Initialization already in progress' };
    }
    initializingRef.current = true;

    // Close previous DB
    if (dbRef.current) {
      try {
        dbRef.current.close();
      } catch {
        // ignore
      }
      dbRef.current = null;
    }

    setIsReady(false);
    setInitError(null);
    schemaRef.current = schemaSql;
    seedRef.current = seedSql;

    try {
      dbRef.current = await createDatabase(schemaSql, seedSql);
      setIsReady(true);
      return { success: true };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setInitError(msg);
      return { success: false, error: msg };
    } finally {
      initializingRef.current = false;
    }
  }, []);

  const execute = useCallback((query: string): LocalQueryResult | null => {
    if (!dbRef.current) return null;
    return executeQuery(dbRef.current, query);
  }, []);

  const reset = useCallback(async () => {
    await initDatabase(schemaRef.current, seedRef.current);
  }, [initDatabase]);

  return { isReady, initError, initDatabase, execute, reset };
}
