"use client";

import { useEffect, useRef, useCallback, useState } from 'react';
import { API_BASE_URL } from '@/config/api';
import { SessionWarningModal } from './SessionWarningModal';

interface SessionManagerProps {
  children: React.ReactNode;
}

export function SessionManager({ children }: SessionManagerProps) {
  const lastActivityRef = useRef<number>(Date.now());
  const refreshIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [showSessionWarning, setShowSessionWarning] = useState(false);
  const [sessionStartTime, setSessionStartTime] = useState(Date.now());
  
  // Token refresh intervals
  const TOKEN_REFRESH_INTERVAL = 12 * 60 * 60 * 1000; // 12 hours (half of 24-hour expiry)
  const ACTIVITY_CHECK_INTERVAL = 5 * 60 * 1000; // 5 minutes
  const INACTIVITY_TIMEOUT = 23 * 60 * 60 * 1000; // 23 hours (warn before 24-hour expiry)
  const WARNING_BEFORE_EXPIRY = 5 * 60 * 1000; // Show warning 5 minutes before expiry
  
  // Refresh the access token
  const refreshToken = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return;
    
    try {
      
      const response = await fetch(`${API_BASE_URL}/api/auth/refresh-token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ refresh_token: refreshToken }),
      });
      
      if (response.ok) {
        const tokenData = await response.json();
        
        // Update stored tokens
        localStorage.setItem('access_token', tokenData.access_token);
        if (tokenData.refresh_token) {
          localStorage.setItem('refresh_token', tokenData.refresh_token);
        }
        
        // Update last activity
        lastActivityRef.current = Date.now();
      } else {
        console.warn('⚠️ Periodic token refresh failed');
      }
    } catch (error) {
      console.error('❌ Error during periodic token refresh:', error);
    }
  }, []);
  
  // Track user activity
  const updateActivity = useCallback(() => {
    lastActivityRef.current = Date.now();
  }, []);
  
  // Check for inactivity
  const checkInactivity = useCallback(() => {
    const now = Date.now();
    const timeSinceLastActivity = now - lastActivityRef.current;
    
    if (timeSinceLastActivity > INACTIVITY_TIMEOUT) {
      console.warn('⚠️ User has been inactive for too long');
      
      // Optional: Show a warning modal or perform logout
      // For now, just refresh the token to keep session alive
      refreshToken();
    }
  }, [refreshToken]);
  
  // Set up activity listeners
  useEffect(() => {
    // Events that indicate user activity
    const activityEvents = [
      'mousedown',
      'mousemove',
      'keypress',
      'scroll',
      'touchstart',
      'click',
      'keydown',
    ];
    
    // Throttle activity updates to prevent excessive calls
    let activityTimeout: NodeJS.Timeout | null = null;
    
    const handleActivity = () => {
      if (activityTimeout) return;
      
      activityTimeout = setTimeout(() => {
        updateActivity();
        activityTimeout = null;
      }, 1000); // Throttle to once per second
    };
    
    // Add activity listeners
    activityEvents.forEach(event => {
      window.addEventListener(event, handleActivity);
    });
    
    // Set up periodic token refresh
    refreshIntervalRef.current = setInterval(() => {
      const accessToken = localStorage.getItem('access_token');
      if (accessToken) {
        refreshToken();
      }
    }, TOKEN_REFRESH_INTERVAL);
    
    // Set up inactivity check
    const inactivityInterval = setInterval(checkInactivity, ACTIVITY_CHECK_INTERVAL);
    
    // Initial token refresh if needed
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
      // Refresh token on app startup/reload
      refreshToken();
    }
    
    // Cleanup
    return () => {
      activityEvents.forEach(event => {
        window.removeEventListener(event, handleActivity);
      });
      
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
      
      clearInterval(inactivityInterval);
      
      if (activityTimeout) {
        clearTimeout(activityTimeout);
      }
    };
  }, [updateActivity, refreshToken, checkInactivity]);
  
  // Handle page visibility changes
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // Page became visible, update activity and potentially refresh token
        updateActivity();
        
        // Check if we should refresh the token
        const timeSinceLastActivity = Date.now() - lastActivityRef.current;
        if (timeSinceLastActivity > TOKEN_REFRESH_INTERVAL / 2) {
          refreshToken();
        }
      }
    };
    
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [updateActivity, refreshToken]);
  
  // Handle browser/tab close warning if there's ongoing work
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      // Check if there are any files being processed
      const processingFiles = document.querySelectorAll('[data-status="PROCESSING"]');
      if (processingFiles.length > 0) {
        const message = 'Files are still being processed. Are you sure you want to leave?';
        e.preventDefault();
        e.returnValue = message;
        return message;
      }
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);
  
  // Check if we should show session warning
  useEffect(() => {
    const checkSessionExpiry = () => {
      const now = Date.now();
      const sessionDuration = now - sessionStartTime;
      const timeUntilExpiry = (24 * 60 * 60 * 1000) - sessionDuration;
      
      if (timeUntilExpiry <= WARNING_BEFORE_EXPIRY && timeUntilExpiry > 0) {
        setShowSessionWarning(true);
      }
    };
    
    const interval = setInterval(checkSessionExpiry, 60 * 1000); // Check every minute
    
    return () => clearInterval(interval);
  }, [sessionStartTime]);
  
  const handleExtendSession = useCallback(async () => {
    await refreshToken();
    setShowSessionWarning(false);
    setSessionStartTime(Date.now());
  }, [refreshToken]);
  
  const handleLogout = useCallback(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_data');
    window.location.href = '/auth/login';
  }, []);
  
  return (
    <>
      {children}
      <SessionWarningModal
        isOpen={showSessionWarning}
        onClose={handleLogout}
        onExtend={handleExtendSession}
        minutesRemaining={5}
      />
    </>
  );
}