"use client"

import { useState, useCallback, useEffect, useRef } from "react"
import { apiService } from "../services/api"
import { useAuth } from "./useAuth"

export interface ChatHistoryItem {
  id: number;
  session_id: string;
  query: string;
  response?: string;
  source_file_id?: number;
  source_file_ids?: number[];
  created_at: string;
  is_favorite: boolean;
  timestamp?: string;
}

export interface ChatSessionItem {
  id: number;
  session_id: string;
  query: string;
  created_at: string;
  last_activity: string;
  message_count: number;
  is_favorite: boolean;
  timestamp: string;
}

export interface FavoriteItem {
  id: number;
  session_id: string;
  query: string;
}

export function useChatHistory(docxChatFilter?: boolean) {
  const { user } = useAuth();
  const [history, setHistory] = useState<ChatHistoryItem[]>([]);
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [favorites, setFavorites] = useState<FavoriteItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0); // Force refresh counter
  
  // Use a ref to always have access to the latest favorites
  const favoritesRef = useRef<FavoriteItem[]>([]);
  favoritesRef.current = favorites;

  const loadHistory = useCallback(async () => {
    if (!user?.id) return;
    
    setLoading(true);
    setError(null);
    try {
      // Load grouped sessions instead of individual chats - use the provided filter
      const data = await apiService.getUserChatSessions(user.id, docxChatFilter);
      // Map the API response to match our interface
      const mappedSessions = (data.sessions || []).map((item: any) => ({
        ...item,
        query: item.query || item.user_query || ''
      }));
      setSessions(mappedSessions);
      
      // Also keep the old history for compatibility - use the provided filter
      const historyData = await apiService.getUserChatHistory(user.id, docxChatFilter);
      const mappedHistory = (historyData.history || []).map((item: any) => ({
        ...item,
        query: item.query || item.user_query || ''
      }));
      setHistory(mappedHistory);
    } catch (error) {
      console.error("Failed to load chat history:", error);
      setError("Failed to load chat history");
    } finally {
      setLoading(false);
    }
  }, [user?.id, docxChatFilter]);

  const loadFavorites = useCallback(async () => {
    if (!user?.id) return;
    
    try {
      console.log("Loading favorites for user:", user.id);
      const data = await apiService.getFavoriteChats(user.id, docxChatFilter);
      console.log("Received favorites data:", data);
      
      // Map the API response to match our interface
      const mappedFavorites = (data.favorites || []).map((item: any) => ({
        id: item.id || item.chat_id,
        query: item.query || item.user_query || '',
        session_id: item.session_id || ''
      }));
      
      console.log("Mapped favorites:", mappedFavorites);
      console.log("Previous favorites count:", favorites.length, "New favorites count:", mappedFavorites.length);
      
      setFavorites(mappedFavorites);
      setRefreshKey(prev => {
        const newKey = prev + 1;
        console.log("Updating refreshKey from", prev, "to", newKey);
        return newKey;
      });
      
      console.log("Favorites state updated successfully");
    } catch (error) {
      console.error("Failed to load favorites:", error);
      setError("Failed to load favorites");
    }
  }, [user?.id, docxChatFilter]);

  const toggleFavorite = useCallback(async (chatId: number, isFavorite: boolean, fallbackQuery?: string) => {
    if (!user?.id) return false;
    
    try {
      console.log("🔄 useChatHistory: Toggling favorite for chat", chatId, "to", isFavorite);
      
      // Optimistically update the UI first
      let rollbackFavorites: FavoriteItem[] | null = null;
      
      if (isFavorite) {
        // Adding to favorites - optimistic update
        console.log("🔄 useChatHistory: Optimistically adding to favorites");
        
        // Find the item from history or create new
        const historyItem = history.find(item => item.id === chatId);
        const newFavorite = {
          id: chatId,
          session_id: historyItem?.session_id || `session-${chatId}`,
          query: historyItem?.query || fallbackQuery || 'Untitled Chat'
        };
        
        setFavorites(prev => {
          rollbackFavorites = [...prev]; // Save for rollback
          if (prev.some(fav => fav.id === chatId)) {
            console.log("🔄 Favorite already exists, not adding");
            return prev; // Already exists
          }
          const updated = [...prev, newFavorite];
          console.log("🔄 Optimistic update: Added favorite");
          console.log("🔄 Previous favorites:", prev.map(f => f.id));
          console.log("🔄 Updated favorites:", updated.map(f => f.id));
          console.log("🔄 New count:", updated.length);
          return updated;
        });
      } else {
        // Removing from favorites - optimistic update
        console.log("🔄 useChatHistory: Optimistically removing from favorites");
        setFavorites(prev => {
          rollbackFavorites = [...prev]; // Save for rollback
          const updated = prev.filter(fav => fav.id !== chatId);
          console.log("🔄 Optimistic update: Removed favorite");
          console.log("🔄 Previous favorites:", prev.map(f => f.id));
          console.log("🔄 Updated favorites:", updated.map(f => f.id));
          console.log("🔄 New count:", updated.length);
          return updated;
        });
      }
      
      // Force immediate re-render
      setRefreshKey(prev => prev + 1);
      
      // Make the API call
      console.log("🔄 useChatHistory: Making API call...");
      const result = await apiService.toggleChatFavorite(chatId, isFavorite);
      
      if (result.success) {
        console.log("✅ useChatHistory: API call successful");
        
        // Update history state to reflect the change
        setHistory(prev => prev.map(item => 
          item.id === chatId ? { ...item, is_favorite: isFavorite } : item
        ));
        
        // Force another re-render to ensure consistency
        setRefreshKey(prev => prev + 1);
        
        console.log("✅ useChatHistory: Toggle favorite completed successfully");
        console.log("✅ Current favorites count:", favoritesRef.current.length);
        
        return true;
      } else {
        console.error("❌ useChatHistory: API call failed - rolling back");
        
        // Rollback the optimistic update
        if (rollbackFavorites) {
          setFavorites(rollbackFavorites);
          setRefreshKey(prev => prev + 1);
        }
        
        return false;
      }
    } catch (error) {
      console.error("❌ useChatHistory: Failed to toggle favorite:", error);
      
      // Rollback on error
      loadFavorites(); // Reload from server to ensure consistency
      
      return false;
    }
  }, [user?.id, history, loadFavorites]);

  const deleteChat = useCallback(async (chatId: number) => {
    if (!user?.id) return false;
    
    try {
      const result = await apiService.deleteChat(chatId);
      if (result.success) {
        // Remove from local state
        setHistory(prev => prev.filter(item => item.id !== chatId));
        setFavorites(prev => prev.filter(item => item.id !== chatId));
        return true;
      }
      return false;
    } catch (error) {
      console.error("Failed to delete chat:", error);
      return false;
    }
  }, [user?.id, docxChatFilter]);

  // Load data when user changes
  useEffect(() => {
    if (user?.id) {
      loadHistory();
      loadFavorites();
    } else {
      setHistory([]);
      setFavorites([]);
    }
  }, [user?.id, docxChatFilter]); // Remove function dependencies to avoid infinite loops

  return {
    history,
    sessions,
    favorites,
    loading,
    error,
    loadHistory,
    loadFavorites,
    toggleFavorite,
    deleteChat,
    refreshKey, // Include refresh key to trigger re-renders
  };
} 