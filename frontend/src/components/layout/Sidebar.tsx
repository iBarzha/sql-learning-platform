import { NavLink } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { useTranslation } from 'react-i18next';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  BookOpen,
  GraduationCap,
  Users,
  UserPlus,
  Settings,
  Database,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip';
import type { LucideIcon } from 'lucide-react';
import logoImg from '@/assets/logo.png';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  to: string;
  icon: LucideIcon;
  labelKey: string;
  roles?: ('student' | 'instructor' | 'admin')[];
}

const navItems: NavItem[] = [
  {
    to: '/',
    icon: LayoutDashboard,
    labelKey: 'common:navigation.dashboard',
  },
  {
    to: '/courses',
    icon: BookOpen,
    labelKey: 'common:navigation.courses',
  },
  {
    to: '/sandbox',
    icon: Database,
    labelKey: 'common:navigation.sandbox',
  },
  {
    to: '/my-courses',
    icon: GraduationCap,
    labelKey: 'common:navigation.myCourses',
    roles: ['instructor', 'admin'],
  },
  {
    to: '/students',
    icon: Users,
    labelKey: 'common:navigation.students',
    roles: ['instructor', 'admin'],
  },
  {
    to: '/users',
    icon: UserPlus,
    labelKey: 'common:navigation.users',
    roles: ['admin'],
  },
  {
    to: '/settings',
    icon: Settings,
    labelKey: 'common:navigation.settings',
    roles: ['admin'],
  },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user } = useAuthStore();
  const { t } = useTranslation();

  const filteredItems = navItems.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-14 z-30 h-[calc(100vh-3.5rem)]',
          'hidden md:flex flex-col',
          'w-16 hover:w-56 transition-all duration-300 ease-in-out overflow-hidden',
          'bg-sidebar-bg border-r border-sidebar-border shadow-noble-sm',
          'group/sidebar'
        )}
      >
        <nav className="flex-1 flex flex-col gap-1 px-2 py-4">
          <TooltipProvider delayDuration={200}>
            {filteredItems.map((item) => {
              const Icon = item.icon;
              const label = t(item.labelKey);

              return (
                <Tooltip key={item.to}>
                  <TooltipTrigger asChild>
                    <div className="w-full">
                      <NavLink
                        to={item.to}
                        end={item.to === '/'}
                        className={({ isActive }) =>
                          cn(
                            'flex items-center h-12 w-full rounded-xl transition-colors duration-200',
                            isActive
                              ? 'bg-primary text-primary-foreground shadow-noble-sm'
                              : 'text-sidebar-muted-foreground hover:bg-secondary hover:text-foreground'
                          )
                        }
                      >
                        <div className="flex items-center justify-center w-12 shrink-0">
                          <Icon className="h-5 w-5" />
                        </div>
                        <span
                          className={cn(
                            'text-sm font-medium whitespace-nowrap',
                            'opacity-0 group-hover/sidebar:opacity-100',
                            'transition-opacity duration-200 delay-75'
                          )}
                        >
                          {label}
                        </span>
                      </NavLink>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent
                    side="right"
                    className="group-hover/sidebar:hidden"
                  >
                    <p>{label}</p>
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </TooltipProvider>
        </nav>

        {/* Bottom branding */}
        <div className="px-2 py-4 border-t border-border/30">
          <div className="flex items-center h-10 overflow-hidden">
            <div className="flex items-center justify-center w-12 shrink-0">
              <img
                src={logoImg}
                alt="Logo"
                width={32}
                height={32}
                className="h-8 w-8 object-contain"
              />
            </div>
            <span
              className={cn(
                'text-xs font-semibold text-sidebar-muted-foreground whitespace-nowrap',
                'opacity-0 group-hover/sidebar:opacity-100',
                'transition-opacity duration-200 delay-75'
              )}
            >
              {t('common:branding.name')}
            </span>
          </div>
        </div>
      </aside>

      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-foreground/20 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-0 z-50 h-full w-72',
          'bg-sidebar-bg border-r border-sidebar-border shadow-noble-lg',
          'flex flex-col md:hidden',
          'transition-transform duration-300 ease-out',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Mobile header */}
        <div className="flex items-center justify-between h-14 px-4 border-b border-border/30">
          <div className="flex items-center gap-3">
            <img
              src={logoImg}
              alt="Logo"
              width={32}
              height={32}
              className="h-8 w-8 object-contain"
            />
            <span className="font-semibold text-sm">{t('common:branding.name')}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="rounded-xl"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Mobile navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {filteredItems.map((item) => {
            const Icon = item.icon;
            const label = t(item.labelKey);

            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors duration-200',
                    isActive
                      ? 'bg-primary text-primary-foreground shadow-noble-sm'
                      : 'text-sidebar-muted-foreground hover:bg-secondary hover:text-foreground'
                  )
                }
              >
                <Icon className="h-5 w-5" />
                {label}
              </NavLink>
            );
          })}
        </nav>

        {/* Mobile user info */}
        <div className="border-t border-border/30 p-4">
          <div className="flex items-center gap-3">
            {user?.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.full_name}
                className="h-10 w-10 rounded-full object-cover"
              />
            ) : (
              <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-sm font-semibold text-primary">
                  {user?.first_name?.[0]}
                  {user?.last_name?.[0]}
                </span>
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="font-medium truncate text-sm">{user?.full_name}</p>
              <p className="text-xs text-muted-foreground capitalize">
                {user?.role}
              </p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
