"use client";

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { 
  Eye, 
  Play, 
  FileText, 
  Database, 
  CheckCircle, 
  XCircle, 
  Clock,
  AlertCircle,
  Info,
  Download,
  Loader2,
  RefreshCw,
  Trash2,
  FileSpreadsheet,
  ExternalLink,
  Copy,
  Link,
  Bug,
  FileSearch,
  X,
  Search,
  Filter
} from 'lucide-react';
import { toast } from 'sonner';
import { apiService } from '@/services/api';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import * as XLSX from 'xlsx';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface SourceFile {
  id: number;
  file_name: string;
  file_url: string;
  drug_name?: string;
  us_ma_date?: string;
  status: string;
  metadata_extracted: boolean;
  metadata_count: number;
  extracted_metadata_names: string[];
  created_at?: string;
  updated_at?: string;
}

interface ExtractedMetadata {
  id: number;
  metadata_name: string;
  value: string;
  drugname?: string;
  confidence_score?: number;
  extraction_prompt?: string;
  created_at?: string;
  updated_at?: string;
  metadata_details?: string;
}

interface DocumentMetadata {
  file_name?: string;
  drug_name?: string;
  page_number?: number;
  page_num?: number; // Sometimes it's stored as page_num
  original_content?: string;
  content?: string; // Sometimes it's stored as content
  [key: string]: any; // Allow other fields
}

interface MetadataViewData {
  source_file_id: number;
  file_name: string;
  file_url: string;
  drug_name?: string;
  metadata_extracted: boolean;
  metadata_count: number;
  metadata: ExtractedMetadata[];
}

