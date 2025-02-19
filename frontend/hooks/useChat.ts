"use client"

import { useState, useCallback } from "react"
import { apiService, type ChatMessage } from "../services/api"

export function useChat(entityId?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim()) return

      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        content,
        role: "user",
        timestamp: new Date(),
        entityId,
      }

      setMessages((prev) => [...prev, userMessage])
      setLoading(true)
      setError(null)

      try {
        // Use unified chat endpoint for better fallback support
        const requestPayload = { 
          message: content,
          session_id: localStorage.getItem('session_id') || undefined,
          user_id: undefined // Will be set by backend from auth
        };

        const response = await apiService.sendUnifiedChatMessage(requestPayload);
        
        const assistantMessage: ChatMessage = {
          id: response.id,
          content: response.content,
          role: "assistant",
          timestamp: new Date(response.timestamp),
          entityId,
          contentType: "html",
          sourceInfo: response.source_info,
          searchResults: response.search_results,
          usedDocuments: response.used_documents
        };
        
        setMessages((prev) => [...prev, assistantMessage])
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to send message")
      } finally {
        setLoading(false)
      }
    },
    [entityId],
  )

  const loadHistory = useCallback(async () => {
    try {
      const history = await apiService.getChatHistory(entityId)
      setMessages(history)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chat history")
    }
  }, [entityId])

  return {
    messages,
    loading,
    error,
    sendMessage,
    loadHistory,
  }
}
