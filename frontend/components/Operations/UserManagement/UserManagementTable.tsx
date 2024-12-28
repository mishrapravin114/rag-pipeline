import { useState, useMemo, useEffect } from 'react';
import { 
  Edit, 
  Key, 
  Trash2, 
  Search, 
  Filter, 
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Shield,
  User,
  Eye,
  Circle
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { EditUserModal } from './EditUserModal';
import { PasswordResetModal } from './PasswordResetModal';
import { SetPasswordModal } from './SetPasswordModal';
import { Badge } from '@/components/ui/badge';
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

interface UserManagementTableProps {
  users: User[];
  onUserUpdated: () => void;
}

type SortField = keyof User;
type SortDirection = 'asc' | 'desc';

export function UserManagementTable({ users, onUserUpdated }: UserManagementTableProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [loadingActions, setLoadingActions] = useState<Record<number, string>>({});
  const [passwordResetData, setPasswordResetData] = useState<{
    isOpen: boolean;
    username: string;
    temporaryPassword: string;
  }>({ isOpen: false, username: '', temporaryPassword: '' });
  
  const [setPasswordData, setSetPasswordData] = useState<{
    isOpen: boolean;
    userId: number;
    username: string;
  }>({ isOpen: false, userId: 0, username: '' });

  // Debug effect to monitor state changes
  useEffect(() => {
    console.log('passwordResetData state changed:', passwordResetData);
  }, [passwordResetData]);

  // Filtering and sorting
  const filteredAndSortedUsers = useMemo(() => {
    let filtered = users.filter(user => {
      // Search filter
      const searchMatch = user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.email.toLowerCase().includes(searchTerm.toLowerCase());
      
      // Role filter
      const roleMatch = roleFilter === 'all' || user.role === roleFilter;
      
      // Status filter
      const statusMatch = statusFilter === 'all' || 
                         (statusFilter === 'active' && user.is_active) ||
                         (statusFilter === 'inactive' && !user.is_active);
      
      return searchMatch && roleMatch && statusMatch;
    });

    // Sort
    filtered.sort((a, b) => {
      let aVal = a[sortField];
      let bVal = b[sortField];

      // Handle null values for last_login
      if (sortField === 'last_login') {
        if (!aVal && !bVal) return 0;
        if (!aVal) return sortDirection === 'asc' ? -1 : 1;
        if (!bVal) return sortDirection === 'asc' ? 1 : -1;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [users, searchTerm, roleFilter, statusFilter, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <ArrowUpDown className="h-4 w-4 text-gray-400" />;
    }
    return sortDirection === 'asc' ? 
      <ArrowUp className="h-4 w-4 text-blue-600" /> : 
      <ArrowDown className="h-4 w-4 text-blue-600" />;
  };

  const getRoleIcon = (role: string) => {
    switch (role) {
      case 'admin':
        return <Shield className="h-4 w-4" />;
      case 'user':
        return <User className="h-4 w-4" />;
      case 'viewer':
        return <Eye className="h-4 w-4" />;
      default:
        return <User className="h-4 w-4" />;
    }
  };

  const getRoleBadgeColor = (role: string) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'user':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'viewer':
        return 'bg-green-100 text-green-800 border-green-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleResetPassword = async (userId: number, username: string) => {
    console.log('Resetting password for user:', username, 'with ID:', userId);
    setLoadingActions(prev => ({ ...prev, [userId]: 'reset' }));
    
    try {
      const data = await apiService.resetUserPassword(userId);
      console.log('Reset password response data:', data);
      
      setPasswordResetData({
        isOpen: true,
        username: username,
        temporaryPassword: data.temporary_password || ''
      });
      console.log('Password reset modal state:', { 
        isOpen: true, 
        username, 
        temporaryPassword: data.temporary_password 
      });
      
      // Don't call onUserUpdated here as it refreshes the page data and might interfere with modal display
    } catch (error) {
      console.error('Reset password error:', error);
      // Still use alert for errors
      alert('Failed to reset password: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setLoadingActions(prev => {
        const newState = { ...prev };
        delete newState[userId];
        return newState;
      });
    }
  };

  const handleSetPassword = (userId: number, username: string) => {
    setSetPasswordData({
      isOpen: true,
      userId: userId,
      username: username
    });
  };

  const handleDeleteUser = async (userId: number, username: string) => {
    if (!confirm(`Are you sure you want to deactivate user "${username}"? This action can be reversed by reactivating the user.`)) {
      return;
    }

    setLoadingActions(prev => ({ ...prev, [userId]: 'delete' }));
    
    try {
      await apiService.deleteUser(userId);
      onUserUpdated();
    } catch (error) {
      alert('Failed to delete user: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setLoadingActions(prev => {
        const newState = { ...prev };
        delete newState[userId];
        return newState;
      });
    }
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="p-6">
      {/* Filters */}
      <div className="flex flex-col md:flex-row gap-4 mb-6">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search by username or email..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>
        
        <div className="flex gap-2">
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="all">All Roles</option>
            <option value="admin">Administrator</option>
            <option value="user">User</option>
            <option value="viewer">Viewer</option>
          </select>
          
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-md text-sm"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-200">
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('id')}
              >
                <div className="flex items-center gap-2">
                  ID {getSortIcon('id')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('username')}
              >
                <div className="flex items-center gap-2">
                  Username {getSortIcon('username')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('email')}
              >
                <div className="flex items-center gap-2">
                  Email {getSortIcon('email')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('role')}
              >
                <div className="flex items-center gap-2">
                  Role {getSortIcon('role')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('is_active')}
              >
                <div className="flex items-center gap-2">
                  Status {getSortIcon('is_active')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('last_login')}
              >
                <div className="flex items-center gap-2">
                  Last Login {getSortIcon('last_login')}
                </div>
              </th>
              <th 
                className="text-left py-3 px-4 font-medium text-gray-900 cursor-pointer hover:bg-gray-50"
                onClick={() => handleSort('created_at')}
              >
                <div className="flex items-center gap-2">
                  Created {getSortIcon('created_at')}
                </div>
              </th>
              <th className="text-right py-3 px-4 font-medium text-gray-900">
                Actions
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredAndSortedUsers.map((user) => (
              <tr key={user.id} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="py-3 px-4 text-sm text-gray-900">{user.id}</td>
                <td className="py-3 px-4 text-sm font-medium text-gray-900">{user.username}</td>
                <td className="py-3 px-4 text-sm text-gray-600">{user.email}</td>
                <td className="py-3 px-4">
                  <Badge className={`flex items-center gap-1 w-fit ${getRoleBadgeColor(user.role)}`}>
                    {getRoleIcon(user.role)}
                    <span className="capitalize">{user.role}</span>
                  </Badge>
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-2">
                    <Circle 
                      className={`h-2 w-2 fill-current ${
                        user.is_active ? 'text-green-500' : 'text-red-500'
                      }`} 
                    />
                    <span className={`text-sm ${
                      user.is_active ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {user.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  {formatDate(user.last_login)}
                </td>
                <td className="py-3 px-4 text-sm text-gray-600">
                  {formatDate(user.created_at)}
                </td>
                <td className="py-3 px-4">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setEditingUser(user)}
                      className="flex items-center gap-1 border-blue-300 text-blue-600 hover:bg-blue-50 hover:text-blue-700 btn-professional-subtle"
                    >
                      <Edit className="h-3 w-3" />
                      Edit
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleResetPassword(user.id, user.username)}
                      disabled={loadingActions[user.id] === 'reset'}
                      className="flex items-center gap-1 border-orange-300 text-orange-600 hover:bg-orange-50 hover:text-orange-700 btn-professional-subtle"
                    >
                      <Key className="h-3 w-3" />
                      {loadingActions[user.id] === 'reset' ? 'Resetting...' : 'Reset'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleSetPassword(user.id, user.username)}
                      className="flex items-center gap-1 border-blue-300 text-blue-600 hover:bg-blue-50 hover:text-blue-700 btn-professional-subtle"
                    >
                      <Key className="h-3 w-3" />
                      Set
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleDeleteUser(user.id, user.username)}
                      disabled={loadingActions[user.id] === 'delete'}
                      className="flex items-center gap-1 border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700 btn-professional-subtle"
                    >
                      <Trash2 className="h-3 w-3" />
                      {loadingActions[user.id] === 'delete' ? 'Deleting...' : 'Delete'}
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {filteredAndSortedUsers.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No users found matching your criteria.
          </div>
        )}
      </div>

      {/* Edit User Modal */}
      {editingUser && (
        <EditUserModal
          user={editingUser}
          isOpen={!!editingUser}
          onClose={() => setEditingUser(null)}
          onUserUpdated={() => {
            setEditingUser(null);
            onUserUpdated();
          }}
        />
      )}

      {/* Password Reset Modal */}
      <PasswordResetModal
        isOpen={passwordResetData.isOpen}
        onClose={() => setPasswordResetData({ isOpen: false, username: '', temporaryPassword: '' })}
        username={passwordResetData.username}
        temporaryPassword={passwordResetData.temporaryPassword}
      />

      {/* Set Password Modal */}
      <SetPasswordModal
        isOpen={setPasswordData.isOpen}
        onClose={() => setSetPasswordData({ isOpen: false, userId: 0, username: '' })}
        userId={setPasswordData.userId}
        username={setPasswordData.username}
        onPasswordSet={() => {
          setSetPasswordData({ isOpen: false, userId: 0, username: '' });
          onUserUpdated();
        }}
      />
    </div>
  );
} 