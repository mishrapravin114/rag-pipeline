"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Search,
  Grid3x3,
  List,
  Download,
  ChevronDown,
  ChevronRight,
  FileText,
  Filter,
  X,
  ChevronUp
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface CollectionViewerProps {
  items: string[];
  collectionName: string;
  isExpanded: boolean;
  onToggle: () => void;
  className?: string;
}

export function CollectionViewer({ items, collectionName, isExpanded, onToggle, className }: CollectionViewerProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('grid');
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  
  // Group items alphabetically
  const groupedItems = useMemo(() => {
    const filtered = items.filter(item => 
      item.toLowerCase().includes(searchTerm.toLowerCase())
    );
    
    const groups: Record<string, string[]> = {};
    filtered.forEach(item => {
      const firstLetter = item[0].toUpperCase();
      if (!groups[firstLetter]) {
        groups[firstLetter] = [];
      }
      groups[firstLetter].push(item);
    });
    
    // Sort groups alphabetically
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [items, searchTerm]);
  
  const filteredCount = groupedItems.reduce((sum, [_, items]) => sum + items.length, 0);
  
  const toggleSection = (letter: string) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(letter)) {
      newExpanded.delete(letter);
    } else {
      newExpanded.add(letter);
    }
    setExpandedSections(newExpanded);
  };
  
  const toggleItem = (item: string) => {
    const newSelected = new Set(selectedItems);
    if (newSelected.has(item)) {
      newSelected.delete(item);
    } else {
      newSelected.add(item);
    }
    setSelectedItems(newSelected);
  };
  
  const exportList = () => {
    const content = items.join('\n');
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${collectionName}-documents.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  // Auto-expand first few sections when searching
  useEffect(() => {
    if (searchTerm) {
      const firstThree = groupedItems.slice(0, 3).map(([letter]) => letter);
      setExpandedSections(new Set(firstThree));
    }
  }, [searchTerm, groupedItems]);
  
  return (
    <div className={cn("bg-white/10 rounded-lg p-3 backdrop-blur-sm border border-white/20", className)}>
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between hover:bg-white/5 rounded-md p-2 transition-colors"
      >
        <div className="flex items-center gap-3">
          <FileText className="h-5 w-5 text-white/80" />
          <span className="text-white font-semibold text-lg">{collectionName}</span>
          <Badge className="bg-green-500/20 text-green-100 border-green-400/30 px-3 py-1">
            {items.length} documents
          </Badge>
        </div>
        {isExpanded ? (
          <ChevronUp className="h-5 w-5 text-white/80" />
        ) : (
          <ChevronDown className="h-5 w-5 text-white/80" />
        )}
      </button>
      
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="mt-3 overflow-hidden"
          >
            {/* Search and Controls */}
            <div className="space-y-3 mb-4">
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/60" />
                  <Input
                    placeholder="Search documents..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10 bg-white/10 border-white/20 text-white placeholder:text-white/50 focus:bg-white/20"
                  />
                  {searchTerm && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSearchTerm('')}
                      className="absolute right-1 top-1/2 -translate-y-1/2 h-7 w-7 p-0 text-white/60 hover:text-white"
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setViewMode(viewMode === 'list' ? 'grid' : 'list')}
                  className="text-white/80 hover:text-white hover:bg-white/10"
                >
                  {viewMode === 'list' ? <Grid3x3 className="h-4 w-4" /> : <List className="h-4 w-4" />}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={exportList}
                  className="text-white/80 hover:text-white hover:bg-white/10"
                >
                  <Download className="h-4 w-4" />
                </Button>
              </div>
              
              {/* Results count */}
              <div className="flex items-center justify-between text-sm text-white/70">
                <span>
                  Showing {filteredCount} of {items.length} documents
                  {selectedItems.size > 0 && ` • ${selectedItems.size} selected`}
                </span>
                {searchTerm && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setSearchTerm('')}
                    className="h-6 text-xs text-white/70 hover:text-white"
                  >
                    Clear search
                  </Button>
                )}
              </div>
            </div>
            
            {/* Document List */}
            <ScrollArea className="h-[400px] pr-3">
              {groupedItems.length === 0 ? (
                <div className="text-center py-8 text-white/60">
                  <p>No documents found matching "{searchTerm}"</p>
                </div>
              ) : viewMode === 'list' ? (
                // List View with Collapsible Sections
                <div className="space-y-2">
                  {groupedItems.map(([letter, letterItems]) => (
                    <div key={letter} className="border border-white/10 rounded-lg overflow-hidden">
                      <button
                        onClick={() => toggleSection(letter)}
                        className="w-full flex items-center justify-between p-3 bg-white/5 hover:bg-white/10 transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          {expandedSections.has(letter) ? (
                            <ChevronDown className="h-4 w-4 text-white/60" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-white/60" />
                          )}
                          <span className="font-semibold text-white">{letter}</span>
                          <Badge variant="secondary" className="bg-white/10 text-white/80 border-white/20">
                            {letterItems.length}
                          </Badge>
                        </div>
                      </button>
                      
                      <AnimatePresence>
                        {expandedSections.has(letter) && (
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: "auto" }}
                            exit={{ height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="p-2 space-y-1">
                              {letterItems.map((item) => (
                                <button
                                  key={item}
                                  onClick={() => toggleItem(item)}
                                  className={cn(
                                    "w-full text-left p-2 rounded text-sm text-white/80 hover:bg-white/10 transition-colors flex items-center gap-2",
                                    selectedItems.has(item) && "bg-white/10 text-white"
                                  )}
                                >
                                  <FileText className="h-3 w-3 flex-shrink-0" />
                                  <span className="truncate">{item}</span>
                                </button>
                              ))}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  ))}
                </div>
              ) : (
                // Grid View
                <div className="space-y-4">
                  {groupedItems.map(([letter, letterItems]) => (
                    <div key={letter}>
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-semibold text-white text-sm">{letter}</span>
                        <div className="flex-1 h-px bg-white/20" />
                        <Badge variant="secondary" className="bg-white/10 text-white/70 border-white/20 text-xs">
                          {letterItems.length}
                        </Badge>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                        {letterItems.map((item) => (
                          <button
                            key={item}
                            onClick={() => toggleItem(item)}
                            className={cn(
                              "p-2 rounded-lg text-xs text-white/80 hover:bg-white/10 transition-colors flex items-center gap-2 border border-white/10",
                              selectedItems.has(item) && "bg-white/10 text-white border-white/30"
                            )}
                          >
                            <FileText className="h-3 w-3 flex-shrink-0" />
                            <span className="truncate">{item}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
            
            {/* Mini-map for quick navigation */}
            {viewMode === 'list' && groupedItems.length > 5 && (
              <div className="mt-3 pt-3 border-t border-white/20">
                <div className="flex flex-wrap gap-1">
                  {groupedItems.map(([letter]) => (
                    <button
                      key={letter}
                      onClick={() => toggleSection(letter)}
                      className={cn(
                        "w-7 h-7 rounded text-xs font-medium transition-colors",
                        expandedSections.has(letter)
                          ? "bg-white/20 text-white"
                          : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80"
                      )}
                    >
                      {letter}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}