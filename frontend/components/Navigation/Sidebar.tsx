"use client";

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  Home, 
  Settings, 
  Users, 
  Database, 
  Eye, 
  FileText,
  ChevronDown,
  ChevronRight,
  Shield,
  LogOut,
  FolderOpen
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';

interface NavigationItem {
  name: string;
  href?: string;
  icon: React.ReactNode;
  children?: NavigationItem[];
  adminOnly?: boolean;
}

const navigationItems: NavigationItem[] = [
  {
    name: 'DocuGenius',
    href: '/dashboard',
    icon: <Home className="h-5 w-5" />
  },
  {
    name: 'Raglior',
    href: '/raglior',
    icon: <FileText className="h-5 w-5" />
  },
  {
    name: 'Operations',
    icon: <Settings className="h-5 w-5" />,
    children: [
      // {
      //   name: 'Configure Metadata Details',
      //   href: '/operations/configure-metadata',
      //   icon: <Settings className="h-4 w-4" />
      // },
      {
        name: 'Metadata Groups',
        href: '/operations/metadata-groups',
        icon: <Users className="h-4 w-4" />
      },
      {
        name: 'Collections',
        href: '/operations/collections',
        icon: <FolderOpen className="h-4 w-4" />
      },
      {
        name: 'User Management',
        href: '/operations/users',
        icon: <Users className="h-4 w-4" />,
        adminOnly: true
      }
    ]
  }
];

export function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();
  const [expandedItems, setExpandedItems] = useState<string[]>(['Operations']);
  
  const handleLogout = async () => {
    await logout();
    router.push('/auth/login');
  };

  const toggleExpanded = (itemName: string) => {
    setExpandedItems(prev => 
      prev.includes(itemName) 
        ? prev.filter(name => name !== itemName)
        : [...prev, itemName]
    );
  };

  const isActive = (href: string) => {
    return pathname === href || pathname.startsWith(href + '/');
  };

  const shouldShowItem = (item: NavigationItem): boolean => {
    if (item.adminOnly && user?.role !== 'admin') {
      return false;
    }
    return true;
  };

  const renderNavigationItem = (item: NavigationItem, level: number = 0) => {
    if (!shouldShowItem(item)) {
      return null;
    }

    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedItems.includes(item.name);
    const itemIsActive = item.href ? isActive(item.href) : false;

    if (hasChildren) {
      return (
        <div key={item.name} className="space-y-1">
          <button
            onClick={() => toggleExpanded(item.name)}
            className={cn(
              "flex items-center justify-between w-full px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200",
              level === 0 ? "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground" : "text-sidebar-foreground/70 hover:bg-sidebar-accent/70 hover:text-sidebar-accent-foreground",
              level > 0 && "ml-4"
            )}
          >
            <div className="flex items-center gap-3">
              <div className="transition-transform duration-200 group-hover:scale-110">{item.icon}</div>
              <span className="transition-all duration-200">{item.name}</span>
            </div>
            {isExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>
          
          {isExpanded && (
            <div className="mt-1 space-y-1">
              {item.children?.map(child => renderNavigationItem(child, level + 1))}
            </div>
          )}
        </div>
      );
    }

    return (
      <Link
        key={item.name}
        href={item.href!}
        className={cn(
          "flex items-center gap-3 px-4 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 relative group",
          level === 0 ? "" : "ml-4",
          itemIsActive 
            ? "bg-gradient-to-r from-sidebar-primary to-sidebar-primary/90 text-sidebar-primary-foreground shadow-md" 
            : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        )}
      >
        <div className="transition-transform duration-200 group-hover:scale-110">{item.icon}</div>
        <span className="transition-all duration-200">{item.name}</span>
        {item.adminOnly && (
          <Shield className="h-3 w-3 text-sidebar-primary ml-auto opacity-70" />
        )}
      </Link>
    );
  };

  return (
    <div className="flex flex-col h-full bg-sidebar-background text-sidebar-foreground border-r border-sidebar-border w-64 flex-shrink-0">
      {/* Header */}
      <div className="flex items-center justify-center px-4 py-6 border-b border-sidebar-border">
        <div className="flex items-center justify-center">
          <img src="/raglior-logo.svg" alt="Raglior Logo" className="h-10 w-auto max-w-full" />
        </div>
      </div>
      
      {/* Navigation */}
      <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
        {navigationItems.map(item => renderNavigationItem(item))}
      </nav>

      {/* User Info with Logout */}
      {user && (
        <div className="px-4 py-4 border-t border-sidebar-border bg-sidebar-accent/30">
          <div className="flex items-center gap-3 mb-3">
            <div className="h-9 w-9 bg-gradient-to-br from-sidebar-primary to-sidebar-primary/80 rounded-lg flex items-center justify-center shadow-md">
              <span className="text-sm font-semibold text-sidebar-primary-foreground">
                {user.username.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-sidebar-foreground truncate">
                {user.username}
              </p>
              <p className="text-xs text-sidebar-foreground/60 truncate capitalize">
                {user.role}
              </p>
            </div>
          </div>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={handleLogout}
            className="w-full justify-start text-sidebar-foreground/70 hover:text-red-600 hover:bg-red-50 px-3 py-2 rounded-lg transition-all duration-200 group"
          >
            <LogOut className="h-4 w-4 mr-2 transition-transform duration-200 group-hover:scale-110" />
            Logout
          </Button>
        </div>
      )}
    </div>
  );
} 