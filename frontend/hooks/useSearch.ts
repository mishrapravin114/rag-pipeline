"use client"

import { useState, useCallback } from "react"
import { apiService, type Entity } from "../services/api"

export function useSearch() {
  const [results, setResults] = useState<Entity[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const search = useCallback(async (query: string, filters?: { therapeuticArea?: string }) => {
    if (!query.trim()) return

    setLoading(true)
    setError(null)

    try {
      const result = await apiService.searchEntities(query, filters)
      setResults(result.entities)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed")
    } finally {
      setLoading(false)
    }
  }, [])

  const clearResults = useCallback(() => {
    setResults([])
    setError(null)
  }, [])

  return {
    results,
    loading,
    error,
    search,
    clearResults,
  }
}
