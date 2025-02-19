"use client"

import { useState, useCallback, useEffect } from "react"
import { apiService, type Entity } from "../services/api"

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<Entity[]>([])
  const [loading, setLoading] = useState(false)

  const loadBookmarks = useCallback(async () => {
    setLoading(true)
    try {
      const data = await apiService.getBookmarks()
      setBookmarks(data)
    } catch (error) {
      console.error("Failed to load bookmarks:", error)
    } finally {
      setLoading(false)
    }
  }, [])

  const toggleBookmark = useCallback(async (entityId: string) => {
    try {
      const result = await apiService.toggleBookmark(entityId)
      if (result.bookmarked) {
        // Add to bookmarks if not already there
        const entity = await apiService.getEntity(entityId)
        setBookmarks((prev) => [...prev, { ...entity, isBookmarked: true }])
      } else {
        // Remove from bookmarks
        setBookmarks((prev) => prev.filter((entity) => entity.id !== entityId))
      }
      return result.bookmarked
    } catch (error) {
      console.error("Failed to toggle bookmark:", error)
      return false
    }
  }, [])

  useEffect(() => {
    loadBookmarks()
  }, [loadBookmarks])

  return {
    bookmarks,
    loading,
    toggleBookmark,
    loadBookmarks,
  }
}
