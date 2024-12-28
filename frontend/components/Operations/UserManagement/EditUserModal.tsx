import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiService } from '@/services/api';
import { FORM_KEYS } from '@/utils/formPersistence';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

interface EditUserModalProps {
  user: User;
  isOpen: boolean;
  onClose: () => void;
  onUserUpdated: () => void;
}

interface EditUserFormData {
  email: string;
  role: 'admin' | 'user' | 'viewer';
  isActive: boolean;
}

export function EditUserModal({ user, isOpen, onClose, onUserUpdated }: EditUserModalProps) {
  const [formData, setFormData] = useState<EditUserFormData>(() => {
    // Restore form data from localStorage if available
    const saved = localStorage.getItem(FORM_KEYS.EDIT_USER(user.id));
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.warn('Failed to parse saved edit form data:', e);
      }
    }
    return {
      email: user.email,
      role: user.role,
      isActive: user.is_active
    };
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Save form data to localStorage on changes
  useEffect(() => {
    if (isOpen) {
      localStorage.setItem(FORM_KEYS.EDIT_USER(user.id), JSON.stringify(formData));
    }
  }, [formData, isOpen, user.id]);

  // Reset form data when user changes
  useEffect(() => {
    setFormData({
      email: user.email,
      role: user.role,
      isActive: user.is_active
    });
  }, [user.id, user.email, user.role, user.is_active]);

  // Debug logging to track form state changes
  useEffect(() => {
    console.log('🔄 EditUserModal re-rendered, formData:', formData);
  }, [formData]);

  useEffect(() => {
    console.log('🔄 EditUserModal isOpen changed:', isOpen);
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    setLoading(true);
    setError('');

    try {
      // Update user with all changes at once
      await apiService.updateUser(user.id, {
        email: formData.email,
        role: formData.role,
        is_active: formData.isActive
      });

      // Clear saved form data on success
      localStorage.removeItem(FORM_KEYS.EDIT_USER(user.id));
      onUserUpdated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    // Clear saved form data
    localStorage.removeItem(FORM_KEYS.EDIT_USER(user.id));
    onClose();
  };

  const handleInputChange = (field: keyof EditUserFormData, value: string | boolean) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">Edit User</h2>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Username (readonly) */}
          <div>
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={user.username}
              disabled
              className="bg-gray-50"
            />
            <p className="text-xs text-gray-500 mt-1">Username cannot be changed</p>
          </div>

          {/* Email */}
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              placeholder="Enter email address"
            />
          </div>

          {/* Role */}
          <div>
            <Label htmlFor="role">Role</Label>
            <select
              id="role"
              value={formData.role}
              onChange={(e) => handleInputChange('role', e.target.value as 'admin' | 'user' | 'viewer')}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
            >
              <option value="user">User</option>
              <option value="viewer">Viewer</option>
              <option value="admin">Administrator</option>
            </select>
          </div>

          {/* Status */}
          <div>
            <Label>Status</Label>
            <div className="flex items-center gap-2 mt-2">
              <input
                type="checkbox"
                id="isActive"
                checked={formData.isActive}
                onChange={(e) => handleInputChange('isActive', e.target.checked)}
                className="h-4 w-4 text-blue-600"
              />
              <label htmlFor="isActive" className="text-sm text-gray-700">
                Active User
              </label>
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 p-3 rounded">
              {error}
            </div>
          )}

          {/* Buttons */}
          <div className="flex justify-end gap-3 pt-4">
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleClose}
              disabled={loading}
              className="border-gray-300 text-gray-700 hover:bg-gray-50 btn-professional-subtle"
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={loading}
              className="min-w-[100px] bg-blue-600 hover:bg-blue-700 text-white btn-professional"
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
} 