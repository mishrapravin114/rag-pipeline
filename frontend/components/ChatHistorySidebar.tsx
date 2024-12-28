"use client"

import React, { useState } from "react";
import { Clock, Trash2, MessageSquare, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useChatHistory, type ChatHistoryItem, type ChatSessionItem, type FavoriteItem } from "@/hooks/useChatHistory";

interface ChatHistorySidebarProps {
  onSelectHistory?: (item: ChatSessionItem) => void;
  onLoadQuery?: (query: string) => void;
  className?: string;
}

export function ChatHistorySidebar({ onSelectHistory, onLoadQuery, className = "" }: ChatHistorySidebarProps) {
  const { history, sessions, loading, error, deleteChat } = useChatHistory();
  const [actionLoading, setActionLoading] = useState<{ [key: number]: boolean }>({});

  // Favorites functionality removed

  const handleDeleteChat = async (chatId: number) => {
    if (!confirm("Are you sure you want to delete this chat?")) return;
    
    setActionLoading(prev => ({ ...prev, [chatId]: true }));
    try {
      await deleteChat(chatId);
    } finally {
      setActionLoading(prev => ({ ...prev, [chatId]: false }));
    }
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffInHours = (now.getTime() - date.getTime()) / (1000 * 60 * 60);
      
      if (diffInHours < 24) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (diffInHours < 24 * 7) {
        return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
      } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
    } catch {
      return 'Unknown';
    }
  };

  const getDateGroup = (dateString: string) => {
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffInDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
      
      if (diffInDays === 0) {
        return 'Today';
      } else if (diffInDays === 1) {
        return 'Yesterday';
      } else if (diffInDays < 7) {
        return 'This Week';
      } else if (diffInDays < 30) {
        return 'This Month';
      } else {
        return date.toLocaleDateString([], { month: 'long', year: 'numeric' });
      }
    } catch {
      return 'Unknown';
    }
  };

  const groupSessionsByDate = (sessionItems: ChatSessionItem[]) => {
    const groups: { [key: string]: ChatSessionItem[] } = {};
    
    sessionItems.forEach(item => {
      const group = getDateGroup(item.last_activity || item.created_at);
      if (!groups[group]) {
        groups[group] = [];
      }
      groups[group].push(item);
    });
    
    // Sort groups by priority (Today, Yesterday, This Week, etc.)
    const groupOrder = ['Today', 'Yesterday', 'This Week', 'This Month'];
    const sortedGroups: { [key: string]: ChatSessionItem[] } = {};
    
    groupOrder.forEach(group => {
      if (groups[group]) {
        sortedGroups[group] = groups[group];
      }
    });
    
    // Add remaining groups (months/years) in reverse chronological order
    Object.keys(groups)
      .filter(group => !groupOrder.includes(group))
      .sort((a, b) => {
        // Sort months/years in reverse chronological order
        const dateA = new Date(a + ' 1');
        const dateB = new Date(b + ' 1');
        return dateB.getTime() - dateA.getTime();
      })
      .forEach(group => {
        sortedGroups[group] = groups[group];
      });
    
    return sortedGroups;
  };

  const truncateQuery = (query: string, maxLength: number = 60) => {
    return query.length > maxLength ? query.substring(0, maxLength) + '...' : query;
  };

  if (error) {
    return (
      <div className={`w-80 bg-white border-l border-gray-200 p-4 ${className}`}>
        <div className="text-center text-red-600">
          <p className="text-sm">Failed to load data</p>
          <p className="text-xs text-gray-500 mt-1">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-card flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="p-4 border-b border-border flex-shrink-0">
        <h3 className="text-lg font-semibold text-foreground mb-3">Chat Activity</h3>
        
        {/* History header */}
        <div className="flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium">Recent Conversations</span>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1 min-h-0">
        <div className="p-4">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="ml-2 text-sm text-muted-foreground">Loading...</span>
            </div>
          ) : (
            <>
              {
                <div className="space-y-4">
                  {sessions.length === 0 ? (
                    <div className="text-center py-8">
                      <MessageSquare className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                      <p className="text-sm text-muted-foreground">No chat history yet</p>
                      <p className="text-xs text-muted-foreground/60 mt-1">Start a conversation to see your history</p>
                    </div>
                  ) : (
                    Object.entries(groupSessionsByDate(sessions)).map(([dateGroup, groupItems]) => (
                      <div key={dateGroup} className="space-y-2">
                        {/* Date Group Header */}
                        <div className="sticky top-0 bg-card border-b border-border pb-1 mb-2">
                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                            {dateGroup}
                          </h4>
                        </div>
                        
                        {/* History Items in Group */}
                        <div className="space-y-2">
                          {groupItems.map((item) => (
                            <div
                              key={item.id}
                              className="p-3 bg-muted/50 rounded-lg hover:bg-muted transition-all duration-200 cursor-pointer group"
                              onClick={() => onSelectHistory?.(item)}
                            >
                              <div className="flex items-start justify-between mb-2">
                                <div className="flex-1 min-w-0 overflow-hidden">
                                  <div className="overflow-x-auto pb-1 history-item-scroll" style={{ scrollbarWidth: 'thin', scrollbarColor: '#cbd5e1 transparent' }}>
                                    <p className="text-sm font-medium text-foreground whitespace-nowrap pr-2">
                                      {item.query}
                                    </p>
                                  </div>
                                  <div className="flex items-center mt-1 space-x-2">
                                    <Badge variant="outline" className="text-xs">
                                      {formatDate(item.last_activity || item.created_at)}
                                    </Badge>
                                    {item.message_count && (
                                      <Badge variant="secondary" className="text-xs">
                                        {item.message_count} message{item.message_count !== 1 ? 's' : ''}
                                      </Badge>
                                    )}
                                  </div>
                                </div>
                                
                                <div className="flex items-center space-x-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                  <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleDeleteChat(item.id);
                                    }}
                                    disabled={actionLoading[item.id]}
                                    className="h-6 w-6 p-0 text-red-400 hover:text-red-600"
                                    title="Delete chat"
                                  >
                                    {actionLoading[item.id] ? (
                                      <Loader2 className="h-3 w-3 animate-spin" />
                                    ) : (
                                      <Trash2 className="h-3 w-3" />
                                    )}
                                  </Button>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              }
            </>
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="p-4 border-t border-gray-200 flex-shrink-0">
        <div className="text-xs text-gray-500 text-center">
          {sessions.length} conversation{sessions.length !== 1 ? 's' : ''}
        </div>
      </div>
    </div>
  );
} 