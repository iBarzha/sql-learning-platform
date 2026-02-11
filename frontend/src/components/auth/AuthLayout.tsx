import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import logoImg from '@/assets/logo.png';
import { FloatingKeywords } from '@/components/ui/FloatingKeywords';

interface AuthLayoutProps {
  children: ReactNode;
  mobileTaglineKey?: string;
}

export function AuthLayout({ children, mobileTaglineKey }: AuthLayoutProps) {
  const { t } = useTranslation(['auth', 'common']);

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-primary/10 via-background to-primary/5">
      {/* Dot grid overlay */}
      <div className="absolute inset-0 auth-grid-pattern" />

      {/* Floating SQL keywords */}
      <FloatingKeywords />

      {/* Centered content */}
      <div className="relative z-10 min-h-screen flex flex-col items-center justify-center p-6 lg:p-12">
        {/* Branding */}
        <div className="flex items-center gap-3 mb-8">
          <img
            src={logoImg}
            alt="Logo"
            width={44}
            height={44}
            className="h-11 w-11 object-contain drop-shadow-md"
          />
          <span className="text-lg font-semibold text-foreground">
            {t('auth:branding.name')}
          </span>
        </div>

        {/* Form card */}
        <div className="w-full max-w-md">
          {children}
        </div>

        {/* Bottom tagline */}
        <p className="mt-8 text-muted-foreground text-sm text-center">
          {t(mobileTaglineKey || 'auth:decorative.tagline')}
        </p>
      </div>
    </div>
  );
}
