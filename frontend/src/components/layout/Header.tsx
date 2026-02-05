import { Link } from 'react-router-dom';
import { useAuthStore } from '@/store/authStore';
import { Button } from '@/components/ui/button';
import { Database, LogOut, User, Menu } from 'lucide-react';

interface HeaderProps {
  onMenuClick?: () => void;
}

export function Header({ onMenuClick }: HeaderProps) {
  const { user, logout } = useAuthStore();

  return (
    <header className="sticky top-0 z-50 w-full h-16 bg-card/80 backdrop-blur-xl border-b border-border/50 shadow-warm-sm">
      <div className="flex h-full items-center px-6 gap-4">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden rounded-xl"
          onClick={onMenuClick}
        >
          <Menu className="h-5 w-5" />
        </Button>

        <Link to="/" className="flex items-center gap-3 font-semibold text-lg">
          <div className="h-9 w-9 rounded-xl bg-primary flex items-center justify-center shadow-warm-sm">
            <Database className="h-5 w-5 text-primary-foreground" />
          </div>
          <span className="hidden sm:inline text-foreground">SQL Learning</span>
        </Link>

        <div className="flex-1" />

        <div className="flex items-center gap-3">
          <Link to="/profile">
            <Button variant="ghost" size="sm" className="gap-2 rounded-xl hover:bg-secondary">
              <div className="h-7 w-7 rounded-lg bg-primary/10 flex items-center justify-center">
                <User className="h-4 w-4 text-primary" />
              </div>
              <span className="hidden sm:inline font-medium">{user?.full_name || user?.email}</span>
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => logout()}
            title="Sign out"
            className="rounded-xl hover:bg-destructive/10 hover:text-destructive"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </header>
  );
}
