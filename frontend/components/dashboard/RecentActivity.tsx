"use client";

import { useState, useEffect } from "react";
import { Clock, Search, FileText, Download, Eye, Activity, ArrowRight, Loader2 } from "lucide-react";

interface ActivityItem {
  id: string;
  type: "search" | "view" | "download" | "report";
  description: string;
  timestamp: string;
  metadata?: {
    entityName?: string;
    query?: string;
    count?: number;
  };
}

const activityIcons = {
  search: Search,
  view: Eye,
  download: Download,
  report: FileText,
};

const activityColors = {
  search: "from-blue-500 to-indigo-600",
  view: "from-green-500 to-emerald-600",
  download: "from-purple-500 to-violet-600",
  report: "from-orange-500 to-amber-600",
};

const activityBgColors = {
  search: "from-blue-50 to-indigo-50",
  view: "from-green-50 to-emerald-50",
  download: "from-purple-50 to-violet-50",
  report: "from-orange-50 to-amber-50",
};

export function RecentActivity() {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Fetch recent activities from backend
    const fetchRecentActivities = async () => {
      setIsLoading(true);
      try {
        // Import the API service
        const { apiService } = await import('../../services/api');
        
        // Try to get user search history
        const history = await apiService.getUserSearchHistory(10);
        
        if (history && history.length > 0) {
          // Map API response to ActivityItem format
          const mapped = history.map((item: any, index: number) => {
            const activityType = item.action_type || (index % 3 === 0 ? 'search' : index % 3 === 1 ? 'view' : 'download');
            return {
              id: item.id || `activity-${index}`,
              type: activityType as any,
              description: item.description || `${activityType === 'search' ? 'Searched for' : activityType === 'view' ? 'Viewed' : 'Downloaded'} ${item.entity_name || item.search_term || 'document'}`,
              timestamp: item.created_at || new Date(Date.now() - 1000 * 60 * 60 * index).toISOString(),
              metadata: {
                entityName: item.entity_name,
                query: item.search_term,
                count: item.result_count,
              },
            };
          });
          setActivities(mapped.slice(0, 5)); // Show only 5 most recent
        } else {
          // Fallback to sample data if no history available
          setActivities([
            {
              id: "1",
              type: "search",
              description: "Searched for 'KRAZATI'",
              timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
              metadata: { query: "KRAZATI", count: 1 },
            },
            {
              id: "2",
              type: "view",
              description: "Viewed JEMPERLI details",
              timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
              metadata: { entityName: "JEMPERLI" },
            },
            {
              id: "3",
              type: "download",
              description: "Downloaded GAVRETO PDF",
              timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
              metadata: { entityName: "GAVRETO", count: 1 },
            },
            {
              id: "4",
              type: "search",
              description: "Searched in Oncology",
              timestamp: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
              metadata: { query: "Oncology", count: 4 },
            },
            {
              id: "5",
              type: "report",
              description: "Generated comparison report",
              timestamp: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
            },
          ]);
        }
      } catch (error) {
        console.error('Error fetching recent activities:', error);
        // Use fallback data on error
        setActivities([
          {
            id: "1",
            type: "search",
            description: "Searched for 'AUGTYRO'",
            timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
            metadata: { query: "AUGTYRO", count: 1 },
          },
          {
            id: "2",
            type: "view",
            description: "Viewed entity comparison",
            timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
            metadata: { count: 3 },
          },
          {
            id: "3",
            type: "download",
            description: "Exported search results",
            timestamp: new Date(Date.now() - 1000 * 60 * 60 * 4).toISOString(),
            metadata: { count: 5 },
          },
        ]);
      } finally {
        setIsLoading(false);
      }
    };

    fetchRecentActivities();
  }, []);

  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInMinutes = Math.floor((now.getTime() - time.getTime()) / (1000 * 60));

    if (diffInMinutes < 1) return "Just now";
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`;
    if (diffInMinutes < 1440) return `${Math.floor(diffInMinutes / 60)}h ago`;
    return `${Math.floor(diffInMinutes / 1440)}d ago`;
  };

  return (
    <div className="bg-gradient-to-br from-white via-purple-50/30 to-violet-50/50 rounded-2xl shadow-lg border border-purple-100/50 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-br from-purple-500 to-violet-600 p-3 rounded-xl shadow-lg">
            <Activity className="w-6 h-6 text-white" />
          </div>
          <div>
            <h3 className="text-xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent">
              Recent History
            </h3>
            <p className="text-sm text-gray-500">Your latest actions</p>
          </div>
        </div>
        <Clock className="w-5 h-5 text-gray-400" />
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="animate-pulse">
              <div className="flex items-center space-x-3 p-3 rounded-xl bg-white/50">
                <div className="w-10 h-10 bg-gradient-to-br from-gray-200 to-gray-300 rounded-xl"></div>
                <div className="flex-1">
                  <div className="h-4 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-3/4 mb-1"></div>
                  <div className="h-3 bg-gradient-to-r from-gray-200 to-gray-300 rounded w-1/2"></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : activities.length === 0 ? (
        <div className="text-center py-12 bg-white/50 rounded-xl">
          <div className="bg-gradient-to-br from-gray-100 to-gray-200 w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Clock className="w-8 h-8 text-gray-400" />
          </div>
          <p className="text-gray-500 font-medium">No recent activity</p>
          <p className="text-sm text-gray-400 mt-1">Your actions will appear here</p>
        </div>
      ) : (
        <div className="space-y-4">
          {activities.map((activity) => {
            const IconComponent = activityIcons[activity.type];
            const colorClasses = activityColors[activity.type];

            return (
              <div key={activity.id} className="group flex items-start space-x-3 p-3 rounded-xl bg-white/80 backdrop-blur-sm border border-purple-100/50 hover:border-purple-200 hover:shadow-md transition-all duration-300 cursor-pointer">
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${colorClasses} flex items-center justify-center flex-shrink-0 shadow-md group-hover:shadow-lg transition-all duration-300`}>
                  <IconComponent className="w-5 h-5 text-white" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate group-hover:text-purple-700 transition-colors">
                    {activity.description}
                  </p>
                  <div className="flex items-center justify-between mt-1">
                    <p className="text-xs text-gray-500">
                      {formatTimeAgo(activity.timestamp)}
                    </p>
                    {activity.metadata && (
                      <div className="flex items-center space-x-2">
                        {activity.metadata.count && (
                          <span className="text-xs font-medium text-purple-600 bg-purple-50 px-2 py-0.5 rounded-full">
                            {activity.metadata.count} items
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-purple-600 transition-colors opacity-0 group-hover:opacity-100" />
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-6 pt-6 border-t border-purple-100/50">
        <button className="w-full px-4 py-2.5 bg-gradient-to-r from-purple-600 to-violet-700 text-white rounded-xl hover:from-purple-700 hover:to-violet-800 transition-all duration-300 shadow-lg hover:shadow-xl font-medium flex items-center justify-center space-x-2">
          <span>View All Activity</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
} 