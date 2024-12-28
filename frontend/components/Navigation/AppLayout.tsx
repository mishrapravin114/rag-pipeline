"use client";

import { useState } from 'react';
import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { cn } from '@/lib/utils';
import { AuthGuard } from '@/components/auth/AuthGuard';
import { SessionManager } from '@/components/SessionManager';

interface AppLayoutProps {
  children: React.ReactNode;
}

export function AppLayout({ children }: AppLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const pathname = usePathname();

  // List of routes that should use the app layout
  const protectedRoutes = ['/dashboard', '/operations', '/insightxai'];
  const shouldUseLayout = protectedRoutes.some(route => pathname.startsWith(route));

  // Don't render layout for auth pages
  if (!shouldUseLayout) {
    return <>{children}</>;
  }

  // Wrap protected routes with AuthGuard and SessionManager
  return (
    <AuthGuard requireAuth={true}>
      <SessionManager>
        <div className="h-screen flex overflow-hidden bg-gray-50">
        {/* Sidebar for desktop */}
        <div className={cn(
          "hidden lg:flex lg:flex-shrink-0",
          "w-64"
        )}>
          <Sidebar />
        </div>

        {/* Mobile sidebar overlay */}
        {sidebarOpen && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div 
              className="fixed inset-0 bg-gray-600 bg-opacity-75"
              onClick={() => setSidebarOpen(false)}
            />
            <div className="relative flex flex-col w-64 bg-white h-full">
              <Sidebar />
            </div>
          </div>
        )}

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Header */}
          <Header onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
          
          {/* Page content */}
          <main className="flex-1 overflow-auto focus:outline-none">
            <div className="relative h-full">
              {children}
            </div>
          </main>
        </div>
      </div>
      </SessionManager>
    </AuthGuard>
  );
} 