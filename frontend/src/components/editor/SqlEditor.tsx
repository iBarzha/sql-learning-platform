import { useRef, useCallback, useEffect } from 'react';
import Editor, { type OnMount, type BeforeMount } from '@monaco-editor/react';
import type { editor as MonacoEditor } from 'monaco-editor';

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: 'sql' | 'javascript' | 'redis' | 'markdown';
  height?: string;
  readOnly?: boolean;
  onExecute?: () => void;
  placeholder?: string;
  className?: string;
}

const SQL_KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET',
  'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'INDEX', 'VIEW', 'JOIN',
  'LEFT', 'RIGHT', 'INNER', 'OUTER', 'FULL', 'CROSS', 'ON', 'AND', 'OR',
  'NOT', 'IN', 'EXISTS', 'BETWEEN', 'LIKE', 'IS', 'NULL', 'AS', 'ORDER',
  'BY', 'GROUP', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL', 'DISTINCT',
  'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'ASC', 'DESC', 'PRIMARY', 'KEY',
  'FOREIGN', 'REFERENCES', 'CONSTRAINT', 'DEFAULT', 'CHECK', 'UNIQUE',
  'NOT NULL', 'AUTO_INCREMENT', 'INTEGER', 'TEXT', 'REAL', 'BLOB',
  'VARCHAR', 'CHAR', 'BOOLEAN', 'DATE', 'TIMESTAMP', 'DECIMAL', 'FLOAT',
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'IFNULL', 'CAST',
  'SUBSTR', 'LENGTH', 'UPPER', 'LOWER', 'TRIM', 'REPLACE', 'ROUND',
  'ABS', 'WITH', 'RECURSIVE', 'EXCEPT', 'INTERSECT', 'ROLLBACK', 'COMMIT',
  'BEGIN', 'TRANSACTION', 'SCHEMA', 'DATABASE', 'IF', 'CASCADE', 'RESTRICT',
];

// Track whether SQL autocomplete provider is already registered (global singleton)
let sqlProviderRegistered = false;

export function SqlEditor({
  value,
  onChange,
  language = 'sql',
  height = '160px',
  readOnly = false,
  onExecute,
  placeholder,
  className,
}: SqlEditorProps) {
  const editorRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  // Use ref so Monaco action always calls the latest onExecute
  const onExecuteRef = useRef(onExecute);
  useEffect(() => {
    onExecuteRef.current = onExecute;
  }, [onExecute]);

  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    // Register SQL autocomplete provider only once globally
    if (language === 'sql' && !sqlProviderRegistered) {
      sqlProviderRegistered = true;
      monaco.languages.registerCompletionItemProvider('sql', {
        provideCompletionItems: (model, position) => {
          const word = model.getWordUntilPosition(position);
          const range = {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn,
          };

          const suggestions = SQL_KEYWORDS.map((kw) => ({
            label: kw,
            kind: monaco.languages.CompletionItemKind.Keyword,
            insertText: kw,
            range,
          }));

          return { suggestions };
        },
      });
    }
  }, [language]);

  const handleMount: OnMount = useCallback(
    (editor, monaco) => {
      editorRef.current = editor;

      // Ctrl+Enter to execute — uses ref to always call latest handler
      editor.addAction({
        id: 'execute-query',
        label: 'Execute Query',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
        run: () => onExecuteRef.current?.(),
      });

      // Focus editor on mount
      editor.focus();
    },
    [],
  );

  return (
    <div className={`rounded-md overflow-hidden border ${className ?? ''}`}>
      <Editor
        height={height}
        language={language === 'redis' ? 'plaintext' : language}
        value={value}
        onChange={(v) => onChange(v ?? '')}
        beforeMount={handleBeforeMount}
        onMount={handleMount}
        options={{
          readOnly,
          minimap: { enabled: false },
          lineNumbers: 'on',
          wordWrap: 'on',
          scrollBeyondLastLine: false,
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
          tabSize: 2,
          automaticLayout: true,
          padding: { top: 8, bottom: 8 },
          renderLineHighlight: 'line',
          suggestOnTriggerCharacters: true,
          quickSuggestions: true,
          folding: false,
          glyphMargin: false,
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          overviewRulerBorder: false,
          scrollbar: {
            vertical: 'auto',
            horizontal: 'auto',
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
          },
          placeholder: placeholder,
        }}
        theme="vs-dark"
      />
    </div>
  );
}
