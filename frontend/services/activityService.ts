// Activity tracking service for real-time updates and persistence
export interface ActivityData {
  id: string;
  type: 'search' | 'view' | 'chat' | 'download' | 'file_view';
  text: string;
  query?: string;
  entity_name?: string;
  results_count?: number;
  source_file_id?: number;
  timestamp: string;
  user_id?: string;
}

class ActivityService {
  private readonly STORAGE_KEY = 'fda_recent_activities';
  private readonly MAX_ACTIVITIES = 20;

  // Save activity to local storage
  saveActivity(activity: Omit<ActivityData, 'id' | 'timestamp'>) {
    try {
      const activities = this.getLocalActivities();
      
      const newActivity: ActivityData = {
        ...activity,
        id: `local-${Date.now()}-${Math.random()}`,
        timestamp: new Date().toISOString(),
        user_id: this.getCurrentUserId()
      };

      // Add to beginning and limit size
      activities.unshift(newActivity);
      if (activities.length > this.MAX_ACTIVITIES) {
        activities.splice(this.MAX_ACTIVITIES);
      }

      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(activities));
      
      // Emit custom event for real-time updates
      window.dispatchEvent(new CustomEvent('activity:new', { detail: newActivity }));
      
      return newActivity;
    } catch (error) {
      console.error('Failed to save activity:', error);
      return null;
    }
  }

  // Get activities from local storage
  getLocalActivities(): ActivityData[] {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Failed to get local activities:', error);
      return [];
    }
  }

  // Clear old activities (older than 7 days)
  cleanupOldActivities() {
    try {
      const activities = this.getLocalActivities();
      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

      const filtered = activities.filter(activity => {
        const activityDate = new Date(activity.timestamp);
        return activityDate > sevenDaysAgo;
      });

      if (filtered.length !== activities.length) {
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(filtered));
      }
    } catch (error) {
      console.error('Failed to cleanup activities:', error);
    }
  }

  // Get current user ID from auth
  private getCurrentUserId(): string {
    try {
      const userData = localStorage.getItem('user_data');
      if (userData) {
        const user = JSON.parse(userData);
        return user.id || user.username || 'anonymous';
      }
    } catch (error) {
      console.error('Failed to get user ID:', error);
    }
    return 'anonymous';
  }

  // Track specific activity types
  trackSearch(query: string, entityName?: string, resultsCount?: number) {
    return this.saveActivity({
      type: 'search',
      text: entityName ? `Searched for "${query}" in ${entityName}` : `Searched for "${query}"`,
      query,
      entity_name: entityName,
      results_count: resultsCount
    });
  }

  trackView(entityName: string, sourceFileId?: number) {
    return this.saveActivity({
      type: 'view',
      text: `Viewed metadata for ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }

  trackChat(entityName: string, sourceFileId?: number, query?: string) {
    return this.saveActivity({
      type: 'chat',
      text: query ? `Asked about ${entityName}: "${query}"` : `Started chat about ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId,
      query
    });
  }

  trackDownload(entityName: string, sourceFileId?: number) {
    return this.saveActivity({
      type: 'download',
      text: `Downloaded ${entityName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }

  trackFileView(fileName: string, entityName?: string, sourceFileId?: number) {
    return this.saveActivity({
      type: 'file_view',
      text: `Viewed document: ${fileName}`,
      entity_name: entityName,
      source_file_id: sourceFileId
    });
  }
}

export const activityService = new ActivityService();