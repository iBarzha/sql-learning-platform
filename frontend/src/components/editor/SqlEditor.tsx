import { useRef, useCallback, useEffect } from 'react';
import Editor, { type OnMount, type BeforeMount } from '@monaco-editor/react';
import type { editor as MonacoEditor } from 'monaco-editor';
import { usePreferencesStore } from '@/store/preferencesStore';
import { registerNobleThemes, NOBLE_DARK, NOBLE_LIGHT } from './monacoThemes';

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

let sqlProviderRegistered = false;
let themesRegistered = false;

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
  const onExecuteRef = useRef(onExecute);
  const resolvedTheme = usePreferencesStore((s) => s.resolvedTheme);

  useEffect(() => {
    onExecuteRef.current = onExecute;
  }, [onExecute]);

  // Dispose editor on unmount to prevent memory leaks
  useEffect(() => {
    return () => {
      editorRef.current?.dispose();
    };
  }, []);

  const monacoTheme = resolvedTheme === 'dark' ? NOBLE_DARK : NOBLE_LIGHT;

  const handleBeforeMount: BeforeMount = useCallback((monaco) => {
    if (!themesRegistered) {
      registerNobleThemes(monaco);
      themesRegistered = true;
    }

    if (language === 'sql' && !sqlProviderRegistered) {
      sqlProviderRegistered = true;
      monaco.languages.registerCompletionItemProvider('sql', {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        provideCompletionItems: (model: any, position: any) => {
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

      editor.addAction({
        id: 'execute-query',
        label: 'Execute Query',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter],
        run: () => onExecuteRef.current?.(),
      });

      editor.focus();
    },
    [],
  );

  return (
    <div className={`rounded-xl overflow-hidden border border-border/50 ${className ?? ''}`}>
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
        theme={monacoTheme}
      />
    </div>
  );
}
