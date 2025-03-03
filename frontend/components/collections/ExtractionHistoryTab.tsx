"use client";

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { 
  RefreshCw, 
  User, 
  Clock, 
  CheckCircle2, 
  AlertCircle,
  Loader2,
  Calendar,
  Filter,
  FileText,
  ChevronLeft,
  ChevronRight,
  Square
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';
import { formatDistanceToNow } from 'date-fns';

interface ExtractionHistoryTabProps {
  collectionId: number;
  collectionName: string;
}

interface DocumentPreview {
  id: number;
  file_name: string;
  entity_name?: string;
}

interface ExtractionJob {
  job_id: number;
  collection_id: number;
  collection_name: string;
  group_id: number;
  group_name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  total_documents: number;
  processed_documents: number;
  failed_documents: number;
  progress_percentage: number;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  created_by: number;
  created_by_name: string;
  error_details?: string | { message: string; [key: string]: any };
  documents_preview?: DocumentPreview[];
}

export function ExtractionHistoryTab({ collectionId, collectionName }: ExtractionHistoryTabProps) {
  const [loading, setLoading] = useState(true);
  const [jobs, setJobs] = useState<ExtractionJob[]>([]);
  const [myJobsOnly, setMyJobsOnly] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalJobs, setTotalJobs] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState<NodeJS.Timeout | null>(null);

  const loadExtractionJobs = useCallback(async () => {
    try {
      const response = await apiService.getCollectionExtractionJobs(
        collectionId, 
        myJobsOnly,
        statusFilter,
        currentPage,
        pageSize
      );
      
      console.log('Extraction jobs response:', response);
      
      // Debug: Log timestamp format for first job
      if (response && (Array.isArray(response) ? response[0] : response.jobs?.[0])) {
        const firstJob = Array.isArray(response) ? response[0] : response.jobs[0];
        console.log('First job timestamps:', {
          created_at: firstJob.created_at,
          started_at: firstJob.started_at,
          completed_at: firstJob.completed_at,
        });
      }
      
      // Handle both old format (array) and new format (paginated response)
      if (Array.isArray(response)) {
        // Old format - backward compatibility
        setJobs(response);
        setTotalJobs(response.length);
        setTotalPages(Math.max(1, Math.ceil(response.length / pageSize)));
      } else if (response && response.jobs) {
        // New paginated format
        setJobs(response.jobs || []);
        setTotalJobs(response.total || 0);
        setTotalPages(response.total_pages || 1);
      } else {
        // Fallback for unexpected response format
        console.error('Unexpected response format:', response);
        setJobs([]);
        setTotalJobs(0);
        setTotalPages(1);
      }
      
      // If any jobs are active, continue auto-refresh
      const jobsList = Array.isArray(response) ? response : (response?.jobs || []);
      const hasActiveJobs = Array.isArray(jobsList) && jobsList.some((job: ExtractionJob) => 
        job.status === 'pending' || job.status === 'processing'
      );
      
      if (!hasActiveJobs && autoRefresh) {
        setAutoRefresh(false);
      }
    } catch (error) {
      console.error('Error loading extraction jobs:', error);
      toast({
        title: "Error",
        description: "Failed to load extraction history",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  }, [collectionId, myJobsOnly, statusFilter, currentPage, pageSize]);

  useEffect(() => {
    loadExtractionJobs();
  }, [loadExtractionJobs]);

  useEffect(() => {
    // Reset to first page when filters or page size change
    setCurrentPage(1);
  }, [myJobsOnly, statusFilter, pageSize]);

  // Auto-refresh logic
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadExtractionJobs, 5000); // Refresh every 5 seconds
      setRefreshInterval(interval);
      return () => clearInterval(interval);
    } else if (refreshInterval) {
      clearInterval(refreshInterval);
      setRefreshInterval(null);
    }
  }, [autoRefresh, loadExtractionJobs]);

  const handleStopJob = async (jobId: number) => {
    try {
      // Call API to stop the job
      await apiService.stopExtractionJob(jobId);
      
      toast({
        title: "Success",
        description: "Extraction job stopped successfully",
      });
      
      // Reload the jobs list to show updated status
      loadExtractionJobs();
    } catch (error) {
      console.error('Error stopping extraction job:', error);
      toast({
        title: "Error",
        description: "Failed to stop extraction job",
        variant: "destructive"
      });
    }
  };

  const getStatusBadge = (status: string, progress?: number, errorDetails?: any) => {
    // Check if this is a user-stopped job
    const isStoppedByUser = status === 'failed' && 
                           typeof errorDetails === 'object' && 
                           errorDetails?.message?.toLowerCase().includes('stopped by user');
    
    if (isStoppedByUser) {
      return <Badge variant="secondary" className="bg-gray-100 text-gray-700">
        <Square className="h-3 w-3 mr-1" />Stopped
      </Badge>;
    }
    
    switch (status) {
      case 'pending':
        return <Badge variant="secondary" className="bg-gray-100"><Clock className="h-3 w-3 mr-1" />Pending</Badge>;
      case 'processing':
        return <Badge variant="secondary" className="bg-blue-100 text-blue-800">
          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
          Processing {progress ? `(${Math.round(progress)}%)` : ''}
        </Badge>;
      case 'completed':
        return <Badge variant="secondary" className="bg-green-100 text-green-800">
          <CheckCircle2 className="h-3 w-3 mr-1" />Completed
        </Badge>;
      case 'failed':
        return <Badge variant="destructive"><AlertCircle className="h-3 w-3 mr-1" />Failed</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  const formatDuration = (start?: string, end?: string) => {
    if (!start) return '-';
    // Parse dates ensuring consistent timezone handling
    const startDate = new Date(start);
    const endDate = end ? new Date(end) : new Date();
    
    // If the dates are in UTC format (ending with 'Z' or containing timezone info), 
    // they'll be parsed correctly. Calculate duration in milliseconds
    const duration = Math.floor((endDate.getTime() - startDate.getTime()) / 1000);
    
    if (duration < 0) return '0s'; // Handle negative durations
    if (duration < 60) return `${duration}s`;
    if (duration < 3600) return `${Math.floor(duration / 60)}m ${duration % 60}s`;
    return `${Math.floor(duration / 3600)}h ${Math.floor((duration % 3600) / 60)}m`;
  };

  const DocumentTooltip = ({ documents, totalCount }: { documents?: DocumentPreview[], totalCount: number }) => {
    if (!documents || documents.length === 0) return null;
    
    const displayDocs = documents;
    const remaining = totalCount - documents.length;
    
    return (
      <div className="space-y-1">
        <p className="font-semibold text-sm mb-2">Documents ({totalCount} total):</p>
        {displayDocs.map((doc, idx) => (
          <div key={doc.id} className="text-xs">
            <span className="font-medium">{idx + 1}.</span> {doc.file_name}
            {doc.entity_name && (
              <span className="text-gray-500 ml-1">({doc.entity_name})</span>
            )}
          </div>
        ))}
        {remaining > 0 && (
          <p className="text-xs text-gray-500 italic">...and {remaining} more documents</p>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
          <span className="ml-2 text-gray-600">Loading extraction history...</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <TooltipProvider>
      <div className="space-y-4">
        {/* Controls */}
        <Card>
          <CardContent className="p-4">
            <div className="flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-4">
                {/* Status Filter */}
                <div className="flex items-center gap-2">
                  <Filter className="h-4 w-4 text-gray-500" />
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger className="w-[150px]">
                      <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="processing">Processing</SelectItem>
                      <SelectItem value="completed">Completed</SelectItem>
                      <SelectItem value="failed">Failed</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                
                {/* My Jobs Filter */}
                <div className="flex items-center space-x-2">
                  <Switch
                    id="my-jobs"
                    checked={myJobsOnly}
                    onCheckedChange={setMyJobsOnly}
                  />
                  <Label htmlFor="my-jobs" className="cursor-pointer">
                    My Jobs Only
                  </Label>
                </div>
                
                {/* Auto-refresh */}
                <div className="flex items-center space-x-2">
                  <Switch
                    id="auto-refresh"
                    checked={autoRefresh}
                    onCheckedChange={setAutoRefresh}
                  />
                  <Label htmlFor="auto-refresh" className="cursor-pointer">
                    Auto-refresh
                  </Label>
                </div>
                
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={loadExtractionJobs}
                disabled={loading}
              >
                <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Jobs List */}
        {!jobs || jobs.length === 0 ? (
          <Card>
            <CardContent className="text-center py-12">
              <Calendar className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Extraction History</h3>
              <p className="text-gray-600">
                {statusFilter !== 'all' 
                  ? `No ${statusFilter} extraction jobs found.`
                  : myJobsOnly 
                    ? "You haven't started any extraction jobs yet." 
                    : "No extraction jobs have been started for this collection."}
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            <div className="space-y-3">
              {jobs && jobs.map((job) => (
                <Card key={job.job_id} className="hover:shadow-md transition-shadow">
                  <CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="space-y-2 flex-1">
                        <div className="flex items-center gap-3">
                          <h3 className="font-medium">{job.group_name}</h3>
                          {getStatusBadge(job.status, job.progress_percentage, job.error_details)}
                          
                          {/* Document preview tooltip */}
                          {job.documents_preview && job.documents_preview.length > 0 && (
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <div className="flex items-center gap-1 text-sm text-gray-600 cursor-help">
                                  <FileText className="h-4 w-4" />
                                  <span>{job.total_documents} docs</span>
                                </div>
                              </TooltipTrigger>
                              <TooltipContent side="right" className="max-w-xs">
                                <DocumentTooltip documents={job.documents_preview} totalCount={job.total_documents} />
                              </TooltipContent>
                            </Tooltip>
                          )}
                        </div>
                        
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span className="flex items-center gap-1">
                            <User className="h-3 w-3" />
                            {job.created_by_name}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            Started: {(() => {
                              const dateStr = job.started_at || job.created_at;
                              const date = new Date(dateStr);
                              // Ensure we're displaying in local timezone consistently
                              return date.toLocaleString();
                            })()}
                          </span>
                          {job.started_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              Duration: {formatDuration(job.started_at, job.completed_at)}
                            </span>
                          )}
                        </div>

                        <div className="text-sm">
                          Progress: {job.processed_documents}/{job.total_documents} documents
                          {job.failed_documents > 0 && (
                            <span className="text-red-600 ml-2">
                              ({job.failed_documents} failed)
                            </span>
                          )}
                        </div>

                        {job.status === 'processing' && (
                          <div className="w-full bg-gray-200 rounded-full h-2">
                            <div 
                              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${job.progress_percentage}%` }}
                            />
                          </div>
                        )}

                        {job.error_details && (
                          (() => {
                            // Check if this is a user-stopped job
                            const isStoppedByUser = typeof job.error_details === 'object' && 
                                                   (job.error_details as any)?.message?.toLowerCase().includes('stopped by user');
                            
                            if (isStoppedByUser) {
                              // Show a neutral info message for stopped jobs
                              const stoppedAt = (job.error_details as any)?.stopped_at;
                              return (
                                <div className="mt-2 p-2 bg-gray-50 border border-gray-200 rounded text-sm text-gray-700">
                                  <div className="flex items-center gap-2">
                                    <Square className="h-4 w-4 text-gray-500" />
                                    <span>Stopped by user</span>
                                    {stoppedAt && (
                                      <span className="text-gray-500">
                                        at {new Date(stoppedAt).toLocaleString()}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            }
                            
                            // Show error message for actual errors
                            let errorMessage = '';
                            if (typeof job.error_details === 'string') {
                              errorMessage = job.error_details;
                            } else if (typeof job.error_details === 'object') {
                              // Extract a user-friendly message from the error object
                              const errorObj = job.error_details as any;
                              errorMessage = errorObj.message || errorObj.error || errorObj.detail || 'An error occurred during extraction';
                              
                              // If there are additional details, append them (but not the whole JSON)
                              if (errorObj.details && typeof errorObj.details === 'string') {
                                errorMessage += `: ${errorObj.details}`;
                              }
                            } else {
                              errorMessage = 'An unexpected error occurred';
                            }
                            
                            return (
                              <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-800">
                                <div className="flex items-start gap-2">
                                  <AlertCircle className="h-4 w-4 mt-0.5 flex-shrink-0" />
                                  <span>{errorMessage}</span>
                                </div>
                              </div>
                            );
                          })()
                        )}
                      </div>
                      
                      {/* Stop button for processing jobs */}
                      {job.status === 'processing' && (
                        <div className="ml-4">
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleStopJob(job.job_id)}
                            className="flex items-center gap-2"
                          >
                            <Square className="h-3 w-3" />
                            Stop
                          </Button>
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
            
            {/* Pagination */}
            {totalJobs > 0 && (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="text-sm text-gray-600">
                    Showing {Math.min((currentPage - 1) * pageSize + 1, totalJobs)} to {Math.min(currentPage * pageSize, totalJobs)} of {totalJobs} jobs
                  </div>
                  {/* Page Size */}
                  <div className="flex items-center gap-2">
                    <Label className="text-sm text-gray-600">Page size:</Label>
                    <Select value={pageSize.toString()} onValueChange={(value) => setPageSize(Number(value))}>
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
                {totalPages > 1 && (
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
                )}
              </div>
            )}
          </>
        )}
      </div>
    </TooltipProvider>
  );
}