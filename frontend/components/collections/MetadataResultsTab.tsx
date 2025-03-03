"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Download, 
  FileText, 
  Database,
  Search,
  Filter,
  Loader2,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  Eye,
  Settings
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';

interface MetadataResultsTabProps {
  collectionId: number;
  collectionName: string;
}

interface MetadataGroup {
  id: number;
  name: string;
  metadata_count: number;
}

interface DocumentMetadata {
  document_id: number;
  file_name: string;
  entity_name?: string;
  metadata: Record<string, string>;
  groups: string[];
}

interface MetadataResults {
  collection_id: number;
  collection_name: string;
  total_documents: number;
  documents: DocumentMetadata[];
}

export function MetadataResultsTab({ collectionId, collectionName }: MetadataResultsTabProps) {
  const [loading, setLoading] = useState(true);
  const [metadataGroups, setMetadataGroups] = useState<MetadataGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [metadataResults, setMetadataResults] = useState<MetadataResults | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [filteredDocuments, setFilteredDocuments] = useState<DocumentMetadata[]>([]);
  const [exportFormat, setExportFormat] = useState<'excel' | 'csv'>('excel');
  const [isExporting, setIsExporting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [paginatedDocuments, setPaginatedDocuments] = useState<DocumentMetadata[]>([]);
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [showColumnFilter, setShowColumnFilter] = useState(false);
  const [viewContentModal, setViewContentModal] = useState<{open: boolean, content: string, title: string}>({open: false, content: '', title: ''});

  useEffect(() => {
    loadMetadataGroups();
    loadMetadataResults();
  }, [collectionId]);

  useEffect(() => {
    if (metadataResults) {
      const filtered = metadataResults.documents.filter(doc => {
        const searchLower = searchTerm.toLowerCase();
        return (
          doc.file_name.toLowerCase().includes(searchLower) ||
          doc.entity_name?.toLowerCase().includes(searchLower) ||
          Object.values(doc.metadata).some(value => 
            value.toLowerCase().includes(searchLower)
          )
        );
      });
      setFilteredDocuments(filtered);
      setCurrentPage(1); // Reset to first page when search changes
    }
  }, [searchTerm, metadataResults]);

  // Pagination effect
  useEffect(() => {
    const startIndex = (currentPage - 1) * pageSize;
    const endIndex = startIndex + pageSize;
    setPaginatedDocuments(filteredDocuments.slice(startIndex, endIndex));
  }, [currentPage, pageSize, filteredDocuments]);

  const totalPages = Math.max(1, Math.ceil(filteredDocuments.length / pageSize));

  const loadMetadataGroups = async () => {
    try {
      // Load only groups that have extraction results for this collection
      const response = await apiService.getExtractedMetadataGroups(collectionId);
      // Handle both old format (array) and new format ({groups: [], total: number})
      if (Array.isArray(response)) {
        setMetadataGroups(response);
      } else if (response && response.groups) {
        setMetadataGroups(response.groups);
      } else {
        setMetadataGroups([]);
      }
    } catch (error) {
      console.error('Error loading extracted metadata groups:', error);
      setMetadataGroups([]);
    }
  };

  const loadMetadataResults = async (groupId?: number) => {
    try {
      setLoading(true);
      const results = await apiService.getCollectionMetadata(collectionId, groupId || undefined);
      setMetadataResults(results);
      setFilteredDocuments(results.documents);
    } catch (error) {
      console.error('Error loading metadata results:', error);
      toast({
        title: "Error",
        description: "Failed to load metadata results",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleGroupFilter = (groupId: string) => {
    const id = groupId === 'all' ? null : parseInt(groupId);
    setSelectedGroupId(id);
    loadMetadataResults(id || undefined);
  };

  const handleExport = async () => {
    try {
      setIsExporting(true);
      const blob = await apiService.exportCollectionMetadata(
        collectionId, 
        exportFormat,
        selectedGroupId || undefined
      );
      
      // Create download link
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `metadata_${collectionName}_${new Date().toISOString().split('T')[0]}.${exportFormat === 'excel' ? 'xlsx' : 'csv'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);

      toast({
        title: "Success",
        description: `Metadata exported as ${exportFormat.toUpperCase()}`
      });
    } catch (error) {
      console.error('Error exporting metadata:', error);
      toast({
        title: "Error",
        description: "Failed to export metadata",
        variant: "destructive"
      });
    } finally {
      setIsExporting(false);
    }
  };

  // Get all unique metadata keys across all documents
  const allMetadataKeys = useMemo(() => {
    if (!metadataResults || metadataResults.total_documents === 0) {
      return [];
    }
    return Array.from(new Set(
      filteredDocuments.flatMap(doc => Object.keys(doc.metadata))
    )).sort();
  }, [filteredDocuments, metadataResults]);

  // Initialize selected columns with first 4 keys if not set
  useEffect(() => {
    if (allMetadataKeys.length > 0 && selectedColumns.length === 0) {
      setSelectedColumns(allMetadataKeys.slice(0, 4));
    }
  }, [allMetadataKeys, selectedColumns.length]);

  // Get columns to display
  const displayColumns = selectedColumns.length > 0 ? selectedColumns : allMetadataKeys.slice(0, 4);

  const handleColumnToggle = (column: string) => {
    setSelectedColumns(prev => {
      if (prev.includes(column)) {
        return prev.filter(col => col !== column);
      } else if (prev.length < 4) {
        return [...prev, column];
      }
      return prev;
    });
  };

  const truncateText = (text: string, maxLength: number) => {
    if (!text) return '-';
    return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
  };

  const handleViewContent = (title: string, content: string) => {
    setViewContentModal({ open: true, title, content });
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading metadata results...</span>
        </CardContent>
      </Card>
    );
  }

  if (!metadataResults || metadataResults.total_documents === 0) {
    return (
      <Card>
        <CardContent className="text-center py-12">
          <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Metadata Extracted</h3>
          <p className="text-gray-600 mb-6">
            Extract metadata using groups to view results here.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search metadata results..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Group Filter */}
            <Select value={selectedGroupId?.toString() || 'all'} onValueChange={handleGroupFilter}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Filter by group" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Groups</SelectItem>
                {metadataGroups.map(group => (
                  <SelectItem key={group.id} value={group.id.toString()}>
                    {group.name} ({group.document_count || group.metadata_count} docs)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex items-center gap-4">
              {/* Column Filter Button */}
              {allMetadataKeys.length > 4 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowColumnFilter(!showColumnFilter)}
                  className="flex items-center gap-2"
                >
                  <Settings className="h-4 w-4" />
                  Columns
                </Button>
              )}

              {/* Export Options */}
              <div className="flex gap-2">
                <Select value={exportFormat} onValueChange={(value: 'excel' | 'csv') => setExportFormat(value)}>
                  <SelectTrigger className="w-[100px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="excel">Excel</SelectItem>
                    <SelectItem value="csv">CSV</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  onClick={handleExport}
                  disabled={isExporting || filteredDocuments.length === 0}
                  className="flex items-center gap-2"
                >
                  {isExporting ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="h-4 w-4" />
                  )}
                  Export
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Column Selection Dialog */}
      {showColumnFilter && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Select Columns to Display (Max 4)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {allMetadataKeys.map(key => (
                <div key={key} className="flex items-center space-x-2">
                  <Checkbox
                    id={`col-${key}`}
                    checked={selectedColumns.includes(key)}
                    onCheckedChange={() => handleColumnToggle(key)}
                    disabled={!selectedColumns.includes(key) && selectedColumns.length >= 4}
                  />
                  <label
                    htmlFor={`col-${key}`}
                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                  >
                    {key}
                  </label>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Results Summary */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg">Metadata Results</CardTitle>
            <Badge variant="secondary">
              {filteredDocuments.length} document{filteredDocuments.length !== 1 ? 's' : ''}
            </Badge>
          </div>
        </CardHeader>
      </Card>

      {/* Results Table */}
      {filteredDocuments.length > 0 ? (
        <>
          <Card>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left p-4 font-medium text-gray-900" style={{width: '10%'}}>Document</th>
                    {displayColumns.map(key => {
                      // Calculate dynamic width based on number of columns
                      const columnWidth = displayColumns.length === 1 ? '90%' : 
                                        displayColumns.length === 2 ? '45%' : 
                                        displayColumns.length === 3 ? '30%' : '22.5%';
                      return (
                        <th key={key} className="text-left p-4 font-medium text-gray-900" style={{width: columnWidth}}>
                          {key}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {paginatedDocuments.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-gray-50">
                    <td className="p-4" style={{width: '10%'}}>
                      <div className="break-words">
                        <p className="font-medium text-sm break-words">{doc.file_name}</p>
                        {doc.entity_name && (
                          <p className="text-xs text-gray-600 break-words mt-1">{doc.entity_name}</p>
                        )}
                      </div>
                    </td>
                    {displayColumns.map(key => {
                      const value = doc.metadata[key] || '-';
                      // Dynamically set max length based on number of columns
                      const maxLength = displayColumns.length === 1 ? 300 : 
                                      displayColumns.length === 2 ? 150 : 
                                      displayColumns.length === 3 ? 100 : 75;
                      const isLong = value.length > maxLength;
                      const columnWidth = displayColumns.length === 1 ? '90%' : 
                                        displayColumns.length === 2 ? '45%' : 
                                        displayColumns.length === 3 ? '30%' : '22.5%';
                      
                      return (
                        <td key={key} className="p-4" style={{width: columnWidth}}>
                          <div className="flex items-start gap-2">
                            <p className="text-sm text-gray-900 break-words flex-1">
                              {truncateText(value, maxLength)}
                            </p>
                            {isLong && (
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 w-6 p-0 flex-shrink-0"
                                onClick={() => handleViewContent(key, value)}
                                title="View full content"
                              >
                                <Eye className="h-3 w-3" />
                              </Button>
                            )}
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          
          {/* Pagination */}
          {filteredDocuments.length > 0 && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="text-sm text-gray-600">
                  Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, filteredDocuments.length)} of {filteredDocuments.length} results
                </div>
                {/* Page Size */}
                <div className="flex items-center gap-2">
                  <Label className="text-sm text-gray-600">Page size:</Label>
                  <Select value={pageSize.toString()} onValueChange={(value) => {
                    setPageSize(Number(value));
                    setCurrentPage(1);
                  }}>
                    <SelectTrigger className="w-[80px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10</SelectItem>
                      <SelectItem value="20">20</SelectItem>
                      <SelectItem value="50">50</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                
                <span className="text-sm text-gray-600">
                  Page {currentPage} of {totalPages}
                </span>
                
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                  disabled={currentPage === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      ) : (
        <Card>
          <CardContent className="text-center py-12">
            <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">
              No results found matching your search criteria.
            </p>
          </CardContent>
        </Card>
      )}

      {/* View Content Modal */}
      <Dialog open={viewContentModal.open} onOpenChange={(open) => setViewContentModal(prev => ({...prev, open}))}>
        <DialogContent className="max-w-2xl max-h-[80vh]">
          <DialogHeader>
            <DialogTitle>{viewContentModal.title}</DialogTitle>
            <DialogDescription>
              Full content for this metadata field
            </DialogDescription>
          </DialogHeader>
          <div className="mt-4 p-4 bg-gray-50 rounded-lg overflow-auto max-h-[60vh]">
            <pre className="whitespace-pre-wrap text-sm">{viewContentModal.content}</pre>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}