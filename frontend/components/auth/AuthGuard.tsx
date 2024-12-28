"use client";

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';

interface AuthGuardProps {
  children: React.ReactNode;
  requireAuth?: boolean;
}

export function AuthGuard({ children, requireAuth = true }: AuthGuardProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    // Skip redirect if still loading
    if (isLoading) return;

    // If auth is required and user is not authenticated
    if (requireAuth && !isAuthenticated) {
      // Avoid redirect loops
      if (pathname !== '/auth/login') {
        router.push('/auth/login?reason=auth_required');
      }
    }
    
    // If user is authenticated and on login page, redirect to dashboard
    if (isAuthenticated && pathname === '/auth/login') {
      router.push('/dashboard');
    }
  }, [isAuthenticated, isLoading, requireAuth, router, pathname]);

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-3 text-gray-600">Loading...</span>
      </div>
    );
  }

  // Show nothing while redirecting
  if (requireAuth && !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-gray-600">Redirecting to login...</div>
      </div>
    );
  }

  return <>{children}</>;
}