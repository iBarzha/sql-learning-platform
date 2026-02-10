import { usePreferencesStore } from '@/store/preferencesStore';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip';

type Locale = 'en' | 'uk';

const localeLabels: Record<Locale, string> = {
  en: 'EN',
  uk: 'UK',
};

const localeNames: Record<Locale, string> = {
  en: 'English',
  uk: 'Українська',
};

export function LanguageSwitcher() {
  const { t, i18n } = useTranslation();
  const { locale, setLocale } = usePreferencesStore();

  const toggleLocale = () => {
    const nextLocale: Locale = locale === 'en' ? 'uk' : 'en';
    setLocale(nextLocale);
    i18n.changeLanguage(nextLocale);
  };

  return (
    <TooltipProvider delayDuration={300}>
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="rounded-xl font-semibold text-xs w-10"
            onClick={toggleLocale}
            aria-label={t('common:language.switch')}
          >
            {localeLabels[locale]}
          </Button>
        </TooltipTrigger>
        <TooltipContent>
          <p>{localeNames[locale]}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
