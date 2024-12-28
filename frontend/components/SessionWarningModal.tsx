"use client";

import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { AlertTriangle, Clock } from 'lucide-react';
import { API_BASE_URL } from '@/config/api';

interface SessionWarningModalProps {
  isOpen: boolean;
  onClose: () => void;
  onExtend: () => void;
  minutesRemaining: number;
}

export function SessionWarningModal({ 
  isOpen, 
  onClose, 
  onExtend, 
  minutesRemaining 
}: SessionWarningModalProps) {
  const [countdown, setCountdown] = useState(minutesRemaining * 60); // Convert to seconds
  
  useEffect(() => {
    if (!isOpen) return;
    
    const interval = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 0) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    
    return () => clearInterval(interval);
  }, [isOpen]);
  
  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="h-12 w-12 bg-amber-100 rounded-full flex items-center justify-center">
              <AlertTriangle className="h-6 w-6 text-amber-600" />
            </div>
            <div>
              <DialogTitle className="text-xl">Session Expiring Soon</DialogTitle>
              <DialogDescription className="text-base mt-1">
                Your session will expire due to inactivity
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>
        
        <div className="py-6">
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
            <div className="flex items-center justify-center gap-3">
              <Clock className="h-8 w-8 text-amber-600" />
              <div className="text-center">
                <div className="text-3xl font-bold text-amber-900">
                  {formatTime(countdown)}
                </div>
                <div className="text-sm text-amber-700 mt-1">
                  Time remaining
                </div>
              </div>
            </div>
          </div>
          
          <p className="text-sm text-gray-600 mt-4 text-center">
            Click "Extend Session" to continue working, or you will be logged out automatically.
          </p>
        </div>
        
        <DialogFooter className="flex gap-3">
          <Button
            variant="outline"
            onClick={onClose}
            className="flex-1 border-gray-300 text-gray-700 hover:bg-gray-50 btn-professional-subtle"
          >
            Log Out Now
          </Button>
          <Button
            onClick={onExtend}
            className="flex-1 bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800 text-white btn-professional"
          >
            Extend Session
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Hook to manage session warnings
export function useSessionWarning() {
  const [showWarning, setShowWarning] = useState(false);
  const WARNING_THRESHOLD = 5 * 60 * 1000; // Show warning 5 minutes before expiry
  const SESSION_DURATION = 24 * 60 * 60 * 1000; // 24 hours
  
  useEffect(() => {
    let warningTimeout: NodeJS.Timeout;
    
    const scheduleWarning = () => {
      // Clear any existing timeout
      if (warningTimeout) clearTimeout(warningTimeout);
      
      // Calculate when to show warning
      const timeToWarning = SESSION_DURATION - WARNING_THRESHOLD;
      
      warningTimeout = setTimeout(() => {
        setShowWarning(true);
      }, timeToWarning);
    };
    
    // Schedule initial warning
    scheduleWarning();
    
    // Listen for session extensions
    const handleSessionExtended = () => {
      setShowWarning(false);
      scheduleWarning();
    };
    
    window.addEventListener('session:extended', handleSessionExtended);
    
    return () => {
      if (warningTimeout) clearTimeout(warningTimeout);
      window.removeEventListener('session:extended', handleSessionExtended);
    };
  }, []);
  
  const extendSession = async () => {
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      if (!refreshToken) return;
      
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
        
        // Dispatch event
        window.dispatchEvent(new CustomEvent('session:extended'));
        
        setShowWarning(false);
      }
    } catch (error) {
      console.error('Failed to extend session:', error);
    }
  };
  
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_data');
    window.location.href = '/auth/login';
  };
  
  return {
    showWarning,
    extendSession,
    handleLogout,
    minutesRemaining: 5
  };
}