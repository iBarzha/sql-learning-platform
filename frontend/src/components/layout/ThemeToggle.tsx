import { usePreferencesStore } from '@/store/preferencesStore';
import { useTranslation } from 'react-i18next';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip';

type Theme = 'system' | 'light' | 'dark';

const themeOrder: Theme[] = ['system', 'light', 'dark'];

const themeIcons: Record<Theme, React.ReactNode> = {
  system: <Monitor className="h-4 w-4" />,
  light: <Sun className="h-4 w-4" />,
  dark: <Moon className="h-4 w-4" />,
};

const themeI18nKeys: Record<Theme, string> = {
  system: 'common:theme.system',
  light: 'common:theme.light',
  dark: 'common:theme.dark',
};

export function ThemeToggle() {
  const { t } = useTranslation();
  const { theme, setTheme } = usePreferencesStore();

  const cycleTheme = () => {
    const currentIndex = themeOrder.indexOf(theme);
    const nextIndex = (currentIndex + 1) % themeOrder.length;
    setTheme(themeOrder[nextIndex]);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="rounded-xl"
            onClick={cycleTheme}
            aria-label={t(themeI18nKeys[theme])}
          >
            {themeIcons[theme]}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{t(themeI18nKeys[theme])}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
