import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import i18n from '@/i18n';

type Theme = 'system' | 'light' | 'dark';
type Locale = 'en' | 'uk';
type ResolvedTheme = 'light' | 'dark';

interface PreferencesState {
  theme: Theme;
  locale: Locale;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
  setLocale: (locale: Locale) => void;
}

const mediaQuery =
  typeof window !== 'undefined'
    ? window.matchMedia('(prefers-color-scheme: dark)')
    : null;

function getSystemTheme(): ResolvedTheme {
  if (mediaQuery) {
    return mediaQuery.matches ? 'dark' : 'light';
  }
  return 'light';
}

function resolveTheme(theme: Theme): ResolvedTheme {
  if (theme === 'system') {
    return getSystemTheme();
  }
  return theme;
}

function applyThemeClass(resolved: ResolvedTheme): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  if (resolved === 'dark') {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
}

export const usePreferencesStore = create<PreferencesState>()(
  persist(
    (set) => ({
      theme: 'system',
      locale: 'en',
      resolvedTheme: resolveTheme('system'),

      setTheme: (theme: Theme) => {
        const resolved = resolveTheme(theme);
        applyThemeClass(resolved);
        set({ theme, resolvedTheme: resolved });
      },

      setLocale: (locale: Locale) => {
        i18n.changeLanguage(locale);
        document.documentElement.lang = locale;
        set({ locale });
      },
    }),
    {
      name: 'preferences-storage',
      partialize: (state) => ({
        theme: state.theme,
        locale: state.locale,
      }),
      onRehydrateStorage: () => {
        return (state) => {
          if (state) {
            const resolved = resolveTheme(state.theme);
            state.resolvedTheme = resolved;
            applyThemeClass(resolved);
            // Sync i18n and html lang attribute with persisted locale
            i18n.changeLanguage(state.locale);
            document.documentElement.lang = state.locale;
          }
        };
      },
    },
  ),
);

// Apply theme class on initial load
applyThemeClass(usePreferencesStore.getState().resolvedTheme);

// Listen for system theme changes
if (mediaQuery) {
  mediaQuery.addEventListener('change', () => {
    const { theme } = usePreferencesStore.getState();
    if (theme === 'system') {
      const resolved = getSystemTheme();
      applyThemeClass(resolved);
      usePreferencesStore.setState({ resolvedTheme: resolved });
    }
  });
}
