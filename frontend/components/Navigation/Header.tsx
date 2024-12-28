"use client";

import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { 
  LogOut, 
  User, 
  Settings,
  Menu
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface HeaderProps {
  onToggleSidebar?: () => void;
}

export function Header({ onToggleSidebar }: HeaderProps) {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await logout();
    router.push('/auth/login');
  };

  const handleProfile = () => {
    // TODO: Navigate to profile page
    console.log('Navigate to profile');
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'text-purple-600 bg-purple-50';
      case 'user':
        return 'text-blue-600 bg-blue-50';
      case 'viewer':
        return 'text-green-600 bg-green-50';
      default:
        return 'text-gray-600 bg-gray-50';
    }
  };

  return (
    <div className="bg-card border-b border-border px-4 py-3 shadow-sm">
      <div className="flex items-center justify-between">
        {/* Left side - Mobile menu button */}
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleSidebar}
            className="lg:hidden"
          >
            <Menu className="h-5 w-5" />
          </Button>
          
          {/* Page title or breadcrumbs could go here */}
        </div>

        {/* Right side - Empty for now */}
        <div className="flex items-center gap-4">
          {/* User info now moved to sidebar */}
        </div>
      </div>
    </div>
  );
} 