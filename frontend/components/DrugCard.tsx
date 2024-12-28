"use client"

import type React from "react"

import { useState } from "react"
import { Bookmark, Calendar, Tag } from "lucide-react"
import type { Drug } from "../services/api"

interface DrugCardProps {
  drug: Drug
  onBookmark?: (drugId: string) => Promise<boolean>
  onClick?: () => void
}

export function DrugCard({ drug, onBookmark, onClick }: DrugCardProps) {
  const [isBookmarked, setIsBookmarked] = useState(drug.isBookmarked || false)
  const [bookmarkLoading, setBookmarkLoading] = useState(false)

  const handleBookmark = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!onBookmark) return

    setBookmarkLoading(true)
    try {
      const bookmarked = await onBookmark(drug.id)
      setIsBookmarked(bookmarked)
    } finally {
      setBookmarkLoading(false)
    }
  }

  return (
    <div
      className="bg-white rounded-lg shadow-md border border-gray-200 p-6 hover:shadow-lg transition-shadow cursor-pointer"
      onClick={onClick}
    >
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-xl font-semibold text-gray-900 mb-1">{drug.name}</h3>
          <p className="text-gray-600">{drug.brand}</p>
        </div>
        <button
          onClick={handleBookmark}
          disabled={bookmarkLoading}
          className={`p-2 rounded-full transition-colors ${
            isBookmarked
              ? "text-blue-600 bg-blue-50 hover:bg-blue-100"
              : "text-gray-400 hover:text-blue-600 hover:bg-blue-50"
          }`}
        >
          <Bookmark className={`w-5 h-5 ${isBookmarked ? "fill-current" : ""}`} />
        </button>
      </div>

      <p className="text-gray-700 mb-4 line-clamp-3">{drug.description}</p>

      <div className="flex items-center gap-4 text-sm text-gray-500">
        <div className="flex items-center gap-1">
          <Tag className="w-4 h-4" />
          <span>{drug.therapeuticArea}</span>
        </div>
        {drug.timeline.length > 0 && (
          <div className="flex items-center gap-1">
            <Calendar className="w-4 h-4" />
            <span>{drug.timeline[0].phase}</span>
          </div>
        )}
      </div>
    </div>
  )
}
