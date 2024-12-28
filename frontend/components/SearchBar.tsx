"use client"

import type React from "react"

import { useState } from "react"
import { Search, Filter } from "lucide-react"

interface SearchBarProps {
  onSearch: (query: string, filters?: { therapeuticArea?: string }) => void
  placeholder?: string
  showFilters?: boolean
}

export function SearchBar({
  onSearch,
  placeholder = "Search drugs, brands, or therapeutic areas...",
  showFilters = true,
}: SearchBarProps) {
  const [query, setQuery] = useState("")
  const [therapeuticArea, setTherapeuticArea] = useState("")
  const [showFilterDropdown, setShowFilterDropdown] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSearch(query, therapeuticArea ? { therapeuticArea } : undefined)
  }

  const therapeuticAreas = ["Oncology", "Cardiology", "Neurology", "Immunology", "Infectious Diseases", "Endocrinology"]

  return (
    <div className="relative w-full max-w-3xl">
      <form onSubmit={handleSubmit} className="relative">
        <div className="flex items-center bg-white/95 backdrop-blur-sm rounded-xl shadow-2xl border border-white/20 focus-within:ring-4 focus-within:ring-blue-300/50 focus-within:border-blue-300 transition-all duration-300">
          <Search className="w-6 h-6 text-blue-600 ml-5" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
            className="flex-1 px-5 py-4 text-gray-900 placeholder-gray-500 bg-transparent border-none outline-none text-lg"
          />
          {showFilters && (
            <button
              type="button"
              onClick={() => setShowFilterDropdown(!showFilterDropdown)}
              className="p-4 text-blue-600 hover:text-blue-700 hover:bg-blue-50 border-l border-gray-200 transition-colors duration-200"
            >
              <Filter className="w-5 h-5" />
            </button>
          )}
          <button
            type="submit"
            className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-r-xl hover:from-blue-700 hover:to-indigo-700 transition-all duration-200 font-semibold shadow-lg hover:shadow-xl"
          >
            Search
          </button>
        </div>
      </form>

      {showFilterDropdown && (
        <div className="absolute top-full left-0 right-0 mt-3 bg-white/95 backdrop-blur-sm rounded-xl shadow-2xl border border-white/20 z-10 animate-in slide-in-from-top-2 duration-200">
          <div className="p-6">
            <label className="block text-sm font-semibold text-gray-700 mb-3">Therapeutic Area</label>
            <select
              value={therapeuticArea}
              onChange={(e) => setTherapeuticArea(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-3 focus:ring-blue-300/50 focus:border-blue-400 bg-white text-gray-900 transition-all duration-200"
            >
              <option value="">All Areas</option>
              {therapeuticAreas.map((area) => (
                <option key={area} value={area}>
                  {area}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  )
}
