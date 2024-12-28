"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { UserManagementTable } from '@/components/Operations/UserManagement/UserManagementTable';
import { CreateUserModal } from '@/components/Operations/UserManagement/CreateUserModal';
import { UserAnalytics } from '@/components/Operations/UserManagement/UserAnalytics';
import { Button } from '@/components/ui/button';
import { Plus, Shield, AlertTriangle } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { apiService } from '@/services/api';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

interface UserAnalyticsData {
  total_users: number;
  active_users: number;
  inactive_users: number;
  role_distribution: Record<string, number>;
  recent_registrations: number;
  active_last_30_days: number;
  generated_at: string;
}

export default function UserManagementPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [analytics, setAnalytics] = useState<UserAnalyticsData | null>(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const { user, token, logout } = useAuth();
  const router = useRouter();

  // Check admin access
  useEffect(() => {
    if (user && user.role !== 'admin') {
      router.push('/dashboard');
      return;
    }
  }, [user, router]);

  // Fetch users and analytics
  const fetchData = async () => {
    if (!token || !user) {
      console.log('Skipping fetch: token or user not available');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      console.log('Fetching users data...');
      // Fetch users using API service
      const usersData = await apiService.getUsers();
      console.log('Users data received:', usersData.length, 'users');
      setUsers(usersData);

      // Fetch analytics using API service
      console.log('Fetching analytics data...');
      try {
        const analyticsData = await apiService.getUserAnalytics();
        console.log('Analytics data received');
        setAnalytics(analyticsData);
      } catch (analyticsError) {
        console.warn('Analytics fetch failed:', analyticsError);
        // Analytics is optional, so we don't throw an error here
      }

    } catch (err) {
      console.error('fetchData error:', err);
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user && token) {
      fetchData();
    }
  }, [user, token]);

  // Auto-refresh data every 30 seconds
  useEffect(() => {
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [token]);

  const handleUserCreated = () => {
    setIsCreateModalOpen(false);
    fetchData(); // Refresh data
  };

  const handleUserUpdated = () => {
    fetchData(); // Refresh data
  };

  // Show loading state
  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Loading user management...</span>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Data</h2>
            <p className="text-gray-600 mb-4">{error}</p>
            <Button onClick={fetchData} variant="outline">
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  // Admin access denied (shouldn't reach here due to redirect, but safety check)
  if (!user || user.role !== 'admin') {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <Shield className="h-12 w-12 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Access Denied</h2>
            <p className="text-gray-600">You need admin privileges to access this page.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="page-title">User Management</h1>
          <p className="text-blue-700 mt-1">Manage user accounts, roles, and permissions</p>
        </div>
        <Button 
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white btn-professional"
        >
          <Plus className="h-4 w-4" />
          Create User
        </Button>
      </div>

      {/* Analytics Dashboard */}
      {analytics && (
        <div className="mb-8">
          <UserAnalytics data={analytics} />
        </div>
      )}

      {/* User Management Table */}
      <div className="bg-white rounded-lg shadow-sm border">
        <UserManagementTable 
          users={users}
          onUserUpdated={handleUserUpdated}
        />
      </div>

      {/* Create User Modal */}
      <CreateUserModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onUserCreated={handleUserCreated}
      />
      </div>
    </div>
  );
} 