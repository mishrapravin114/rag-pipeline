"use client"

import { useState, useCallback, useEffect } from "react"
import { apiService, type Drug } from "../services/api"

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<Drug[]>([])
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

  const toggleBookmark = useCallback(async (drugId: string) => {
    try {
      const result = await apiService.toggleBookmark(drugId)
      if (result.bookmarked) {
        // Add to bookmarks if not already there
        const drug = await apiService.getDrug(drugId)
        setBookmarks((prev) => [...prev, { ...drug, isBookmarked: true }])
      } else {
        // Remove from bookmarks
        setBookmarks((prev) => prev.filter((drug) => drug.id !== drugId))
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
