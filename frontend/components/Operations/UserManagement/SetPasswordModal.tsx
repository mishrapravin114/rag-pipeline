import { useState, useEffect } from 'react';
import { X, Eye, EyeOff, Key } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { FORM_KEYS } from '@/utils/formPersistence';

interface SetPasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  userId: number;
  username: string;
  onPasswordSet: () => void;
}

interface SetPasswordFormData {
  password: string;
  confirmPassword: string;
}

export function SetPasswordModal({ 
  isOpen, 
  onClose, 
  userId,
  username,
  onPasswordSet 
}: SetPasswordModalProps) {
  const [formData, setFormData] = useState<SetPasswordFormData>(() => {
    // Restore form data from localStorage if available
    const saved = localStorage.getItem(FORM_KEYS.SET_PASSWORD(userId));
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.warn('Failed to parse saved password form data:', e);
      }
    }
    return {
      password: '',
      confirmPassword: ''
    };
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState<{ password?: string; confirmPassword?: string }>({});

  // Save form data to localStorage on changes
  useEffect(() => {
    if (isOpen && (formData.password || formData.confirmPassword)) {
      localStorage.setItem(FORM_KEYS.SET_PASSWORD(userId), JSON.stringify(formData));
    }
  }, [formData, isOpen, userId]);

  // Debug logging to track form state changes
  useEffect(() => {
    console.log('🔄 SetPasswordModal re-rendered, formData:', formData);
  }, [formData]);

  useEffect(() => {
    console.log('🔄 SetPasswordModal isOpen changed:', isOpen);
  }, [isOpen]);

  if (!isOpen) return null;

  const validateForm = () => {
    const newErrors: { password?: string; confirmPassword?: string } = {};

    if (!formData.password.trim()) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (!formData.confirmPassword.trim()) {
      newErrors.confirmPassword = 'Please confirm password';
    } else if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) return;

    setLoading(true);
    try {
      await apiService.setUserPassword(userId, formData.password);
      
      // Clear saved form data on success
      localStorage.removeItem(FORM_KEYS.SET_PASSWORD(userId));
      onPasswordSet();
      handleClose();
      
      // Show success message
      toast.success(`Password successfully set for user: ${username}`);
    } catch (error) {
      // Show error message in toast instead of alert
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      
      // Check if it's a 404 error and provide a more user-friendly message
      if (errorMessage.includes('404')) {
        toast.error('Password update feature is not available. Please contact your administrator.');
      } else {
        toast.error(`Failed to set password: ${errorMessage}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    // Clear saved form data
    localStorage.removeItem(FORM_KEYS.SET_PASSWORD(userId));
    setFormData({
      password: '',
      confirmPassword: ''
    });
    setErrors({});
    setShowPassword(false);
    setShowConfirmPassword(false);
    onClose();
  };

  const handleInputChange = (field: 'password' | 'confirmPassword', value: string) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center gap-2">
            <Key className="h-5 w-5 text-gray-600" />
            <h2 className="text-xl font-semibold text-gray-900">Set Password</h2>
          </div>
          <button onClick={handleClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <p className="text-sm text-blue-800">
              Setting password for user: <strong>{username}</strong>
            </p>
          </div>

          {/* Password */}
          <div>
            <Label htmlFor="password">New Password</Label>
            <div className="relative mt-1">
              <Input
                id="password"
                type={showPassword ? "text" : "password"}
                value={formData.password}
                onChange={(e) => handleInputChange('password', e.target.value)}
                placeholder="Enter new password"
                className={errors.password ? 'border-red-500' : ''}
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-2 text-gray-500 hover:text-gray-700"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {errors.password && (
              <p className="text-sm text-red-500 mt-1">{errors.password}</p>
            )}
          </div>

          {/* Confirm Password */}
          <div>
            <Label htmlFor="confirmPassword">Confirm Password</Label>
            <div className="relative mt-1">
              <Input
                id="confirmPassword"
                type={showConfirmPassword ? "text" : "password"}
                value={formData.confirmPassword}
                onChange={(e) => handleInputChange('confirmPassword', e.target.value)}
                placeholder="Confirm new password"
                className={errors.confirmPassword ? 'border-red-500' : ''}
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-2 top-2 text-gray-500 hover:text-gray-700"
              >
                {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="text-sm text-red-500 mt-1">{errors.confirmPassword}</p>
            )}
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-xs text-amber-800">
              <strong>Note:</strong> The user will not be required to change this password on login.
            </p>
          </div>

          {/* Buttons */}
          <div className="flex gap-3 pt-4">
            <Button 
              type="button" 
              variant="outline" 
              onClick={handleClose}
              className="flex-1 border-gray-300 text-gray-700 hover:bg-gray-50 btn-professional-subtle"
              disabled={loading}
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white btn-professional"
              disabled={loading}
            >
              {loading ? 'Setting Password...' : 'Set Password'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}