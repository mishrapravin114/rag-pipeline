import { useState, useEffect, useCallback } from 'react';
import { apiService } from '@/services/api';
import { activityService } from '@/services/activityService';

interface Activity {
  id: string;
  type: 'search' | 'view' | 'chat' | 'download' | 'file_view' | 'info' | 'error';
  text: string;
  time: string;
  query?: string;
  entity_name?: string;
  results_count?: number;
  source_file_id?: number;
  isLocal?: boolean;
  timestamp?: Date;
}

export function useActivityTracker() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);

  // Helper to get time ago
  const getTimeAgo = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 60) return 'just now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  };

  // Load activities from server and merge with local
  const loadActivities = useCallback(async () => {
    try {
      console.log('📊 Loading activities...');
      
      // Get local activities first
      const localActivities = activityService.getLocalActivities();
      const localFormatted = localActivities.slice(0, 5).map(item => ({
        id: item.id,
        type: item.type as any,
        text: item.text,
        time: getTimeAgo(new Date(item.timestamp)),
        query: item.query,
        entity_name: item.entity_name,
        results_count: item.results_count,
        source_file_id: item.source_file_id,
        timestamp: new Date(item.timestamp),
        isLocal: true
      }));
      
      // Try to get from chat history API (same as InsightXAI)
      let serverActivities: Activity[] = [];
      let chatHistorySuccessful = false;
      
      try {
        // Get user ID from auth - you may need to import useAuth or get it another way
        const userStr = localStorage.getItem('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          if (user.id) {
            // Use the same API as InsightXAI but filter for docXChat=true for dashboard
            console.log('📊 Dashboard: Fetching chat history with docXChat=true for user:', user.id);
            const chatHistoryData = await apiService.getUserChatHistory(user.id, true);
            console.log('Chat history from API (docXChat=true):', chatHistoryData);
            console.log('History length:', chatHistoryData.history?.length || 0);
            
            chatHistorySuccessful = true; // Mark as successful even if empty
            
            if (chatHistoryData.history && chatHistoryData.history.length > 0) {
              serverActivities = chatHistoryData.history.slice(0, 10).map((item: any) => ({
                id: `chat-${item.id}`,
                type: 'chat' as const,
                text: formatActivityText({
                  action_type: 'chat',
                  query: item.query || item.user_query,
                  entity_name: item.entity_name,
                  search_query: item.query || item.user_query,
                  user_query: item.query || item.user_query
                }),
                time: getTimeAgo(new Date(item.created_at)),
                query: item.query || item.user_query,
                entity_name: item.entity_name,
                timestamp: new Date(item.created_at),
                isLocal: false
              }));
            }
          }
        }
      } catch (error) {
        console.error('❌ Chat history API error:', error);
        console.log('Chat history not available, trying dashboard stats');
        
        // Fallback to dashboard stats
        try {
          const dashboardData = await apiService.getDashboardData();
          if (dashboardData.additional_stats?.recent_activity && dashboardData.additional_stats.recent_activity.length > 0) {
            console.log('Using recent activity from dashboard stats:', dashboardData.additional_stats.recent_activity);
            serverActivities = dashboardData.additional_stats.recent_activity.map((item: any) => ({
              id: item.id || `server-${Date.now()}-${Math.random()}`,
              type: item.type || 'search',
              text: formatActivityText({
                action_type: item.type,
                query: item.query,
                entity_name: item.entityName || item.entity_name,
                search_query: item.query,
                user_query: item.query
              }),
              time: getTimeAgo(new Date(item.timestamp)),
              query: item.query,
              entity_name: item.entityName || item.entity_name,
              timestamp: new Date(item.timestamp),
              isLocal: false
            }));
          }
        } catch (dashError) {
          console.log('Dashboard stats also not available');
        }
      }
      
      // If still no data AND chat history wasn't successful, try search history
      if (serverActivities.length === 0 && !chatHistorySuccessful) {
        console.log('No chat history available, falling back to search history');
        const history = await apiService.getUserSearchHistory(10);
        
        if (history && history.length > 0) {
          serverActivities = history.map((item: any) => ({
          id: item.id || `server-${Date.now()}-${Math.random()}`,
          type: item.action_type || 'search',
          text: formatActivityText(item),
          time: getTimeAgo(new Date(item.timestamp || item.created_at)),
          query: item.query || item.search_query || item.user_query,
          entity_name: item.entity_name,
          results_count: item.results_count,
          source_file_id: item.source_file_id,
          timestamp: new Date(item.timestamp || item.created_at),
          isLocal: false
        }));
        }
      }
      
      // Merge local and server activities  
      const merged = [...localFormatted, ...serverActivities];
      
      // Remove duplicates based on text and timestamp proximity
      const unique = merged.filter((activity, index, self) => {
        return index === self.findIndex(a => {
          // Consider activities duplicate if they have same text and are within 5 seconds
          const timeDiff = Math.abs(activity.timestamp.getTime() - a.timestamp.getTime());
          return a.text === activity.text && timeDiff < 5000;
        });
      });
      
      if (unique.length > 0) {
        setActivities(unique.slice(0, 10));
      } else if (localFormatted.length > 0) {
        setActivities(localFormatted);
      } else {
        setActivities([{
          id: 'default-1',
          type: 'info',
          text: 'No recent activity',
          time: 'Start exploring FDA entities',
          isLocal: false
        }]);
      }
    } catch (error) {
      console.error('❌ Failed to load activities:', error);
      
      // Fall back to local activities if server fails
      const localActivities = activityService.getLocalActivities();
      if (localActivities.length > 0) {
        const localFormatted = localActivities.slice(0, 5).map(item => ({
          id: item.id,
          type: item.type as any,
          text: item.text,
          time: getTimeAgo(new Date(item.timestamp)),
          query: item.query,
          entity_name: item.entity_name,
          results_count: item.results_count,
          source_file_id: item.source_file_id,
          timestamp: new Date(item.timestamp),
          isLocal: true
        }));
        setActivities(localFormatted);
      } else {
        setActivities([{
          id: 'error-1',
          type: 'error',
          text: 'Unable to load activity',
          time: 'Please refresh',
          isLocal: false
        }]);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Format activity text based on type and data
  const formatActivityText = (item: any) => {
    const type = item.action_type || 'search';
    const query = item.query || item.search_query || item.user_query || '';
    const entityName = item.entity_name;

    switch (type) {
      case 'search':
        if (entityName && query) {
          return `Searched for "${query}" in ${entityName}`;
        } else if (query) {
          return `Searched for "${query}"`;
        } else if (entityName) {
          return `Filtered by ${entityName}`;
        }
        return 'Performed search';
      
      case 'chat':
        // For chat, show the actual user query
        if (query && query.length > 0) {
          // Truncate long queries for display
          const displayQuery = query.length > 100 ? query.substring(0, 97) + '...' : query;
          return `Asked: "${displayQuery}"`;
        }
        return entityName ? `Chat about ${entityName}` : 'Started chat session';
      
      case 'view':
        return entityName ? `Viewed ${entityName}` : 'Viewed document';
      
      case 'file_view':
        return `Viewed document: ${entityName || query}`;
      
      case 'download':
        return `Downloaded ${entityName || 'document'}`;
      
      default:
        return query || 'Activity recorded';
    }
  };

  // Add a new activity locally
  const addActivity = useCallback((activity: Omit<Activity, 'id' | 'time' | 'timestamp'>) => {
    const newActivity: Activity = {
      ...activity,
      id: `local-${Date.now()}-${Math.random()}`,
      time: 'just now',
      timestamp: new Date(),
      isLocal: true
    };

    console.log('🆕 Adding local activity:', newActivity);

    setActivities(prev => {
      // Add new activity at the beginning
      const updated = [newActivity, ...prev];
      // Keep only 10 activities
      return updated.slice(0, 10);
    });

    // Update times for existing activities
    setTimeout(() => updateActivityTimes(), 1000);
  }, []);

  // Update activity times periodically
  const updateActivityTimes = useCallback(() => {
    setActivities(prev => prev.map(activity => ({
      ...activity,
      time: activity.timestamp ? getTimeAgo(activity.timestamp) : activity.time
    })));
  }, []);

  // Track search activity
  const trackSearch = useCallback((query: string, entityName?: string, resultsCount?: number) => {
    // Save to local storage
    activityService.trackSearch(query, entityName, resultsCount);
    
    // Add to state immediately
    addActivity({
      type: 'search',
      text: entityName ? `Searched for "${query}" in ${entityName}` : `Searched for "${query}"`,
      query,
      entity_name: entityName,
      results_count: resultsCount
    });
  }, [addActivity]);

  // Track view activity
  const trackView = useCallback((entityName: string, sourceFileId?: number) => {
    // Save to local storage
    activityService.trackView(entityName, sourceFileId);
    
    // Add to state immediately
    addActivity({
      type: 'view',
      text: `Viewed metadata for ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }, [addActivity]);

  // Track chat activity
  const trackChat = useCallback((entityName: string, sourceFileId?: number) => {
    // Save to local storage
    activityService.trackChat(entityName, sourceFileId);
    
    // Add to state immediately
    addActivity({
      type: 'chat',
      text: `Started chat about ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }, [addActivity]);

  // Track download activity
  const trackDownload = useCallback((entityName: string, sourceFileId?: number) => {
    // Save to local storage
    activityService.trackDownload(entityName, sourceFileId);
    
    // Add to state immediately
    addActivity({
      type: 'download',
      text: `Downloaded ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }, [addActivity]);

  // Initial load and listen for activity events
  useEffect(() => {
    loadActivities();
    
    // Clean up old activities on mount
    activityService.cleanupOldActivities();
    
    // Listen for new activity events
    const handleNewActivity = (event: CustomEvent) => {
      console.log('🆕 New activity event:', event.detail);
      loadActivities(); // Reload to show new activity
    };
    
    window.addEventListener('activity:new', handleNewActivity as EventListener);
    
    return () => {
      window.removeEventListener('activity:new', handleNewActivity as EventListener);
    };
  }, [loadActivities]);

  // Periodic refresh
  useEffect(() => {
    const interval = setInterval(() => {
      updateActivityTimes();
      // Reload from server every minute
      if (Date.now() % 60000 < 1000) {
        loadActivities();
      }
    }, 10000); // Update every 10 seconds

    return () => clearInterval(interval);
  }, [updateActivityTimes, loadActivities]);

  return {
    activities,
    loading,
    trackSearch,
    trackView,
    trackChat,
    trackDownload,
    refreshActivities: loadActivities
  };
}