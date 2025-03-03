"use client";

import React, { useState, useEffect, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { 
  Play, 
  Database, 
  FileText,
  Users,
  Calendar,
  AlertCircle,
  Loader2,
  Info,
  CheckCircle2,
  Search,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Tag,
  FileQuestion
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';

interface ExtractMetadataTabProps {
  collectionId: number;
  collectionName: string;
  totalDocuments: number;
  onExtractionStarted?: () => void;
}

interface MetadataConfiguration {
  id: number;
  metadata_name: string;
  description?: string;
  extraction_prompt: string;
  data_type: string;
  validation_rules?: any;
  display_order?: number;
}

interface MetadataGroup {
  id: number;
  name: string;
  description?: string;
  metadata_count: number;
  configuration_count: number;
  created_at: string;
  configurations?: MetadataConfiguration[];
}

interface Document {
  id: number;
  file_name: string;
  entity_name?: string;
  status: string;
}

interface DocumentsResponse {
  documents: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export function ExtractMetadataTab({ 
  collectionId, 
  collectionName, 
  totalDocuments,
  onExtractionStarted 
}: ExtractMetadataTabProps) {
  const [loading, setLoading] = useState(true);
  const [metadataGroups, setMetadataGroups] = useState<MetadataGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [allDocuments, setAllDocuments] = useState<Document[]>([]);
  const [selectAll, setSelectAll] = useState(false);
  const [selectAllPages, setSelectAllPages] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [showDocumentSelection, setShowDocumentSelection] = useState(false);
  const [showSuccessDialog, setShowSuccessDialog] = useState(false);
  const [extractionJobId, setExtractionJobId] = useState<string>('');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalDocumentsCount, setTotalDocumentsCount] = useState(0);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [showFieldDetails, setShowFieldDetails] = useState(false);
  const pageSize = 50;

  useEffect(() => {
    loadMetadataGroups();
  }, [collectionId]);

  useEffect(() => {
    if (showDocumentSelection) {
      loadDocuments();
    }
  }, [collectionId, showDocumentSelection, currentPage, searchTerm]);

  const loadMetadataGroups = async () => {
    try {
      const response = await apiService.getMetadataGroups();
      // Handle both old format (array) and new format ({groups: [], total: number})
      if (Array.isArray(response)) {
        setMetadataGroups(response);
      } else if (response && response.groups) {
        // The API returns groups with configurations included
        setMetadataGroups(response.groups);
      } else {
        setMetadataGroups([]);
      }
    } catch (error) {
      console.error('Error loading metadata groups:', error);
      toast({
        title: "Error",
        description: "Failed to load metadata groups",
        variant: "destructive"
      });
      setMetadataGroups([]);
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      setLoadingDocuments(true);
      const response = await apiService.getCollectionDetails(
        collectionId, 
        currentPage, 
        pageSize, 
        searchTerm
      );
      
      if (response.documents) {
        setDocuments(response.documents);
        setTotalDocumentsCount(response.total || response.documents.length);
        setTotalPages(response.total_pages || Math.ceil((response.total || response.documents.length) / pageSize));
        
        // Load all documents only if select all pages is checked
        if (selectAllPages && !allDocuments.length) {
          loadAllDocuments();
        }
      }
    } catch (error) {
      console.error('Error loading documents:', error);
      toast({
        title: "Error",
        description: "Failed to load documents",
        variant: "destructive"
      });
    } finally {
      setLoadingDocuments(false);
    }
  };

  const loadAllDocuments = async () => {
    try {
      let allDocs: Document[] = [];
      let page = 1;
      let hasMore = true;
      
      while (hasMore) {
        const response = await apiService.getCollectionDetails(
          collectionId,
          page,
          100, // Larger page size for bulk loading
          searchTerm
        );
        
        if (response.documents) {
          allDocs = [...allDocs, ...response.documents];
          hasMore = response.documents.length === 100;
          page++;
        } else {
          hasMore = false;
        }
      }
      
      setAllDocuments(allDocs);
      setSelectedDocumentIds(allDocs.map(doc => doc.id));
    } catch (error) {
      console.error('Error loading all documents:', error);
      toast({
        title: "Error",
        description: "Failed to load all documents",
        variant: "destructive"
      });
    }
  };

  const handleSelectAllToggle = () => {
    if (selectAll) {
      // Deselect all on current page
      const currentPageIds = documents.map(doc => doc.id);
      setSelectedDocumentIds(prev => prev.filter(id => !currentPageIds.includes(id)));
    } else {
      // Select all on current page
      const currentPageIds = documents.map(doc => doc.id);
      setSelectedDocumentIds(prev => {
        const newIds = [...prev];
        currentPageIds.forEach(id => {
          if (!newIds.includes(id)) {
            newIds.push(id);
          }
        });
        return newIds;
      });
    }
    setSelectAll(!selectAll);
  };

  const handleSelectAllPagesToggle = async () => {
    if (selectAllPages) {
      // Deselect all
      setSelectedDocumentIds([]);
      setAllDocuments([]);
      setSelectAll(false);
    } else {
      // Select all pages
      if (!allDocuments.length) {
        await loadAllDocuments();
      } else {
        setSelectedDocumentIds(allDocuments.map(doc => doc.id));
      }
    }
    setSelectAllPages(!selectAllPages);
  };

  // Check if all documents on current page are selected
  useEffect(() => {
    if (documents.length > 0) {
      const allCurrentPageSelected = documents.every(doc => selectedDocumentIds.includes(doc.id));
      setSelectAll(allCurrentPageSelected);
    }
  }, [selectedDocumentIds, documents]);

  const handleDocumentToggle = (docId: number) => {
    setSelectedDocumentIds(prev => {
      if (prev.includes(docId)) {
        return prev.filter(id => id !== docId);
      } else {
        return [...prev, docId];
      }
    });
  };

  const handleStartExtraction = async () => {
    if (!selectedGroupId) {
      toast({
        title: "Error",
        description: "Please select a metadata group",
        variant: "destructive"
      });
      return;
    }

    try {
      setIsExtracting(true);

      const payload = {
        group_id: selectedGroupId,
        document_ids: showDocumentSelection && selectedDocumentIds.length > 0 
          ? selectedDocumentIds 
          : undefined // undefined means all documents
      };

      const response = await apiService.extractMetadataForCollection(
        collectionId,
        selectedGroupId,
        payload.document_ids
      );

      // Store job ID and show success dialog
      setExtractionJobId(response.job_id);
      setShowSuccessDialog(true);

      // Reset selections
      setSelectedGroupId(null);
      setSelectedDocumentIds([]);
      setSelectAll(false);
      setShowDocumentSelection(false);

    } catch (error: any) {
      console.error('Error starting extraction:', error);
      
      if (error.response?.status === 409) {
        toast({
          title: "Extraction Already Running",
          description: error.response?.data?.detail || "An extraction job is already in progress for this collection and group.",
          variant: "destructive"
        });
      } else {
        toast({
          title: "Error",
          description: "Failed to start metadata extraction",
          variant: "destructive"
        });
      }
    } finally {
      setIsExtracting(false);
    }
  };

  const selectedGroup = metadataGroups.find(g => g.id === selectedGroupId);
  const documentCount = showDocumentSelection && selectedDocumentIds.length > 0 
    ? selectedDocumentIds.length 
    : totalDocuments;

  // Filtered documents for search
  const displayedSelectedCount = useMemo(() => {
    if (!showDocumentSelection) return 0;
    return selectedDocumentIds.length;
  }, [showDocumentSelection, selectedDocumentIds]);

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading extraction options...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Information Alert */}
      <Alert>
        <Info className="h-4 w-4" />
        <AlertDescription>
          Extract metadata from documents using predefined extraction groups. Select a metadata group and optionally choose specific documents to process.
        </AlertDescription>
      </Alert>

      {/* Metadata Group Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Select Metadata Group
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <Select
              value={selectedGroupId?.toString() || ""}
              onValueChange={(value) => {
                setSelectedGroupId(Number(value));
                setShowFieldDetails(false); // Reset field details view on selection change
              }}
            >
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Choose a metadata group to extract" />
              </SelectTrigger>
              <SelectContent>
                {metadataGroups.map(group => (
                  <SelectItem key={group.id} value={group.id.toString()}>
                    <div className="flex items-center justify-between w-full">
                      <span>{group.name}</span>
                      <Badge variant="secondary" className="ml-2">
                        {group.configuration_count || group.metadata_count || 0} fields
                      </Badge>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {selectedGroup && (
              <div className="mt-4 space-y-4">
                <div className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 space-y-1">
                      <h4 className="font-medium text-sm text-gray-700">Selected Group Details</h4>
                      <div className="mt-2 space-y-1">
                        <p className="text-sm"><span className="font-medium">Name:</span> {selectedGroup.name}</p>
                        {selectedGroup.description && (
                          <p className="text-sm"><span className="font-medium">Description:</span> {selectedGroup.description}</p>
                        )}
                        <p className="text-sm"><span className="font-medium">Total Fields:</span> {selectedGroup.configuration_count || selectedGroup.metadata_count || 0}</p>
                        <p className="text-sm"><span className="font-medium">Created:</span> {new Date(selectedGroup.created_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowFieldDetails(!showFieldDetails)}
                      className="ml-2"
                    >
                      {showFieldDetails ? (
                        <>
                          <ChevronUp className="h-4 w-4 mr-1" />
                          Hide Fields
                        </>
                      ) : (
                        <>
                          <ChevronDown className="h-4 w-4 mr-1" />
                          Show Fields
                        </>
                      )}
                    </Button>
                  </div>
                </div>

                {/* Metadata Fields Details */}
                {showFieldDetails && selectedGroup.configurations && (
                  <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                    <h5 className="font-medium text-sm text-blue-900 mb-3 flex items-center gap-2">
                      <Tag className="h-4 w-4" />
                      Metadata Fields ({selectedGroup.configurations.length})
                    </h5>
                    <TooltipProvider>
                      <div className="space-y-2 max-h-64 overflow-y-auto">
                        {selectedGroup.configurations.length > 0 ? (
                          selectedGroup.configurations.map((field, index) => (
                            <div key={field.id} className="p-3 bg-white rounded border border-gray-200 hover:border-blue-300 transition-colors">
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2">
                                    <span className="text-sm font-medium text-gray-900">
                                      {field.metadata_name}
                                    </span>
                                    <Badge variant="secondary" className="text-xs">
                                      {field.data_type}
                                    </Badge>
                                  </div>
                                  {field.description && (
                                    <p className="text-xs text-gray-600 mt-1">{field.description}</p>
                                  )}
                                  <div className="mt-2 flex items-start gap-2">
                                    <Tooltip>
                                      <TooltipTrigger asChild>
                                        <button className="flex items-start gap-2 text-left hover:bg-gray-50 rounded p-1 -m-1 transition-colors">
                                          <FileQuestion className="h-3 w-3 text-gray-400 mt-0.5 flex-shrink-0" />
                                          <p className="text-xs text-gray-500 italic">
                                            {field.extraction_prompt.length > 100 
                                              ? field.extraction_prompt.substring(0, 100) + '...'
                                              : field.extraction_prompt
                                            }
                                          </p>
                                        </button>
                                      </TooltipTrigger>
                                      <TooltipContent side="top" className="max-w-sm">
                                        <p className="text-xs whitespace-pre-wrap">{field.extraction_prompt}</p>
                                      </TooltipContent>
                                    </Tooltip>
                                  </div>
                                  {field.validation_rules && Object.keys(field.validation_rules).length > 0 && (
                                    <div className="mt-2 flex items-center gap-2">
                                      <Badge variant="outline" className="text-xs">
                                        Has validation rules
                                      </Badge>
                                    </div>
                                  )}
                                </div>
                                <span className="text-xs text-gray-400 ml-2">#{index + 1}</span>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-gray-600 text-center py-4">
                            No fields configured for this group
                          </p>
                        )}
                      </div>
                    </TooltipProvider>
                    {selectedGroup.configurations.length > 5 && (
                      <p className="text-xs text-blue-700 mt-2 text-center">
                        Scroll to see all {selectedGroup.configurations.length} fields
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Document Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Document Selection
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setShowDocumentSelection(!showDocumentSelection);
                if (!showDocumentSelection) {
                  // Reset to first page when opening
                  setCurrentPage(1);
                  setSearchTerm('');
                }
              }}
            >
              {showDocumentSelection ? 'Use All Documents' : 'Select Specific Documents'}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!showDocumentSelection ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-600">All {totalDocuments} documents in the collection will be processed</p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Search Bar */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <Input
                  type="text"
                  placeholder="Search documents by name..."
                  value={searchTerm}
                  onChange={(e) => {
                    setSearchTerm(e.target.value);
                    setCurrentPage(1); // Reset to first page on search
                  }}
                  className="pl-10"
                />
              </div>

              {/* Selection Controls */}
              <div className="flex items-center justify-between pb-4 border-b">
                <div className="space-y-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="select-all"
                      checked={selectAll}
                      onCheckedChange={handleSelectAllToggle}
                      disabled={loadingDocuments}
                    />
                    <label htmlFor="select-all" className="text-sm font-medium cursor-pointer">
                      Select all on this page
                    </label>
                  </div>
                  {totalDocumentsCount > pageSize && (
                    <div className="flex items-center space-x-2 pl-6">
                      <Checkbox
                        id="select-all-pages"
                        checked={selectAllPages}
                        onCheckedChange={handleSelectAllPagesToggle}
                        disabled={loadingDocuments}
                      />
                      <label htmlFor="select-all-pages" className="text-sm font-medium cursor-pointer text-blue-600">
                        Select all {totalDocumentsCount} documents
                      </label>
                    </div>
                  )}
                </div>
                <div className="text-right">
                  <Badge variant="secondary">
                    {displayedSelectedCount} of {totalDocumentsCount} selected
                  </Badge>
                  {searchTerm && (
                    <p className="text-xs text-gray-600 mt-1">
                      Showing results for "{searchTerm}"
                    </p>
                  )}
                </div>
              </div>

              {/* Documents List */}
              {loadingDocuments ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
                  <span className="ml-2 text-gray-600">Loading documents...</span>
                </div>
              ) : documents.length === 0 ? (
                <div className="text-center py-12">
                  <FileText className="h-12 w-12 text-gray-300 mx-auto mb-2" />
                  <p className="text-gray-600">
                    {searchTerm ? `No documents found matching "${searchTerm}"` : 'No documents found'}
                  </p>
                </div>
              ) : (
                <div className="max-h-96 overflow-y-auto space-y-2">
                  {documents.map(doc => (
                    <div key={doc.id} className="flex items-center space-x-2 p-2 hover:bg-gray-50 rounded">
                      <Checkbox
                        id={`doc-${doc.id}`}
                        checked={selectedDocumentIds.includes(doc.id)}
                        onCheckedChange={() => handleDocumentToggle(doc.id)}
                      />
                      <label 
                        htmlFor={`doc-${doc.id}`} 
                        className="flex-1 cursor-pointer text-sm"
                      >
                        <p className="font-medium">{doc.file_name}</p>
                        {doc.entity_name && (
                          <p className="text-xs text-gray-600">{doc.entity_name}</p>
                        )}
                      </label>
                      <Badge variant={doc.status === 'indexed' ? 'secondary' : 'outline'} className="text-xs">
                        {doc.status}
                      </Badge>
                    </div>
                  ))}
                </div>
              )}

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 border-t">
                  <p className="text-sm text-gray-600">
                    Page {currentPage} of {totalPages}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                      disabled={currentPage === 1 || loadingDocuments}
                    >
                      <ChevronLeft className="h-4 w-4 mr-1" />
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                      disabled={currentPage === totalPages || loadingDocuments}
                    >
                      Next
                      <ChevronRight className="h-4 w-4 ml-1" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Extraction Summary and Action */}
      <Card>
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div className="space-y-2">
              <h3 className="font-medium">Ready to Extract</h3>
              {selectedGroupId ? (
                <div className="text-sm text-gray-600 space-y-1">
                  <p className="flex items-center gap-2">
                    <Database className="h-4 w-4" />
                    Group: {selectedGroup?.name}
                  </p>
                  <p className="flex items-center gap-2">
                    <FileText className="h-4 w-4" />
                    Documents: {documentCount}
                  </p>
                  <p className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Estimated fields: {documentCount * (selectedGroup?.configuration_count || selectedGroup?.metadata_count || 0)}
                  </p>
                </div>
              ) : (
                <p className="text-sm text-gray-600">Please select a metadata group to continue</p>
              )}
            </div>
            
            <Button
              size="lg"
              onClick={handleStartExtraction}
              disabled={!selectedGroupId || isExtracting || (showDocumentSelection && selectedDocumentIds.length === 0)}
              className="min-w-[200px]"
            >
              {isExtracting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Starting Extraction...
                </>
              ) : (
                <>
                  <Play className="mr-2 h-4 w-4" />
                  Start Extraction
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Success Dialog */}
      <Dialog open={showSuccessDialog} onOpenChange={setShowSuccessDialog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-5 w-5 text-green-600" />
              Extraction Started Successfully
            </DialogTitle>
            <DialogDescription className="pt-3">
              Your metadata extraction job has been started successfully. 
              You can monitor the progress in the extraction history tab.
            </DialogDescription>
          </DialogHeader>
          <div className="flex items-center space-x-2 text-sm text-gray-600 mt-2">
            <Badge variant="secondary">Job ID: {extractionJobId}</Badge>
          </div>
          <DialogFooter className="mt-4">
            <Button
              variant="outline"
              onClick={() => setShowSuccessDialog(false)}
            >
              Stay Here
            </Button>
            <Button
              onClick={() => {
                setShowSuccessDialog(false);
                if (onExtractionStarted) {
                  onExtractionStarted();
                }
              }}
              className="bg-blue-600 hover:bg-blue-700"
            >
              View Progress
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}