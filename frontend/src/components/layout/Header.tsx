import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Menu } from 'lucide-react';
import logoImg from '@/assets/logo.png';
import { Button } from '@/components/ui/button';
import { ThemeToggle } from './ThemeToggle';
import { LanguageSwitcher } from './LanguageSwitcher';
import { UserMenu } from './UserMenu';
import { TooltipProvider } from '@/components/ui/tooltip';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { t } = useTranslation();

  return (
    <header className="fixed top-0 z-50 w-full h-14 bg-card/95 backdrop-blur-md border-b border-border shadow-noble-sm">
      <div className="flex h-full items-center px-4 md:px-6 gap-3">
        {/* Mobile menu button */}
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden rounded-xl"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </Button>

        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-3 font-semibold text-lg"
        >
          <img
            src={logoImg}
            alt="Logo"
            width={36}
            height={36}
            className="h-9 w-9 object-contain drop-shadow-sm"
            style={{ imageRendering: 'auto' }}
          />
          <span className="hidden md:inline text-foreground">
            {t('common:branding.name')}
          </span>
        </Link>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Right side actions */}
        <TooltipProvider delayDuration={300}>
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <LanguageSwitcher />
            <UserMenu />
          </div>
        </TooltipProvider>
      </div>
    </header>
  );
}
