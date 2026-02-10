import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { Toaster } from '@/components/ui/sonner';
import { FloatingKeywords } from '@/components/ui/FloatingKeywords';

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen bg-background relative overflow-hidden">
      {/* Global floating SQL keywords background */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <FloatingKeywords />
      </div>

      <Header onMenuClick={() => setSidebarOpen(true)} />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="md:pl-16 relative z-10">
        <div className="px-6 py-8 md:px-10 md:py-10 max-w-7xl mx-auto">
          <Outlet />
        </div>
      </main>
      <Toaster />
    </div>
  );
}
