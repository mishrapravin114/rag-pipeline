import { useState, useEffect, useCallback, useRef } from 'react';
import { API_BASE_URL } from '@/config/api';

interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'user' | 'viewer';
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  google_access_token?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface LoginCredentials {
  username: string;
  password: string;
}

interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export function useAuth() {
  const [authState, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  const isInitialized = useRef(false);

  // Initialize auth state from localStorage only once
  useEffect(() => {
    const initializeAuth = async () => {
      if (isInitialized.current) return;
      isInitialized.current = true;

      try {
        const token = localStorage.getItem('access_token');
        const refreshToken = localStorage.getItem('refresh_token');
        const userData = localStorage.getItem('user_data');

        if (token && userData) {
          // First check if the token is expired (client-side check)
          const isTokenExpired = () => {
            try {
              const payload = JSON.parse(atob(token.split('.')[1]));
              const now = Math.floor(Date.now() / 1000);
              return payload.exp <= now;
            } catch (e) {
              return true;
            }
          };

          // If token is expired, try to refresh it
          if (isTokenExpired() && refreshToken) {
            console.log('🔄 Token expired on page load, attempting refresh...');
            const refreshSuccess = await refreshAccessToken(refreshToken);
            if (!refreshSuccess) {
              console.log('❌ Token refresh failed, clearing auth data');
              clearAuthData();
              return;
            }
            // If refresh succeeded, the refreshAccessToken function already updated the auth state
            return;
          }

          // Token appears valid, verify with server
          try {
            const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
              headers: {
                'Authorization': `Bearer ${token}`,
              },
            });

            if (response.ok) {
              const user = await response.json();
              // Update user data if different from stored
              localStorage.setItem('user_data', JSON.stringify(user));
              
              setAuthState({
                user,
                token,
                refreshToken,
                isAuthenticated: true,
                isLoading: false,
              });
              console.log('✅ Auth state restored successfully');
            } else if (response.status === 401 && refreshToken) {
              // Token invalid, try refresh
              console.log('🔄 Token invalid, attempting refresh...');
              const refreshSuccess = await refreshAccessToken(refreshToken);
              if (!refreshSuccess) {
                clearAuthData();
              }
            } else {
              // No refresh token or other error
              clearAuthData();
            }
          } catch (error) {
            console.error('Auth verification error:', error);
            // Try refresh if we have a refresh token
            if (refreshToken) {
              const refreshSuccess = await refreshAccessToken(refreshToken);
              if (!refreshSuccess) {
                clearAuthData();
              }
            } else {
              clearAuthData();
            }
          }
        } else {
          setAuthState(prev => ({ ...prev, isLoading: false }));
        }
      } catch (error) {
        console.error('Auth initialization error:', error);
        clearAuthData();
      }
    };

    initializeAuth();
  }, []); // Empty dependency array to run only once

  const clearAuthData = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_data');
    setAuthState({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  const refreshAccessToken = useCallback(async (refreshToken: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/refresh-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ refresh_token: refreshToken }),
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        
        // Get updated user profile
        const profileResponse = await fetch(`${API_BASE_URL}/api/auth/profile`, {
          headers: {
            'Authorization': `Bearer ${data.access_token}`,
          },
        });

        if (profileResponse.ok) {
          const user = await profileResponse.json();
          localStorage.setItem('user_data', JSON.stringify(user));
          
          setAuthState({
            user,
            token: data.access_token,
            refreshToken: data.refresh_token,
            isAuthenticated: true,
            isLoading: false,
          });
          
          return true;
        }
      }
      
      clearAuthData();
      return false;
    } catch (error) {
      console.error('Token refresh error:', error);
      clearAuthData();
      return false;
    }
  }, [clearAuthData]);

  const login = async (credentials: LoginCredentials): Promise<{ success: boolean; error?: string }> => {
    try {
      setAuthState(prev => ({ ...prev, isLoading: true }));
      
      const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (response.ok) {
        const data: AuthResponse = await response.json();
        
        // Store tokens and user data
        localStorage.setItem('access_token', data.access_token);
        localStorage.setItem('refresh_token', data.refresh_token);
        localStorage.setItem('user_data', JSON.stringify(data.user));

        setAuthState({
          user: data.user,
          token: data.access_token,
          refreshToken: data.refresh_token,
          isAuthenticated: true,
          isLoading: false,
        });

        return { success: true };
      } else {
        const errorData = await response.json();
        setAuthState(prev => ({ ...prev, isLoading: false }));
        return { 
          success: false, 
          error: errorData.detail || 'Login failed' 
        };
      }
    } catch (error) {
      setAuthState(prev => ({ ...prev, isLoading: false }));
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Network error' 
      };
    }
  };

  const logout = useCallback(async () => {
    try {
      if (authState.token) {
        // Call logout endpoint to invalidate tokens on server
        await fetch(`${API_BASE_URL}/api/auth/logout`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${authState.token}`,
          },
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      clearAuthData();
    }
  }, [authState.token, clearAuthData]);

  const updateProfile = async (profileData: Partial<Pick<User, 'email'>>) => {
    try {
      if (!authState.token) {
        throw new Error('No authentication token');
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authState.token}`,
        },
        body: JSON.stringify(profileData),
      });

      if (response.ok) {
        const updatedUser = await response.json();
        localStorage.setItem('user_data', JSON.stringify(updatedUser));
        
        setAuthState(prev => ({
          ...prev,
          user: updatedUser,
        }));

        return { success: true };
      } else {
        const errorData = await response.json();
        return { 
          success: false, 
          error: errorData.detail || 'Profile update failed' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Network error' 
      };
    }
  };

  const changePassword = async (oldPassword: string, newPassword: string) => {
    try {
      if (!authState.token) {
        throw new Error('No authentication token');
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/change-password`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authState.token}`,
        },
        body: JSON.stringify({
          current_password: oldPassword,
          new_password: newPassword,
        }),
      });

      if (response.ok) {
        return { success: true };
      } else {
        const errorData = await response.json();
        return { 
          success: false, 
          error: errorData.detail || 'Password change failed' 
        };
      }
    } catch (error) {
      return { 
        success: false, 
        error: error instanceof Error ? error.message : 'Network error' 
      };
    }
  };

  // Function to verify current token (called only when needed)
  const verifyToken = useCallback(async () => {
    if (!authState.token) return false;

    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/profile`, {
        headers: {
          'Authorization': `Bearer ${authState.token}`,
        },
      });

      if (response.ok) {
        const user = await response.json();
        // Update user data if different
        if (JSON.stringify(user) !== JSON.stringify(authState.user)) {
          localStorage.setItem('user_data', JSON.stringify(user));
          setAuthState(prev => ({ ...prev, user }));
        }
        return true;
      } else if (response.status === 401 && authState.refreshToken) {
        // Try to refresh token
        return await refreshAccessToken(authState.refreshToken);
      } else {
        clearAuthData();
        return false;
      }
    } catch (error) {
      console.error('Token verification error:', error);
      clearAuthData();
      return false;
    }
  }, [authState.token, authState.user, authState.refreshToken, refreshAccessToken, clearAuthData]);

  // Function to sync auth state with localStorage changes (for when API service refreshes tokens)
  const syncAuthState = useCallback(() => {
    const token = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    const userData = localStorage.getItem('user_data');

    if (token && userData && token !== authState.token) {
      try {
        const user = JSON.parse(userData);
        setAuthState({
          user,
          token,
          refreshToken,
          isAuthenticated: true,
          isLoading: false,
        });
      } catch (error) {
        console.error('Error syncing auth state:', error);
        clearAuthData();
      }
    } else if (!token) {
      clearAuthData();
    }
  }, [authState.token, clearAuthData]);

  // Listen for storage changes (when API service updates tokens)
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token' || e.key === 'refresh_token' || e.key === 'user_data') {
        console.log('🔄 Storage change detected, syncing auth state...')
        syncAuthState()
      }
    }

    // Listen for auth logout events from API service
    const handleAuthLogout = (e: CustomEvent) => {
      console.log('🚪 Auth logout event received:', e.detail?.reason)
      clearAuthData()
    }

    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('auth:logout', handleAuthLogout as EventListener)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('auth:logout', handleAuthLogout as EventListener)
    }
  }, [syncAuthState, clearAuthData]);

  // Add automatic token refresh before expiration
  useEffect(() => {
    if (!authState.isAuthenticated || !authState.token || !authState.refreshToken) {
      return;
    }

    const checkTokenExpiration = () => {
      try {
        const payload = JSON.parse(atob(authState.token!.split('.')[1]));
        const now = Math.floor(Date.now() / 1000);
        const timeUntilExpiry = payload.exp - now;
        
        // If token expires in less than 5 minutes, refresh it
        if (timeUntilExpiry < 300 && timeUntilExpiry > 0) {
          console.log('🔄 Token expiring soon, auto-refreshing...');
          refreshAccessToken(authState.refreshToken!);
        }
      } catch (e) {
        console.error('Error checking token expiration:', e);
      }
    };

    // Check token expiration every minute
    const interval = setInterval(checkTokenExpiration, 60000);
    
    // Also check immediately
    checkTokenExpiration();

    return () => clearInterval(interval);
  }, [authState.isAuthenticated, authState.token, authState.refreshToken, refreshAccessToken]);

  return {
    user: authState.user,
    token: authState.token,
    isAuthenticated: authState.isAuthenticated,
    isLoading: authState.isLoading,
    login,
    logout,
    updateProfile,
    changePassword,
    verifyToken,
  };
} 