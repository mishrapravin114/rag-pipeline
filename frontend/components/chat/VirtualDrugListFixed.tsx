"use client";

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Search, X, Copy, Check, Loader2, FolderOpen } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { toast } from 'sonner';
import { apiService } from '@/services/api';
import { cn } from '@/lib/utils';

interface DrugItem {
  drug_name: string;
  document_count: number;
  document_ids: number[];
  documents?: Array<{
    id: number;
    file_name: string;
  }>;
}

interface VirtualDrugListProps {
  collectionId: number;
  collectionName: string;
  onDrugClick?: (drugName: string) => void;
  className?: string;
  height?: number;
  itemHeight?: number;
}

export function VirtualDrugListFixed({
  collectionId,
  collectionName,
  onDrugClick,
  className,
  height = 400,
  itemHeight = 60
}: VirtualDrugListProps) {
  const [drugs, setDrugs] = useState<DrugItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [hasNextPage, setHasNextPage] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [copiedDrug, setCopiedDrug] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Refs for managing state
  const searchTimeoutRef = useRef<NodeJS.Timeout>();
  const offsetRef = useRef(0);
  const isSearchingRef = useRef(false);
  
  const BATCH_SIZE = 200;

  // Copy to clipboard function (simple version)
  const copyToClipboard = async (text: string): Promise<boolean> => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      } else {
        // Fallback
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        let successful = false;
        try {
          successful = document.execCommand('copy');
        } catch (err) {
          console.error('Failed to copy using execCommand:', err);
        }
        
        document.body.removeChild(textArea);
        return successful;
      }
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      return false;
    }
  };

  // Reset and load initial data
  const resetAndLoad = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    offsetRef.current = 0;
    isSearchingRef.current = true;
    
    try {
      const response = await apiService.getCollectionDrugNames(collectionId, {
        search: searchQuery || undefined,
        limit: BATCH_SIZE,
        offset: 0,
        include_counts: true
      });
      
      setDrugs(response.drug_names);
      setTotalCount(response.total_count);
      setHasNextPage(response.has_more);
      offsetRef.current = response.drug_names.length;
    } catch (error) {
      console.error('Error loading drug names:', error);
      setError('Failed to load drug names');
      toast.error('Failed to load drug names');
    } finally {
      setIsLoading(false);
      isSearchingRef.current = false;
    }
  }, [collectionId, searchQuery]);

  // Load more data for pagination
  const loadMoreItems = useCallback(async () => {
    if (isLoading || !hasNextPage || isSearchingRef.current) return;
    
    setIsLoading(true);
    try {
      const response = await apiService.getCollectionDrugNames(collectionId, {
        search: searchQuery || undefined,
        limit: BATCH_SIZE,
        offset: offsetRef.current,
        include_counts: true
      });
      
      setDrugs(prev => [...prev, ...response.drug_names]);
      setHasNextPage(response.has_more);
      offsetRef.current += response.drug_names.length;
    } catch (error) {
      console.error('Error loading more drugs:', error);
      toast.error('Failed to load more drugs');
    } finally {
      setIsLoading(false);
    }
  }, [collectionId, searchQuery, isLoading, hasNextPage]);

  // Debounced search effect
  useEffect(() => {
    if (searchTimeoutRef.current) {
      clearTimeout(searchTimeoutRef.current);
    }
    
    searchTimeoutRef.current = setTimeout(() => {
      resetAndLoad();
    }, 300);
    
    return () => {
      if (searchTimeoutRef.current) {
        clearTimeout(searchTimeoutRef.current);
      }
    };
  }, [searchQuery, resetAndLoad]);

  // Initial load
  useEffect(() => {
    resetAndLoad();
  }, [collectionId]);

  // Handle drug click/copy
  const handleDrugClick = useCallback(async (drug: DrugItem) => {
    const success = await copyToClipboard(drug.drug_name);
    if (success) {
      setCopiedDrug(drug.drug_name);
      toast.success(`Copied "${drug.drug_name}" to clipboard`);
      setTimeout(() => setCopiedDrug(null), 2000);
      
      // Call the onDrugClick callback if provided
      if (onDrugClick) {
        onDrugClick(drug.drug_name);
      }
    } else {
      toast.error('Failed to copy to clipboard');
    }
  }, [onDrugClick]);

  // Clear search
  const clearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);

  if (error) {
    return (
      <div className={cn("flex flex-col", className)}>
        <div className="flex items-center justify-center p-8 text-center">
          <div>
            <div className="text-red-600 mb-2">{error}</div>
            <Button onClick={resetAndLoad} size="sm" variant="outline">
              Try Again
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex flex-col", className)}>
      {/* Collection Info */}
      <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-semibold text-blue-900">{collectionName}</h4>
          <Badge className="bg-green-100 text-green-800 border-green-200 text-xs">
            {totalCount} total
            {isLoading && ' (loading...)'}
          </Badge>
        </div>
        <p className="text-xs text-blue-700">
          {drugs.length > 0 
            ? `Showing ${drugs.length} of ${totalCount} drugs. Click to copy and use in chat.`
            : 'Search drug names to see results'
          }
        </p>
      </div>

      {/* Search Input */}
      <div className="mb-4 relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          placeholder="Search drug names..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-10 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white"
        />
        {searchQuery && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearSearch}
            className="absolute right-1 top-1/2 transform -translate-y-1/2 h-7 w-7 p-0"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {/* Drug List with Tooltips */}
      <div className="flex-1 border border-gray-200 rounded-lg overflow-hidden">
        {drugs.length > 0 ? (
          <div className="max-h-96 overflow-y-auto">
            {drugs.map((drug, index) => (
              <div key={`${drug.drug_name}-${index}`} className="px-3 py-2 border-b border-gray-100 last:border-b-0">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="outline"
                        onClick={() => handleDrugClick(drug)}
                        className="w-full justify-start text-left h-auto p-3 bg-white hover:bg-blue-50 hover:border-blue-300 border-gray-200 transition-all duration-150 group"
                      >
                        <div className="flex items-center gap-3 w-full min-w-0">
                          <FolderOpen className="h-4 w-4 text-blue-500 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-gray-800 font-medium truncate">
                              {drug.drug_name}
                            </p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="secondary" className="text-xs">
                                {drug.document_count} doc{drug.document_count !== 1 ? 's' : ''}
                              </Badge>
                            </div>
                          </div>
                          {copiedDrug === drug.drug_name ? (
                            <Check className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
                          ) : (
                            <Copy className="h-3.5 w-3.5 text-gray-400 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                          )}
                        </div>
                      </Button>
                    </TooltipTrigger>
                    {drug.documents && drug.documents.length > 0 && (
                      <TooltipContent side="left" className="max-w-sm z-50">
                        <div className="text-xs">
                          <p className="font-semibold mb-1">Documents ({drug.document_count}):</p>
                          <ul className="space-y-0.5 max-h-48 overflow-y-auto">
                            {drug.documents.slice(0, 10).map((doc, idx) => (
                              <li key={`${doc.id}-${idx}`} className="text-gray-600 break-words">
                                • {doc.file_name}
                              </li>
                            ))}
                            {drug.documents.length > 10 && (
                              <li className="text-gray-500 italic pt-1">
                                ... and {drug.documents.length - 10} more
                              </li>
                            )}
                          </ul>
                        </div>
                      </TooltipContent>
                    )}
                  </Tooltip>
                </TooltipProvider>
              </div>
            ))}
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <span className="ml-2 text-sm text-gray-600">Loading drug names...</span>
          </div>
        ) : searchQuery ? (
          <div className="text-center p-8">
            <p className="text-sm text-gray-500">No drugs found matching "{searchQuery}"</p>
          </div>
        ) : (
          <div className="text-center p-8">
            <p className="text-sm text-gray-500">No drugs available</p>
          </div>
        )}
      </div>

      {/* Load More / Status */}
      <div className="mt-2 text-center">
        {hasNextPage && !isLoading && (
          <Button 
            onClick={loadMoreItems}
            variant="outline" 
            size="sm"
            className="text-xs"
          >
            Load More ({drugs.length} of {totalCount})
          </Button>
        )}
        {!hasNextPage && drugs.length > 0 && (
          <span className="text-xs text-gray-500">All {totalCount} drugs loaded</span>
        )}
      </div>
    </div>
  );
}