export default function ViewMetadataPage() {
  const [sourceFiles, setSourceFiles] = useState<SourceFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [extractingMetadata, setExtractingMetadata] = useState<number | null>(null);
  const [viewingMetadata, setViewingMetadata] = useState<MetadataViewData | null>(null);
  const [viewingSourceFile, setViewingSourceFile] = useState<SourceFile | null>(null);
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [reExtractLoading, setReExtractLoading] = useState(false);
  const [showReExtractDialog, setShowReExtractDialog] = useState(false);
  const [lastDebugSessionId, setLastDebugSessionId] = useState<string | null>(null);
  const [showDocMetadataDialog, setShowDocMetadataDialog] = useState(false);
  const [selectedDocMetadata, setSelectedDocMetadata] = useState<DocumentMetadata[]>([]);
  const [selectedMetadataName, setSelectedMetadataName] = useState<string>('');
  const [downloadingAll, setDownloadingAll] = useState(false);
  const [sequentialExtracting, setSequentialExtracting] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  
  // Stats state
  const [stats, setStats] = useState({
    total: 0,
    readyForExtraction: 0,
    metadataExtracted: 0,
    totalMetadataFields: 0
  });

  useEffect(() => {
    fetchSourceFiles(1);
    fetchStats();
  }, []);

  // Auto-refresh functionality
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchSourceFiles(currentPage);
        fetchStats();
      }, 5000); // Refresh every 5 seconds

      return () => clearInterval(interval);
    }
  }, [autoRefresh, currentPage]);
  
  // Reload when filters change
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchSourceFiles(1); // Reset to first page when filters change
    }, 300);
    
    return () => clearTimeout(timer);
  }, [statusFilter, searchTerm, pageSize]);

  const fetchSourceFiles = async (page: number = 1) => {
    try {
      setRefreshing(true);
      
      const offset = (page - 1) * pageSize;
      
      const response = await apiService.getSourceFilesForMetadata({
        limit: pageSize,
        offset: offset,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchTerm || undefined
      });
      
      setSourceFiles(response.source_files);
      setTotalCount(response.total_count);
      setTotalPages(Math.ceil(response.total_count / pageSize));
      setCurrentPage(page);
    } catch (error) {
      console.error('Error fetching source files:', error);
      toast.error('Failed to load source files');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };
  
  const fetchStats = async () => {
    try {
      const statsData = await apiService.getMetadataExtractionStats();
      setStats(statsData);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const handleExtractMetadata = async (sourceFileId: number) => {
    try {
      setExtractingMetadata(sourceFileId);
      
      const response = await apiService.extractMetadata(sourceFileId);

      if (response.success) {
        toast.success(response.message);
        // Save debug session ID if available
        if (response.debug_session_id) {
          setLastDebugSessionId(response.debug_session_id);
        }
        // Refresh the source files list to show updated status
        await fetchSourceFiles(currentPage);
        await fetchStats();
      } else {
        toast.error(response.error || 'Failed to extract metadata');
      }
    } catch (error: any) {
      console.error('Error extracting metadata:', error);
      toast.error(error.message || 'Failed to extract metadata');
    } finally {
      setExtractingMetadata(null);
    }
  };

  const handleViewMetadata = async (sourceFileId: number) => {
    try {
      const response = await apiService.viewExtractedMetadata(sourceFileId);
      
      if (response.success) {
        setViewingMetadata(response);
        // Find and store the source file info
        const sourceFile = sourceFiles.find(f => f.id === sourceFileId);
        setViewingSourceFile(sourceFile || null);
        setIsViewModalOpen(true);
      } else {
        toast.error(response.error || 'Failed to load metadata');
      }
    } catch (error: any) {
      console.error('Error viewing metadata:', error);
      toast.error(error.message || 'Failed to load metadata');
    }
  };

  const handleDeleteMetadata = async () => {
    if (!viewingMetadata) return;
    setDeleteLoading(true);
    try {
      await apiService.deleteExtractedMetadata(viewingMetadata.source_file_id);
      toast.success('Extracted metadata deleted');
      setIsViewModalOpen(false);
      setShowDeleteDialog(false);
      await fetchSourceFiles(currentPage);
      await fetchStats();
    } catch (error: any) {
      toast.error(error.message || 'Failed to delete metadata');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleReExtractMetadata = async (sourceFileId?: number) => {
    // If sourceFileId is provided, it's from the table, so show confirmation first
    if (sourceFileId) {
      // Find the file details for confirmation dialog
      const file = sourceFiles.find(f => f.id === sourceFileId);
      if (file) {
        setViewingMetadata({
          source_file_id: sourceFileId,
          file_name: file.file_name,
          file_url: file.file_url,
          drug_name: file.drug_name,
          metadata_extracted: file.metadata_extracted,
          metadata_count: file.metadata_count,
          metadata: []
        });
        setShowReExtractDialog(true);
        return;
      }
    }
    
    // Otherwise, proceed with re-extraction (from dialog)
    if (!viewingMetadata) return;
    setReExtractLoading(true);
    setExtractingMetadata(viewingMetadata.source_file_id);
    try {
      const response = await apiService.reExtractMetadata(viewingMetadata.source_file_id);
      
      if (response.success) {
        toast.success('Metadata re-extracted successfully');
        // Save debug session ID if available
        if (response.debug_session_id) {
          setLastDebugSessionId(response.debug_session_id);
        }
        setIsViewModalOpen(false);
        setShowReExtractDialog(false);
        // Refresh the source files list to show updated status
        await fetchSourceFiles(currentPage);
        await fetchStats();
      } else {
        toast.error(response.error || 'Failed to re-extract metadata');
      }
    } catch (error: any) {
      console.error('Error re-extracting metadata:', error);
      toast.error(error.message || 'Failed to re-extract metadata');
    } finally {
      setReExtractLoading(false);
      setExtractingMetadata(null);
    }
  };

  const handleSequentialExtraction = async () => {
    try {
      // Get all files that are eligible for extraction and haven't been extracted yet
      const eligibleFiles = sourceFiles.filter(file => 
        canExtractMetadata(file) && !file.metadata_extracted
      );

      if (eligibleFiles.length === 0) {
        toast.warning('No files eligible for metadata extraction');
        return;
      }

      const fileIds = eligibleFiles.map(file => file.id);
      
      setSequentialExtracting(true);
      
      const result = await apiService.extractMetadataSequential(fileIds);
      
      if (result.success) {
        toast.success(result.message, {
          description: `Processing ${result.total_queued} files sequentially in the background`,
          duration: 5000,
        });
        
        // Enable auto-refresh to monitor progress
        setAutoRefresh(true);
      }
      
    } catch (error: any) {
      console.error('Error starting sequential extraction:', error);
      toast.error(error.message || 'Failed to start sequential extraction');
    } finally {
      setSequentialExtracting(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const statusConfig = {
      'PENDING': { color: 'bg-yellow-100 text-yellow-800', icon: Clock },
      'PROCESSING': { color: 'bg-blue-100 text-blue-800', icon: Loader2 },
      'DOCUMENT_STORED': { color: 'bg-green-100 text-green-800', icon: Database },
      'READY': { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      'COMPLETED': { color: 'bg-green-100 text-green-800', icon: CheckCircle },
      'FAILED': { color: 'bg-red-100 text-red-800', icon: XCircle },
      'ERROR': { color: 'bg-red-100 text-red-800', icon: AlertCircle }
    };

    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig['PENDING'];
    const Icon = config.icon;

    return (
      <Badge className={`${config.color} flex items-center gap-1`}>
        <Icon className="h-3 w-3" />
        {status}
      </Badge>
    );
  };

  const canExtractMetadata = (file: SourceFile) => {
    // Only files that are indexed (READY or COMPLETED) can have metadata extracted
    return ['READY', 'COMPLETED'].includes(file.status);
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatMetadataValue = (value: string) => {
    if (!value) return null;
    
    // Check if value contains HTML tags
    const hasHtmlTags = /<[a-z][\s\S]*>/i.test(value);
    
    if (hasHtmlTags) {
      // Remove HTML tags but preserve structure with line breaks
      const withLineBreaks = value
        .replace(/<\/p>/gi, '\n\n')
        .replace(/<\/div>/gi, '\n')
        .replace(/<\/li>/gi, '\n')
        .replace(/<br\s*\/?>/gi, '\n')
        .replace(/<[^>]*>/g, '')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .trim();
      
      return withLineBreaks;
    }
    
    return value;
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard', {
        duration: 2000,
        position: 'top-right',
      });
    } catch (error) {
      console.error('Copy error:', error);
      toast.error('Failed to copy to clipboard', {
        duration: 2000,
        position: 'top-right',
      });
    }
  };

  const copyAllMetadata = async () => {
    if (!viewingMetadata) return;
    
    const allMetadata = viewingMetadata.metadata
      .filter(m => m.value)
      .map(m => `${m.metadata_name}: ${formatMetadataValue(m.value) || m.value}`)
      .join('\n\n');
    
    if (allMetadata) {
      try {
        await navigator.clipboard.writeText(allMetadata);
        toast.success('All metadata copied to clipboard');
      } catch (error) {
        toast.error('Failed to copy metadata');
      }
    } else {
      toast.warning('No metadata to copy');
    }
  };

  const openFileUrl = (url: string) => {
    if (url) {
      window.open(url, '_blank');
    }
  };

  const viewDocumentMetadata = (metadata: ExtractedMetadata) => {
    if (metadata.metadata_details) {
      try {
        const details = JSON.parse(metadata.metadata_details);
        setSelectedDocMetadata(Array.isArray(details) ? details : []);
        setSelectedMetadataName(metadata.metadata_name);
        setShowDocMetadataDialog(true);
      } catch (error) {
        console.error('Error parsing metadata details:', error);
        console.error('Raw metadata_details:', metadata.metadata_details);
        toast.error('Failed to parse document metadata');
      }
    } else {
      toast.warning('No document metadata available for this field');
    }
  };

  const exportMetadataJSON = (metadata: MetadataViewData) => {
    const dataStr = JSON.stringify(metadata, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `metadata_${metadata.file_name.replace(/\.[^/.]+$/, "")}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const exportMetadataExcel = (metadata: MetadataViewData, sourceFile?: SourceFile) => {
    // Prepare data for Excel export with only specified columns
    const excelData = metadata.metadata.map((item) => ({
      'File URL': metadata.file_url || '',
      'Drug Name': metadata.drug_name || '',
      'US MA Date': sourceFile?.us_ma_date || '',
      'Metadata Name': item.metadata_name,
      'Extracted Value': item.value || 'Not found',
      'Confidence Score': item.confidence_score ? `${(item.confidence_score * 100).toFixed(1)}%` : 'N/A',
      'Extraction Date': formatDate(item.created_at)
    }));

    // Create workbook and worksheet
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.json_to_sheet(excelData);

    // Set column widths
    const colWidths = [
      { wch: 40 }, // File URL
      { wch: 20 }, // Drug Name
      { wch: 15 }, // US MA Date
      { wch: 25 }, // Metadata Name
      { wch: 50 }, // Extracted Value
      { wch: 18 }, // Confidence Score
      { wch: 20 }  // Extraction Date
    ];
    ws['!cols'] = colWidths;

    // Add worksheet to workbook
    XLSX.utils.book_append_sheet(wb, ws, 'Metadata Export');

    // Generate filename and save
    const fileName = `metadata_${metadata.drug_name || metadata.file_name.replace(/\.[^/.]+$/, "")}_${new Date().toISOString().split('T')[0]}.xlsx`;
    XLSX.writeFile(wb, fileName);
    
    toast.success('Excel file downloaded successfully', {
      duration: 2000,
      position: 'top-right',
    });
  };

  const exportAllMetadataExcel = async () => {
    try {
      setDownloadingAll(true);
      
      // Use the new join query API endpoint
      const response = await apiService.getMetadataExportData();
      
      if (!response.success || !response.flat_data || response.flat_data.length === 0) {
        toast.warning('No metadata found to export');
        return;
      }
      
      // Create workbook and worksheet using the flat data from join query
      const wb = XLSX.utils.book_new();
      const ws = XLSX.utils.json_to_sheet(response.flat_data);
      
      // Set column widths
      const colWidths = [
        { wch: 40 }, // File URL
        { wch: 20 }, // Drug Name
        { wch: 15 }, // US MA Date
        { wch: 25 }, // Metadata Name
        { wch: 50 }, // Extracted Value
        { wch: 18 }, // Confidence Score
        { wch: 20 }  // Extraction Date
      ];
      ws['!cols'] = colWidths;
      
      // Add worksheet to workbook
      XLSX.utils.book_append_sheet(wb, ws, 'All Metadata Export');
      
      // Generate filename and save
      const fileName = `all_metadata_export_${new Date().toISOString().split('T')[0]}.xlsx`;
      XLSX.writeFile(wb, fileName);
      
      toast.success(`Exported ${response.total_records} metadata records for ${response.total_drugs} drugs`, {
        duration: 3000,
        position: 'top-right',
      });
      
    } catch (error) {
      console.error('Error exporting all metadata:', error);
      toast.error('Failed to export metadata');
    } finally {
      setDownloadingAll(false);
    }
  };

  const exportAllMetadataJSON = async () => {
    try {
      setDownloadingAll(true);
      
      // Use the new join query API endpoint
      const response = await apiService.getMetadataExportData();
      
      if (!response.success || !response.grouped_data || Object.keys(response.grouped_data).length === 0) {
        toast.warning('No metadata found to export');
        return;
      }
      
      // Convert to JSON string with pretty formatting
      const jsonStr = JSON.stringify(response.grouped_data, null, 2);
      
      // Create blob and download
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `metadata_grouped_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      toast.success(`Exported ${response.total_records} metadata records for ${response.total_drugs} drugs`, {
        duration: 3000,
        position: 'top-right',
      });
      
    } catch (error) {
      console.error('Error exporting metadata as JSON:', error);
      toast.error('Failed to export metadata');
    } finally {
      setDownloadingAll(false);
      setShowDownloadMenu(false);
    }
  };

  if (loading) {
    return (
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">View Metadata Details</h1>
          <p className="text-gray-600 mt-1">
            Extract and browse metadata from FDA documents
          </p>
        </div>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="page-title">View Metadata Details</h1>
              <p className="text-blue-700 mt-1">
                Extract and browse metadata from pharmaceutical documents using configured extraction rules
              </p>
            </div>
          </div>
          
          {/* Search and Filter Bar */}
          <div className="flex items-center gap-4 mb-6">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search files by name, URL, or drug name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="all">All Status</option>
              <option value="PENDING">Pending</option>
              <option value="PROCESSING">Processing</option>
              <option value="DOCUMENT_STORED">Document Stored</option>
              <option value="READY">Ready</option>
              <option value="FAILED">Failed</option>
            </select>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Extract Sequentially button */}
            {stats.readyForExtraction > 0 && (
              <Button
                onClick={handleSequentialExtraction}
                disabled={sequentialExtracting || refreshing}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white btn-professional"
                title="Extract metadata for all eligible files sequentially"
              >
                {sequentialExtracting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Starting...
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    Extract Sequentially ({stats.readyForExtraction})
                  </>
                )}
              </Button>
            )}
            
            {/* Stop Auto-refresh button */}
            {autoRefresh && (
              <Button
                onClick={() => setAutoRefresh(false)}
                variant="outline"
                className="flex items-center gap-2 text-orange-600 border-orange-600 hover:bg-orange-50 btn-professional-subtle"
              >
                <X className="h-4 w-4" />
                Stop Auto-refresh
              </Button>
            )}
            
            <DropdownMenu open={showDownloadMenu} onOpenChange={setShowDownloadMenu}>
              <DropdownMenuTrigger asChild>
                <Button
                  disabled={downloadingAll || refreshing || stats.metadataExtracted === 0}
                  variant="outline"
                  className="flex items-center gap-2 border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 btn-professional-subtle"
                  title="Download all metadata from all files"
                >
                  {downloadingAll ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Downloading...
                    </>
                  ) : (
                    <>
                      <Download className="h-4 w-4" />
                      Download All
                    </>
                  )}
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem
                  onClick={exportAllMetadataExcel}
                  className="flex items-center gap-2"
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  Download as Excel
                </DropdownMenuItem>
                <DropdownMenuItem
                  onClick={exportAllMetadataJSON}
                  className="flex items-center gap-2"
                >
                  <FileText className="h-4 w-4" />
                  Download as JSON (Grouped)
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              onClick={() => fetchSourceFiles(currentPage)}
              disabled={refreshing}
              variant="outline"
              className="flex items-center gap-2 border-blue-200 text-blue-700 btn-refresh"
            >
              <RefreshCw className={`h-4 w-4 ${refreshing || autoRefresh ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>

        {/* Summary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Total Files</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Ready for Extraction</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">
                {stats.readyForExtraction}
              </div>
              <p className="text-xs text-gray-500 mt-1">
                (Indexed files only)
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Metadata Extracted</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">
                {stats.metadataExtracted}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-gray-600">Total Metadata Fields</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-purple-600">
                {stats.totalMetadataFields}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Source Files Table */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Source Files & Metadata Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sourceFiles.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No Source Files Found</h3>
                <p className="text-gray-600">Add source files in the Source Details page to begin metadata extraction.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        File Information
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Drug Name
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Status
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Metadata
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Last Updated
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Actions
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {sourceFiles.map((file) => (
                      <tr key={file.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center">
                            <FileText className="h-5 w-5 text-gray-400 mr-3" />
                            <div>
                              <div className="text-sm font-medium text-gray-900 max-w-xs truncate">
                                {file.file_name}
                              </div>
                              <div className="text-sm text-gray-500">
                                ID: {file.id}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="text-sm text-gray-900">
                            {file.drug_name || 'Not specified'}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex flex-col gap-1">
                            {getStatusBadge(file.status)}
                            {file.status === 'DOCUMENT_STORED' && (
                              <span className="text-xs text-orange-600">
                                Needs indexing
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <div className="flex items-center gap-2">
                            {file.metadata_extracted ? (
                              <Badge className="bg-green-100 text-green-800 flex items-center gap-1">
                                <CheckCircle className="h-3 w-3" />
                                Extracted ({file.metadata_count})
                              </Badge>
                            ) : (
                              <Badge className="bg-gray-100 text-gray-800 flex items-center gap-1">
                                <XCircle className="h-3 w-3" />
                                Not Extracted
                              </Badge>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {formatDate(file.updated_at)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              variant={file.metadata_extracted ? "outline" : "default"}
                              onClick={() => file.metadata_extracted ? handleReExtractMetadata(file.id) : handleExtractMetadata(file.id)}
                              disabled={!canExtractMetadata(file) || extractingMetadata === file.id || reExtractLoading}
                              className={`flex items-center gap-1 ${file.metadata_extracted ? 'btn-refresh' : 'bg-blue-600 hover:bg-blue-700 text-white btn-professional'}`}
                            >
                              {extractingMetadata === file.id ? (
                                <>
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                  {file.metadata_extracted ? 'Re-extracting...' : 'Extracting...'}
                                </>
                              ) : (
                                <>
                                  {file.metadata_extracted ? (
                                    <>
                                      <RefreshCw className="h-3 w-3" />
                                      Re-extract
                                    </>
                                  ) : (
                                    <>
                                      <Play className="h-3 w-3" />
                                      Extract Metadata
                                    </>
                                  )}
                                </>
                              )}
                            </Button>
                            
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleViewMetadata(file.id)}
                              disabled={!file.metadata_extracted}
                              className="flex items-center gap-1 border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 btn-professional-subtle"
                            >
                              <Eye className="h-3 w-3" />
                              View Metadata
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <div className="text-sm text-gray-700">
              Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalCount)} of {totalCount} files
            </div>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchSourceFiles(currentPage - 1)}
                disabled={currentPage === 1 || loading || refreshing}
              >
                Previous
              </Button>
              
              <div className="flex gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum;
                  if (totalPages <= 5) {
                    pageNum = i + 1;
                  } else if (currentPage <= 3) {
                    pageNum = i + 1;
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = currentPage - 2 + i;
                  }
                  
                  return (
                    <Button
                      key={pageNum}
                      variant={currentPage === pageNum ? "default" : "outline"}
                      size="sm"
                      onClick={() => fetchSourceFiles(pageNum)}
                      disabled={loading || refreshing}
                      className="min-w-[40px]"
                    >
                      {pageNum}
                    </Button>
                  );
                })}
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => fetchSourceFiles(currentPage + 1)}
                disabled={currentPage === totalPages || loading || refreshing}
              >
                Next
              </Button>
              
              <div className="ml-4 flex items-center gap-2">
                <span className="text-sm text-gray-700">Show:</span>
                <select
                  value={pageSize}
                  onChange={(e) => setPageSize(Number(e.target.value))}
                  className="px-3 py-1 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                  <option value={100}>100</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Enhanced View Metadata Modal */}
        <Dialog open={isViewModalOpen} onOpenChange={setIsViewModalOpen}>
          <DialogContent className="max-w-[95vw] max-h-[95vh] w-[95vw]">
            <DialogHeader>
              <div className="flex items-center justify-between">
                <DialogTitle className="flex items-center gap-2">
                  <Eye className="h-5 w-5" />
                  Extracted Metadata: {viewingMetadata?.file_name}
                </DialogTitle>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setIsViewModalOpen(false)}
                  className="mr-6"
                >
                  Close
                </Button>
              </div>
            </DialogHeader>
            
            {viewingMetadata && (
              <div className="space-y-4 max-h-[85vh] overflow-y-auto pr-2" style={{
                scrollbarWidth: 'thin',
                scrollbarColor: '#cbd5e1 #f1f5f9'
              }}>
                {/* File Information Header */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base flex items-center gap-2">
                        <Info className="h-4 w-4" />
                        File Information
                      </CardTitle>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => exportMetadataExcel(viewingMetadata, viewingSourceFile || undefined)}
                        className="flex items-center gap-1"
                        title="Download Excel"
                      >
                        <Download className="h-3 w-3" />
                        Download
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent className="pt-0">
                    <div className="grid grid-cols-2 gap-6 text-sm">
                      <div>
                        <span className="font-medium text-gray-600">File Name:</span> 
                        <span className="ml-2">{viewingMetadata.file_name}</span>
                      </div>
                      <div>
                        <span className="font-medium text-gray-600">Drug Name:</span> 
                        <span className="ml-2">{viewingMetadata.drug_name || 'Not specified'}</span>
                      </div>
                      <div>
                        <span className="font-medium text-gray-600">Total Fields:</span> 
                        <span className="ml-2 font-semibold text-purple-600">{viewingMetadata.metadata_count}</span>
                      </div>
                      <div>
                        <span className="font-medium text-gray-600">Source File ID:</span> 
                        <span className="ml-2">{viewingMetadata.source_file_id}</span>
                      </div>
                      <div className="col-span-2">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-600">File URL:</span>
                          {viewingMetadata.file_url ? (
                            <div className="flex items-center gap-2">
                              <span className="text-blue-600 text-xs bg-blue-50 px-2 py-1 rounded max-w-md truncate">
                                {viewingMetadata.file_url}
                              </span>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-6 px-2 text-xs"
                                onClick={() => openFileUrl(viewingMetadata.file_url)}
                              >
                                <ExternalLink className="h-3 w-3 mr-1" />
                                Open
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-6 px-2 text-xs"
                                onClick={() => copyToClipboard(viewingMetadata.file_url)}
                              >
                                <Copy className="h-3 w-3 mr-1" />
                                Copy
                              </Button>
                            </div>
                          ) : (
                            <span className="text-gray-400 italic">No URL available</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Professional Metadata Table */}
                <Card>
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">Extracted Metadata</CardTitle>
                      {viewingMetadata.metadata.some(m => m.value) && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={copyAllMetadata}
                          className="flex items-center gap-1 text-xs"
                        >
                          <Copy className="h-3 w-3" />
                          Copy All
                        </Button>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="p-0">
                    {viewingMetadata.metadata.length === 0 ? (
                      <div className="text-center py-12">
                        <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                        <h3 className="text-lg font-medium text-gray-900 mb-2">No Metadata Available</h3>
                        <p className="text-gray-600">No metadata has been extracted for this file yet.</p>
                      </div>
                    ) : (
                      <div className="h-[50vh] border rounded-lg overflow-y-auto overflow-x-auto" style={{
                        scrollbarWidth: 'thin',
                        scrollbarColor: '#cbd5e1 #f1f5f9'
                      }}>
                        <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/4">
                                  Metadata Name
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-1/2">
                                  Extracted Value
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                                  Confidence
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                                  Actions
                                </th>
                                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Date
                                </th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {viewingMetadata.metadata.map((metadata, index) => (
                                <tr key={metadata.id || `${metadata.metadata_name}-${index}`} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                  <td className="px-6 py-4 align-top">
                                    <div className="font-medium text-gray-900 mb-1">
                                      {metadata.metadata_name}
                                    </div>
                                    {metadata.extraction_prompt && (
                                      <details className="text-xs text-gray-500 mt-2">
                                        <summary className="cursor-pointer hover:text-gray-700 font-medium">
                                          View Prompt
                                        </summary>
                                        <div className="mt-1 p-2 bg-gray-100 rounded text-xs leading-relaxed">
                                          {metadata.extraction_prompt}
                                        </div>
                                      </details>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 align-top">
                                    <div className="text-gray-900 break-words">
                                      {metadata.value ? (
                                        <div className="space-y-2">
                                          <div className="bg-blue-50 text-blue-900 px-3 py-2 rounded-md text-sm border border-blue-200">
                                            {formatMetadataValue(metadata.value) ? (
                                              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">
                                                {formatMetadataValue(metadata.value)}
                                              </pre>
                                            ) : (
                                              metadata.value
                                            )}
                                          </div>
                                          {formatMetadataValue(metadata.value) && 
                                           formatMetadataValue(metadata.value) !== metadata.value && (
                                            <div className="text-xs text-gray-500 bg-yellow-50 px-2 py-1 rounded border border-yellow-200">
                                              <span className="font-medium">Note:</span> HTML content was formatted for better readability
                                            </div>
                                          )}
                                        </div>
                                      ) : (
                                        <span className="text-gray-400 italic">Not found</span>
                                      )}
                                    </div>
                                  </td>
                                  <td className="px-6 py-4 align-top text-center">
                                    {metadata.confidence_score ? (
                                      <Badge 
                                        variant="outline" 
                                        className={`text-xs ${
                                          metadata.confidence_score >= 0.8 
                                            ? 'border-green-200 text-green-700 bg-green-50'
                                            : metadata.confidence_score >= 0.6
                                            ? 'border-yellow-200 text-yellow-700 bg-yellow-50'
                                            : 'border-red-200 text-red-700 bg-red-50'
                                        }`}
                                      >
                                        {(metadata.confidence_score * 100).toFixed(0)}%
                                      </Badge>
                                    ) : (
                                      <span className="text-gray-400 text-xs">N/A</span>
                                    )}
                                  </td>
                                  <td className="px-6 py-4 align-top text-center">
                                    <div className="flex items-center gap-2 justify-center">
                                      {metadata.value ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 px-2 text-xs flex items-center gap-1 hover:bg-blue-50"
                                          onClick={() => copyToClipboard(formatMetadataValue(metadata.value) || metadata.value)}
                                          title="Copy to clipboard"
                                        >
                                          <Copy className="h-3 w-3" />
                                          Copy
                                        </Button>
                                      ) : (
                                        <span className="text-gray-400 text-xs">-</span>
                                      )}
                                      {metadata.metadata_details && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 px-2 text-xs flex items-center gap-1 hover:bg-purple-50"
                                          onClick={() => viewDocumentMetadata(metadata)}
                                          title="View source chunks used for extraction"
                                        >
                                          <FileSearch className="h-3 w-3" />
                                          Sources
                                        </Button>
                                      )}
                                    </div>
                                  </td>
                                  <td className="px-6 py-4 align-top text-xs text-gray-500">
                                    {formatDate(metadata.created_at)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Delete Confirmation Dialog */}
        <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete Extracted Metadata?</AlertDialogTitle>
            </AlertDialogHeader>
            <div className="text-sm text-gray-600 mb-4">
              Are you sure you want to delete all extracted metadata for <span className="font-semibold">{viewingMetadata?.file_name}</span>?<br />
              This action cannot be undone.
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={deleteLoading}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleDeleteMetadata} disabled={deleteLoading} className="bg-red-600 hover:bg-red-700">
                {deleteLoading ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Re-extract Confirmation Dialog */}
        <AlertDialog open={showReExtractDialog} onOpenChange={setShowReExtractDialog}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Re-extract Metadata?</AlertDialogTitle>
            </AlertDialogHeader>
            <div className="text-sm text-gray-600 mb-4">
              <p className="mb-2">This will delete the existing extracted metadata for <span className="font-semibold">{viewingMetadata?.file_name}</span> and extract it again using the current metadata configuration.</p>
              <p className="text-yellow-600 font-medium">Note: This process may take a few minutes depending on the document size.</p>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={reExtractLoading}>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleReExtractMetadata} disabled={reExtractLoading} className="btn-refresh">
                {reExtractLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Re-extracting...
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Re-extract
                  </>
                )}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Document Metadata Dialog */}
        <Dialog open={showDocMetadataDialog} onOpenChange={setShowDocMetadataDialog}>
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader>
              <div className="flex items-center justify-between">
                <DialogTitle className="flex items-center gap-2">
                  <FileSearch className="h-5 w-5" />
                  Metadata Source Details - {selectedMetadataName}
                </DialogTitle>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowDocMetadataDialog(false)}
                  className="mr-6"
                >
                  Close
                </Button>
              </div>
            </DialogHeader>
            
            <div className="overflow-y-auto max-h-[60vh]">
              {selectedDocMetadata.length === 0 ? (
                <div className="text-center py-8">
                  <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No source chunks available</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {selectedDocMetadata.map((doc, index) => (
                    <Card key={index} className="p-4">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <h3 className="font-semibold text-sm">Chunk {index + 1}</h3>
                          <Badge variant="outline" className="text-xs">
                            Page {(() => {
                              // Log the entire document object to see its structure
                              console.log(`Chunk ${index + 1} full object:`, doc);
                              
                              // Try to find page number in various ways
                              let pageNum = null;
                              
                              // Direct property access
                              if ('page_number' in doc) pageNum = doc.page_number;
                              else if ('page_num' in doc) pageNum = doc.page_num;
                              else if ('pageNumber' in doc) pageNum = doc.pageNumber;
                              else if ('page' in doc) pageNum = doc.page;
                              
                              // Try to find any key containing 'page'
                              if (!pageNum) {
                                const pageKey = Object.keys(doc).find(key => 
                                  key.toLowerCase().includes('page') && 
                                  typeof doc[key] === 'number'
                                );
                                if (pageKey) pageNum = doc[pageKey];
                              }
                              
                              return pageNum !== null && pageNum !== undefined ? pageNum : 'N/A';
                            })()}
                          </Badge>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>
                            <span className="font-medium text-gray-600">File:</span>
                            <span className="ml-2">{doc.file_name || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="font-medium text-gray-600">Drug:</span>
                            <span className="ml-2">{doc.drug_name || 'N/A'}</span>
                          </div>
                        </div>
                        {(doc.original_content || doc.content) && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium text-gray-600 text-sm">Content Preview:</span>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="h-6 text-xs"
                                onClick={() => copyToClipboard(doc.original_content || doc.content || '')}
                              >
                                <Copy className="h-3 w-3 mr-1" />
                                Copy
                              </Button>
                            </div>
                            <div className="bg-gray-50 p-3 rounded-md border border-gray-200">
                              <pre className="text-xs text-gray-700 whitespace-pre-wrap">
                                {(() => {
                                  const content = doc.original_content || doc.content || '';
                                  return content.length > 500 
                                    ? content.substring(0, 500) + '...' 
                                    : content;
                                })()}
                              </pre>
                            </div>
                          </div>
                        )}
                      </div>
                    </Card>
                  ))}
                  <div className="text-xs text-gray-500 mt-4">
                    Total source chunks: {selectedDocMetadata.length}
                  </div>
                </div>
              )}
            </div>
          </DialogContent>
        </Dialog>

        {/* Debug Information Card */}
        {lastDebugSessionId && (
          <Card className="mt-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Bug className="h-4 w-4" />
                Debug Information
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-sm space-y-2">
                <p className="text-gray-600">
                  Last extraction session ID: <code className="bg-gray-100 px-2 py-1 rounded">{lastDebugSessionId}</code>
                </p>
                <p className="text-gray-500 text-xs mt-2">
                  Debug logs are saved in: <code className="bg-gray-100 px-1 rounded">backend/metadata_extraction_debug/{lastDebugSessionId}</code>
                </p>
                <p className="text-gray-500 text-xs mt-1">
                  Folder format: <code className="bg-gray-100 px-1 rounded">[drug_name]_[timestamp]_[id]</code>
                </p>
                <div className="mt-3">
                  <p className="font-medium mb-1">Debug files include:</p>
                  <ul className="list-disc list-inside text-xs text-gray-600 space-y-1">
                    <li>Configuration details for each metadata field</li>
                    <li>Extraction prompts sent to the LLM</li>
                    <li>Vector database query parameters</li>
                    <li>Retrieved documents from ChromaDB</li>
                    <li>LLM responses (first pass and second pass)</li>
                    <li>Final extraction results and confidence scores</li>
                    <li>Any errors encountered during extraction</li>
                  </ul>
                </div>
                <div className="mt-3 pt-3 border-t">
                  <p className="text-xs text-gray-500">
                    To investigate why a metadata field shows "Not Found", check the debug folder for that specific metadata name.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
} 