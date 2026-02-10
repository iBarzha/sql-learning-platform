declare module 'sql.js' {
  export interface QueryExecResult {
    columns: string[];
    values: unknown[][];
  }

  export interface ParamsObject {
    [key: string]: unknown;
  }

  export interface Database {
    run(sql: string, params?: ParamsObject | unknown[]): Database;
    exec(sql: string, params?: ParamsObject | unknown[]): QueryExecResult[];
    each(
      sql: string,
      callback: (row: Record<string, unknown>) => void,
      done?: () => void,
    ): Database;
    prepare(sql: string): Statement;
    getRowsModified(): number;
    close(): void;
    export(): Uint8Array;
  }

  export interface Statement {
    bind(params?: ParamsObject | unknown[]): boolean;
    step(): boolean;
    getAsObject(): Record<string, unknown>;
    get(): unknown[];
    getColumnNames(): string[];
    free(): boolean;
    reset(): void;
    run(params?: ParamsObject | unknown[]): void;
  }

  export interface SqlJsStatic {
    Database: new (data?: ArrayLike<number> | Buffer | null) => Database;
  }

  export interface SqlJsConfig {
    locateFile?: (filename: string) => string;
  }

  export default function initSqlJs(config?: SqlJsConfig): Promise<SqlJsStatic>;
}
