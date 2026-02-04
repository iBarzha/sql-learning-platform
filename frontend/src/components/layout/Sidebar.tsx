import { NavLink } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  BookOpen,
  GraduationCap,
  Users,
  Settings,
  X,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
  roles?: ('student' | 'instructor' | 'admin')[];
}

const navItems: NavItem[] = [
  {
    to: '/',
    icon: <LayoutDashboard className="h-4 w-4" />,
    label: 'Dashboard',
  },
  {
    to: '/courses',
    icon: <BookOpen className="h-4 w-4" />,
    label: 'Courses',
  },
  {
    to: '/my-courses',
    icon: <GraduationCap className="h-4 w-4" />,
    label: 'My Courses',
    roles: ['instructor'],
  },
  {
    to: '/students',
    icon: <Users className="h-4 w-4" />,
    label: 'Students',
    roles: ['instructor', 'admin'],
  },
  {
    to: '/settings',
    icon: <Settings className="h-4 w-4" />,
    label: 'Settings',
    roles: ['admin'],
  },
];

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user } = useAuthStore();

  const filteredItems = navItems.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/80 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed left-0 top-14 z-40 h-[calc(100vh-3.5rem)] w-64 border-r bg-background transition-transform duration-200 md:translate-x-0',
          isOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-full flex-col">
          {/* Mobile close button */}
          <div className="flex items-center justify-end p-2 md:hidden">
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 p-2">
            {filteredItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )
                }
              >
                {item.icon}
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* User info */}
          <div className="border-t p-4">
            <div className="text-sm">
              <p className="font-medium">{user?.full_name}</p>
              <p className="text-muted-foreground capitalize">{user?.role}</p>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
