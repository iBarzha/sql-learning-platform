import type * as Monaco from 'monaco-editor';

export const NOBLE_DARK = 'noble-dark';
export const NOBLE_LIGHT = 'noble-light';

const nobleDarkTheme: Monaco.editor.IStandaloneThemeData = {
  base: 'vs-dark',
  inherit: true,
  colors: {
    'editor.background': '#1d1f18',
    'editor.foreground': '#c8d1bc',
    'editor.lineHighlightBackground': '#252820',
    'editor.selectionBackground': '#839a6440',
    'editorCursor.foreground': '#839a64',
    'editorLineNumber.foreground': '#8a8b8c',
    'editorLineNumber.activeForeground': '#c8d1bc',
    'editor.inactiveSelectionBackground': '#839a6420',
    'editorIndentGuide.background': '#2a2d24',
    'editorGutter.background': '#1d1f18',
    'editorWidget.background': '#252820',
    'editorWidget.border': '#333828',
    'input.background': '#252820',
    'input.foreground': '#c8d1bc',
    'input.border': '#333828',
    'dropdown.background': '#252820',
    'list.activeSelectionBackground': '#839a6440',
    'list.hoverBackground': '#2a2d24',
    'list.focusBackground': '#839a6430',
  },
  rules: [
    { token: 'comment', foreground: '8a8b8c', fontStyle: 'italic' },
    { token: 'string', foreground: 'c8d1bc' },
    { token: 'string.sql', foreground: 'c8d1bc' },
    { token: 'keyword', foreground: '839a64', fontStyle: 'bold' },
    { token: 'keyword.sql', foreground: '839a64', fontStyle: 'bold' },
    { token: 'number', foreground: 'db574a' },
    { token: 'number.float', foreground: 'db574a' },
    { token: 'type', foreground: 'c8d1bc' },
    { token: 'type.identifier', foreground: 'c8d1bc' },
    { token: 'predefined.function', foreground: '839a64' },
    { token: 'function', foreground: '839a64' },
    { token: 'variable', foreground: 'c8d1bc' },
    { token: 'variable.predefined', foreground: 'c8d1bc' },
    { token: 'operator', foreground: '8a8b8c' },
    { token: 'operator.sql', foreground: '8a8b8c' },
    { token: 'constant', foreground: 'db574a' },
    { token: 'predefined.sql', foreground: '839a64' },
    { token: 'identifier', foreground: 'c8d1bc' },
    { token: 'delimiter', foreground: '8a8b8c' },
  ],
};

const nobleLightTheme: Monaco.editor.IStandaloneThemeData = {
  base: 'vs',
  inherit: true,
  colors: {
    'editor.background': '#f5f5f0',
    'editor.foreground': '#2a2d24',
    'editor.lineHighlightBackground': '#eef0e8',
    'editor.selectionBackground': '#839a6430',
    'editorCursor.foreground': '#839a64',
    'editorLineNumber.foreground': '#8a8b8c',
    'editorLineNumber.activeForeground': '#2a2d24',
    'editor.inactiveSelectionBackground': '#839a6415',
    'editorIndentGuide.background': '#e0e2da',
    'editorGutter.background': '#f5f5f0',
    'editorWidget.background': '#f5f5f0',
    'editorWidget.border': '#e0e2da',
    'input.background': '#ffffff',
    'input.foreground': '#2a2d24',
    'input.border': '#e0e2da',
    'dropdown.background': '#ffffff',
    'list.activeSelectionBackground': '#839a6430',
    'list.hoverBackground': '#eef0e8',
    'list.focusBackground': '#839a6420',
  },
  rules: [
    { token: 'comment', foreground: '8a8b8c', fontStyle: 'italic' },
    { token: 'string', foreground: '5a6848' },
    { token: 'string.sql', foreground: '5a6848' },
    { token: 'keyword', foreground: '566b38', fontStyle: 'bold' },
    { token: 'keyword.sql', foreground: '566b38', fontStyle: 'bold' },
    { token: 'number', foreground: 'c44a3e' },
    { token: 'number.float', foreground: 'c44a3e' },
    { token: 'type', foreground: '2a2d24' },
    { token: 'type.identifier', foreground: '2a2d24' },
    { token: 'predefined.function', foreground: '566b38' },
    { token: 'function', foreground: '566b38' },
    { token: 'variable', foreground: '2a2d24' },
    { token: 'variable.predefined', foreground: '2a2d24' },
    { token: 'operator', foreground: '8a8b8c' },
    { token: 'operator.sql', foreground: '8a8b8c' },
    { token: 'constant', foreground: 'c44a3e' },
    { token: 'predefined.sql', foreground: '566b38' },
    { token: 'identifier', foreground: '2a2d24' },
    { token: 'delimiter', foreground: '8a8b8c' },
  ],
};

/**
 * Registers both NobleFinance Monaco editor themes.
 * Call this once after Monaco is loaded, before creating any editors.
 */
export function registerNobleThemes(
  monaco: typeof Monaco
): void {
  monaco.editor.defineTheme(NOBLE_DARK, nobleDarkTheme);
  monaco.editor.defineTheme(NOBLE_LIGHT, nobleLightTheme);
}
