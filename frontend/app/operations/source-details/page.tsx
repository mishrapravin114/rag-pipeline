"use client";

import { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { apiService } from '@/services/api';
import { 
  Plus, 
  Search, 
  Database, 
  FileText, 
  Play, 
  Eye, 
  Upload, 
  Download, 
  Filter,
  X,
  Save,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Clock,
  Trash2,
  RefreshCw,
  Link,
  Calendar,
  FileCheck,
  FileX,
  Loader2,
  FileUp,
  BarChart3,
  RotateCcw,
  HardDrive,
  Info,
  Copy,
  FolderPlus
} from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

interface SourceFile {
  id: number;
  file_name: string;
  file_url: string;
  drug_name?: string;
  status: string;
  file_size?: string;
  file_type?: string;
  processing_progress?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
  created_by?: number;
  creator_username?: string;
  extraction_count?: number;
  comments?: string;
  us_ma_date?: string;
}

interface UploadForm {
  file_name: string;
  file_url: string;
  drug_name: string;
  description: string;
  us_ma_date: string;
  collection_id?: number;
}

interface Collection {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

interface BulkUploadItem {
  file_name: string;
  file_url: string;
  drug_name?: string;
  comments?: string;
  us_ma_date?: string;
}

interface DocumentData {
  id: number;
  doc_content: string;
  metadata: any;
  created_at: string;
  updated_at: string;
}

interface Stats {
  total: number;
  completed: number;
  processing: number;
  failed: number;
  pending: number;
  ready: number;
}

export default function SourceDetailsPage() {
  const [sourceFiles, setSourceFiles] = useState<SourceFile[]>([]);
  const [filteredFiles, setFilteredFiles] = useState<SourceFile[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<number[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, completed: 0, processing: 0, failed: 0, pending: 0, ready: 0 });
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<{ [key: string]: boolean }>({});
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(0);
  
  // View Document Modal State
  const [isViewModalOpen, setIsViewModalOpen] = useState(false);
  const [viewingDocuments, setViewingDocuments] = useState<{
    source_file: any;
    documents: DocumentData[];
    total_documents: number;
  } | null>(null);
  const [viewLoading, setViewLoading] = useState(false);
  
  // Additional modal states
  const [isReprocessModalOpen, setIsReprocessModalOpen] = useState(false);
  const [reprocessFileData, setReprocessFileData] = useState<SourceFile | null>(null);
  
  // Delete file confirmation modal state
  const [isDeleteFileModalOpen, setIsDeleteFileModalOpen] = useState(false);
  const [deleteFileData, setDeleteFileData] = useState<SourceFile | null>(null);
  
  // Bulk Upload Modal State
  const [isBulkUploadModalOpen, setIsBulkUploadModalOpen] = useState(false);
  const [bulkUploadData, setBulkUploadData] = useState<string>('');
  const [bulkUploadLoading, setBulkUploadLoading] = useState(false);
  const [bulkUploadResult, setBulkUploadResult] = useState<any>(null);
  const [isBulkResultModalOpen, setIsBulkResultModalOpen] = useState(false);
  
  // Excel file upload state
  const [selectedExcelFile, setSelectedExcelFile] = useState<File | null>(null);
  const [excelData, setExcelData] = useState<BulkUploadItem[]>([]);
  const [excelPreviewData, setExcelPreviewData] = useState<any[]>([]);
  const [isFileProcessing, setIsFileProcessing] = useState(false);
  
  // Auto-refresh state
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());
  
  const [uploadForm, setUploadForm] = useState<UploadForm>({
    file_name: '',
    file_url: '',
    drug_name: '',
    description: '',
    us_ma_date: '',
    collection_id: undefined
  });
  
  // File upload state
  const [uploadMethod, setUploadMethod] = useState<'url' | 'file'>('url');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loadingCollections, setLoadingCollections] = useState(false);

  const { user } = useAuth();

  // Load collections
  const loadCollections = async () => {
    try {
      setLoadingCollections(true);
      const response = await apiService.getCollections();
      setCollections(response.collections || []);
    } catch (error) {
      console.error('Error loading collections:', error);
    } finally {
      setLoadingCollections(false);
    }
  };

  // Load source files from API
  const loadSourceFiles = async (page: number = 1) => {
    try {
      setLoading(true);
      setError(null);
      
      const offset = (page - 1) * pageSize;
      
      const result = await apiService.getSourceFiles({
        limit: pageSize,
        offset: offset,
        status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchTerm || undefined
      });
      
      setSourceFiles(result.source_files);
      setTotalCount(result.total_count);
      setTotalPages(Math.ceil(result.total_count / pageSize));
      setCurrentPage(page);
      setLastRefresh(new Date());
      
    } catch (error) {
      console.error('Error loading source files:', error);
      
      if (error instanceof Error && error.message.includes('Authentication')) {
        setError('Your session has expired. Please refresh the page or log in again.');
      } else {
        setError('Failed to load source files. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadSourceFiles(currentPage);
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, currentPage]);

  // Load initial data
  useEffect(() => {
    loadSourceFiles(1);
    loadCollections();
  }, []);
  
  // Reload when filters change
  useEffect(() => {
    const timer = setTimeout(() => {
      loadSourceFiles(1); // Reset to first page when filters change
    }, 300);
    
    return () => clearTimeout(timer);
  }, [statusFilter, searchTerm, pageSize]);

  // Filter and search logic - Now handled server-side
  useEffect(() => {
    // Since filtering is now done server-side, just set filtered files to source files
    setFilteredFiles(sourceFiles);
  }, [sourceFiles]);

  // Calculate stats
  useEffect(() => {
    const newStats = {
      total: totalCount, // Use totalCount from API
      completed: sourceFiles.filter(f => f.status === 'READY').length,
      processing: sourceFiles.filter(f => ['PROCESSING', 'INDEXING'].includes(f.status)).length,
      failed: sourceFiles.filter(f => f.status === 'FAILED').length,
      pending: sourceFiles.filter(f => f.status === 'PENDING').length,
      ready: sourceFiles.filter(f => f.status === 'DOCUMENT_STORED').length,
    };
    setStats(newStats);
  }, [sourceFiles, totalCount]);

  // Add new source file - FIXED: This function now works properly
  const handleAddSource = async () => {
    if (uploadMethod === 'url' && (!uploadForm.file_name || !uploadForm.file_url)) {
      setError('File name and URL are required');
      return;
    }
    
    if (uploadMethod === 'file' && !selectedFile) {
      setError('Please select a file to upload');
      return;
    }

    try {
      setActionLoading({ ...actionLoading, add: true });
      setIsUploading(true);
      
      let newFile;
      
      if (uploadMethod === 'file' && selectedFile) {
        // Handle file upload
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('drug_name', uploadForm.drug_name || '');
        formData.append('comments', uploadForm.description || '');
        formData.append('us_ma_date', uploadForm.us_ma_date || '');
        if (uploadForm.collection_id) {
          formData.append('collection_id', uploadForm.collection_id.toString());
        }
        const response = await apiService.uploadSourceFile(formData);
        newFile = response;
      } else {
        // Handle URL upload
        newFile = await apiService.createSourceFile({
          file_name: uploadForm.file_name,
          file_url: uploadForm.file_url,
          drug_name: uploadForm.drug_name,
          comments: uploadForm.description,
          us_ma_date: uploadForm.us_ma_date,
          status: 'PENDING',
          collection_id: uploadForm.collection_id
        });
      }

      // Add to local state
      setSourceFiles([newFile, ...sourceFiles]);
      setIsUploadModalOpen(false);
      setUploadForm({ file_name: '', file_url: '', drug_name: '', description: '', us_ma_date: '', collection_id: undefined });
      setSelectedFile(null);
      setUploadMethod('url');
      setError(null);
      
      // Show success message
      const { toast } = await import('sonner');
      toast.success('Source file added successfully!', {
        description: `${newFile.file_name} has been added and is ready for processing.`,
        duration: 5000,
      });
      
    } catch (error) {
      console.error('Error adding source file:', error);
      setError('Failed to add source file. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, add: false });
      setIsUploading(false);
    }
  };
  
  // Handle file selection
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type (only PDF)
      if (file.type !== 'application/pdf') {
        setError('Only PDF files are allowed');
        return;
      }
      
      setSelectedFile(file);
      // Auto-fill file name if not already set
      if (!uploadForm.file_name) {
        setUploadForm({ ...uploadForm, file_name: file.name });
      }
    }
  };

  // FIXED: Delete function now shows custom modal instead of browser confirm
  const handleDeleteFile = (id: number) => {
    const sourceFile = sourceFiles.find(f => f.id === id);
    if (!sourceFile) return;

    setDeleteFileData(sourceFile);
    setIsDeleteFileModalOpen(true);
  };

  // Confirm delete file with custom modal
  const confirmDeleteFile = async () => {
    if (!deleteFileData) return;
    
    try {
      setActionLoading({ ...actionLoading, [`delete_${deleteFileData.id}`]: true });
      
      
      await apiService.deleteSourceFile(deleteFileData.id);
      
      // Remove from local state
      setSourceFiles(files => files.filter(file => file.id !== deleteFileData.id));
      setSelectedFiles(prev => prev.filter(fileId => fileId !== deleteFileData.id));
      
      // Close the modal
      setIsDeleteFileModalOpen(false);
      setDeleteFileData(null);
      setError(null);
      
      // Show success message
      const { toast } = await import('sonner');
      toast.success('File deleted successfully', {
        description: `${deleteFileData.file_name} has been removed.`,
        duration: 4000,
      });
      
    } catch (error) {
      console.error('Error deleting file:', error);
      setError('Failed to delete file. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`delete_${deleteFileData.id}`]: false });
    }
  };

  // Toggle file selection for bulk operations
  const toggleFileSelection = (id: number) => {
    setSelectedFiles(prev => 
      prev.includes(id) 
        ? prev.filter(fileId => fileId !== id)
        : [...prev, id]
    );
  };

  // Handle view documents
  const handleViewDocuments = async (fileId: number) => {
    try {
      setViewLoading(true);
      
      const result = await apiService.getSourceFileDocuments(fileId);
      setViewingDocuments(result);
      setIsViewModalOpen(true);
      
    } catch (error) {
      console.error('Error loading documents:', error);
      setError('Failed to load document details. Please try again.');
    } finally {
      setViewLoading(false);
    }
  };

  // Handle process file
  const handleProcessFile = async (id: number) => {
    try {
      setActionLoading({ ...actionLoading, [`process_${id}`]: true });
      
      await apiService.processSourceFile(id);
      
      // Update local state
      setSourceFiles(files => 
        files.map(file => 
          file.id === id 
            ? { ...file, status: 'PROCESSING', processing_progress: 0 }
            : file
        )
      );
      
      // Show success message
      const { toast } = await import('sonner');
      const fileName = sourceFiles.find(f => f.id === id)?.file_name || 'File';
      toast.success('Processing started', {
        description: `${fileName} is now being processed.`,
        duration: 4000,
      });
      
    } catch (error) {
      console.error('Error processing file:', error);
        setError('Failed to start processing. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`process_${id}`]: false });
    }
  };

  // Handle index file to vector database
  const handleIndexFile = async (id: number) => {
    try {
      setActionLoading({ ...actionLoading, [`index_${id}`]: true });
      
      await apiService.indexSourceFile(id);
      
      // Update local state
      setSourceFiles(files => 
        files.map(file => 
          file.id === id 
            ? { ...file, status: 'INDEXING', processing_progress: 0 }
            : file
        )
      );
      
    } catch (error) {
      console.error('Error indexing file:', error);
        setError('Failed to start indexing. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`index_${id}`]: false });
    }
  };

  // Handle reprocess file
  const handleReprocessFile = async (id: number) => {
    try {
      setActionLoading({ ...actionLoading, [`reprocess_${id}`]: true });
      
      await apiService.reprocessSourceFile(id);
      
      // Update local state
      setSourceFiles(files => 
        files.map(file => 
          file.id === id 
            ? { ...file, status: 'PROCESSING', processing_progress: 0 }
            : file
        )
      );
      
      setIsReprocessModalOpen(false);
      setReprocessFileData(null);
      
      // Show success message
      const { toast } = await import('sonner');
      const fileName = sourceFiles.find(f => f.id === id)?.file_name || 'File';
      toast.success('Reprocessing started', {
        description: `${fileName} is being reprocessed.`,
        duration: 4000,
      });
      
    } catch (error) {
      console.error('Error reprocessing file:', error);
      setError('Failed to start reprocessing. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`reprocess_${id}`]: false });
    }
  };

  // Handle delete vector database entries
  const handleDeleteVectorDb = async (id: number) => {
    try {
      setActionLoading({ ...actionLoading, [`delete_vectordb_${id}`]: true });
      
      await apiService.deleteSourceFileVectorDB(id);
      
      // Update local state - could change status to indicate vector DB is cleared
      setSourceFiles(files => 
        files.map(file => 
          file.id === id 
            ? { ...file, status: 'DOCUMENT_STORED' }
            : file
        )
      );
      
    } catch (error) {
      console.error('Error deleting vector DB entries:', error);
      setError('Failed to delete vector database entries. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`delete_vectordb_${id}`]: false });
    }
  };

  // Handle bulk process selected files
  const handleBulkProcess = async () => {
    try {
      setActionLoading({ ...actionLoading, bulk_process: true });
      
      
      const result = await apiService.bulkProcessSourceFiles(selectedFiles);
      
      // Update local state for processed files
      setSourceFiles(files => 
        files.map(file => 
          selectedFiles.includes(file.id) && ['PENDING', 'FAILED'].includes(file.status)
            ? { ...file, status: 'PROCESSING', processing_progress: 0 }
            : file
        )
      );
      
      setSelectedFiles([]);
      
    } catch (error) {
      console.error('Error bulk processing files:', error);
      setError('Failed to start bulk processing. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, bulk_process: false });
    }
  };

  // Handle sequential process selected files
  const handleSequentialProcess = async () => {
    try {
      setActionLoading({ ...actionLoading, sequential_process: true });
      
      const { toast } = await import('sonner');
      
      const result = await apiService.processSourceFilesSequential(selectedFiles);
      
      if (result.success) {
        // Show success toast with details
        toast.success(result.message, {
          description: `Processing ${result.total_queued} files sequentially in the background`,
          duration: 5000,
        });
        
        // Update local state for processed files
        setSourceFiles(files => 
          files.map(file => 
            selectedFiles.includes(file.id) && ['PENDING', 'FAILED'].includes(file.status)
              ? { ...file, status: 'PROCESSING', processing_progress: 0 }
              : file
          )
        );
        
        setSelectedFiles([]);
        
        // Enable auto-refresh to monitor progress
        setAutoRefresh(true);
      }
      
    } catch (error) {
      console.error('Error starting sequential processing:', error);
      setError('Failed to start sequential processing. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, sequential_process: false });
    }
  };

  // Download bulk upload template
  const handleDownloadTemplate = async () => {
    try {
      const blob = await apiService.getBulkUploadTemplate();
      
      // Create downloadable XLSX file
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'source_files_template.xlsx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error('Error downloading template:', error);
      setError(`Failed to download template: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Handle Excel file selection and processing
  const handleExcelFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    const validTypes = [
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
      'application/vnd.ms-excel', // .xls
    ];

    if (!validTypes.includes(file.type)) {
      setError('Please select a valid Excel file (.xlsx or .xls)');
      return;
    }

    setSelectedExcelFile(file);
    setIsFileProcessing(true);
    setError(null);

    try {
      // Import xlsx library dynamically
      const XLSX = await import('xlsx');
      
      const fileReader = new FileReader();
      fileReader.onload = (e) => {
        try {
          const data = new Uint8Array(e.target?.result as ArrayBuffer);
          const workbook = XLSX.read(data, { type: 'array' });
          
          // Get the first worksheet
          const worksheetName = workbook.SheetNames[0];
          const worksheet = workbook.Sheets[worksheetName];
          
          // Convert to JSON
          const jsonData = XLSX.utils.sheet_to_json(worksheet, { header: 1 });
          
          if (jsonData.length < 2) {
            throw new Error('Excel file must contain at least a header row and one data row');
          }

          // Get headers (first row)
          const headers = jsonData[0] as string[];
          
          // Process data rows
          const processedData: BulkUploadItem[] = [];
          const previewData: any[] = [];
          
          for (let i = 1; i < jsonData.length; i++) {
            const row = jsonData[i] as any[];
            
            // Skip empty rows
            if (!row || row.every(cell => !cell || cell.toString().trim() === '')) {
              continue;
            }

            // Create object from row data
            const rowData: any = {};
            headers.forEach((header, index) => {
              if (header && row[index] !== undefined) {
                rowData[header.toLowerCase().replace(/\s+/g, '_')] = row[index];
              }
            });

            // Validate required fields
            const fileName = rowData.file_name || rowData.filename || rowData['file name'];
            const fileUrl = rowData.file_url || rowData.fileurl || rowData['file url'] || rowData.url;

            if (!fileName || !fileUrl) {
              throw new Error(`Row ${i + 1}: Missing required fields (file_name and file_url)`);
            }

            // Add to processed data
            const item: BulkUploadItem = {
              file_name: fileName.toString().trim(),
              file_url: fileUrl.toString().trim(),
              drug_name: (rowData.drug_name || rowData.drugname || rowData['drug name'] || '')?.toString().trim() || undefined,
              comments: (rowData.comments || rowData.description || rowData.notes || '')?.toString().trim() || undefined,
              us_ma_date: (rowData.us_ma_date || rowData['us ma date'] || rowData['us_ma_date'] || '')?.toString().trim() || undefined
            };

            processedData.push(item);
            previewData.push({ row: i + 1, ...item });
          }

          if (processedData.length === 0) {
            throw new Error('No valid data found in Excel file');
          }

          setExcelData(processedData);
          setExcelPreviewData(previewData);
      
    } catch (error) {
          console.error('Error processing Excel file:', error);
          setError(`Error processing Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`);
          setSelectedExcelFile(null);
    } finally {
          setIsFileProcessing(false);
        }
      };

      fileReader.onerror = () => {
        setError('Error reading file');
        setIsFileProcessing(false);
        setSelectedExcelFile(null);
      };

      fileReader.readAsArrayBuffer(file);
      
    } catch (error) {
      console.error('Error loading Excel file:', error);
      setError(`Error loading Excel file: ${error instanceof Error ? error.message : 'Unknown error'}`);
      setIsFileProcessing(false);
      setSelectedExcelFile(null);
    }
  };

  // Handle bulk upload from Excel data
  const handleBulkUpload = async () => {
    try {
      setBulkUploadLoading(true);
      
      // Validate Excel data exists
      if (!excelData || excelData.length === 0) {
        setError('Please select and process an Excel file first.');
        return;
      }
      
      const result = await apiService.bulkUploadSourceFiles(excelData);
      
      setBulkUploadResult(result);
      setIsBulkUploadModalOpen(false);
      setIsBulkResultModalOpen(true);
      
      // Reset form
      setSelectedExcelFile(null);
      setExcelData([]);
      setExcelPreviewData([]);
      
      // Refresh the list if there were successful uploads
      if (result.successful_items > 0) {
        loadSourceFiles(1); // Refresh from page 1 after bulk upload
      }
      
    } catch (error) {
      console.error('Error in bulk upload:', error);
      setError('Failed to process bulk upload. Please try again.');
    } finally {
      setBulkUploadLoading(false);
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ready': return 'default';
      case 'processing': case 'indexing': return 'secondary';
      case 'failed': return 'destructive';
      case 'pending': return 'outline';
      case 'document_stored': return 'secondary';
      default: return 'outline';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'ready': return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'processing': return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
      case 'indexing': return <Loader2 className="h-4 w-4 text-purple-600 animate-spin" />;
      case 'failed': return <AlertCircle className="h-4 w-4 text-red-600" />;
      case 'pending': return <Clock className="h-4 w-4 text-yellow-600" />;
      case 'document_stored': return <FileCheck className="h-4 w-4 text-blue-600" />;
      default: return <FileX className="h-4 w-4 text-gray-400" />;
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
        <span className="text-gray-600">Loading source files...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="page-title">Source Details</h1>
            <p className="text-blue-700 mt-1">
              Manage pharmaceutical document sources and processing pipeline
            </p>
          </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Clock className="h-4 w-4" />
            Last refresh: {lastRefresh.toLocaleTimeString()}
          </div>
          <Button 
            variant="outline" 
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-2 btn-refresh ${autoRefresh ? 'bg-green-50 border-green-200 text-green-700 hover:bg-green-100 hover:border-green-400 hover:text-green-800' : 'border-blue-200 text-blue-700'}`}
          >
            <RefreshCw className={`h-4 w-4 ${autoRefresh ? 'animate-spin' : ''}`} />
            Auto-refresh {autoRefresh ? 'ON' : 'OFF'}
          </Button>
          <Button variant="outline" onClick={() => loadSourceFiles(currentPage)} className="flex items-center gap-2 border-blue-200 text-blue-700 btn-refresh">
            <RefreshCw className="h-4 w-4" />
            Refresh Now
          </Button>
          {selectedFiles.length > 0 && (
            <>
              <Button 
                variant="outline" 
                onClick={handleBulkProcess} 
                disabled={actionLoading.bulk_process}
                className="flex items-center gap-2 border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 btn-professional-subtle"
              >
                {actionLoading.bulk_process ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                Process Selected ({selectedFiles.length})
              </Button>
              <Button 
                variant="outline" 
                onClick={handleSequentialProcess} 
                disabled={actionLoading.sequential_process}
                className="flex items-center gap-2 bg-purple-50 border-purple-200 text-purple-700 hover:bg-purple-100 btn-professional-subtle"
              >
                {actionLoading.sequential_process ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RotateCcw className="h-4 w-4" />
                )}
                Process Sequential ({selectedFiles.length})
              </Button>
            </>
          )}
          <Button 
            variant="outline"
            onClick={() => setIsBulkUploadModalOpen(true)}
            className="flex items-center gap-2 border-blue-200 text-blue-700 hover:bg-blue-50 hover:border-blue-300 btn-professional-subtle"
          >
            <FileUp className="h-4 w-4" />
            Bulk Upload
          </Button>
          <Button 
            onClick={() => setIsUploadModalOpen(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
          >
            <Plus className="h-4 w-4" />
            Add Source File
          </Button>
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-600" />
              <div>
                <p className="text-red-800 font-medium">Error</p>
                <p className="text-red-600 text-sm">{error}</p>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setError(null)}>
                <X className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Total Files</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
              </div>
              <Database className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Completed</p>
                <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
              </div>
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Processing</p>
                <p className="text-2xl font-bold text-blue-600">{stats.processing}</p>
              </div>
              <Loader2 className="h-8 w-8 text-blue-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Failed</p>
                <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
              </div>
              <AlertCircle className="h-8 w-8 text-red-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Pending</p>
                <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
              </div>
              <Clock className="h-8 w-8 text-yellow-600" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">Document Stored</p>
                <p className="text-2xl font-bold text-emerald-600">{stats.ready}</p>
              </div>
              <FileCheck className="h-8 w-8 text-emerald-600" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search files, drug names, URLs, comments, or creators..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-gray-500" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="all">All Status</option>
                  <option value="pending">Pending</option>
                  <option value="processing">Processing</option>
                  <option value="document_stored">Document Stored</option>
                  <option value="indexing">Indexing</option>
                  <option value="ready">Ready</option>
                  <option value="failed">Failed</option>
                </select>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Source Files List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            Source Files ({filteredFiles.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredFiles.length === 0 ? (
            <div className="text-center p-12">
              <Database className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {searchTerm || statusFilter !== 'all' ? 'No files found' : 'No source files yet'}
              </h3>
              <p className="text-gray-600 mb-6">
                {searchTerm || statusFilter !== 'all'
                  ? 'Try adjusting your search terms or filters'
                  : 'Add your first FDA document source to get started'
                }
              </p>
              {!searchTerm && statusFilter === 'all' && (
                <Button onClick={() => setIsUploadModalOpen(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Source File
                </Button>
              )}
            </div>
          ) : (
            <div className="divide-y divide-gray-200">
              {filteredFiles.map((file) => (
                <div key={file.id} className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <input
                        type="checkbox"
                        checked={selectedFiles.includes(file.id)}
                        onChange={() => toggleFileSelection(file.id)}
                        className="mt-1 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                      />
                      
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3 mb-2">
                          {getStatusIcon(file.status)}
                          <h3 className="text-lg font-medium text-gray-900 truncate">
                            {file.drug_name ? `${file.drug_name}-${file.file_name}` : file.file_name}
                          </h3>
                          <Badge variant={getStatusBadgeVariant(file.status)}>
                            {file.status}
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-gray-600 mb-2 break-all">
                          <Link className="h-3 w-3 inline mr-1" />
                          {file.file_url}
                        </p>
                        
                        {file.comments && (
                          <p className="text-sm text-gray-600 mb-2">
                            {file.comments}
                          </p>
                        )}

                        {file.us_ma_date && (
                          <p className="text-sm text-gray-600 mb-2">
                            <span className="font-medium">US MA Date:</span> {file.us_ma_date}
                          </p>
                        )}
                        
                        <div className="flex items-center gap-4 text-xs text-gray-500">
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {new Date(file.created_at).toLocaleDateString()}
                          </span>
                          {file.creator_username && (
                            <span>By {file.creator_username}</span>
                          )}
                          {file.extraction_count !== undefined && (
                            <span className="flex items-center gap-1">
                              <BarChart3 className="h-3 w-3" />
                              {file.extraction_count} extractions
                            </span>
                          )}
                          {file.file_size && (
                            <span>{file.file_size}</span>
                          )}
                        </div>
                        
                        {file.processing_progress !== undefined && file.processing_progress > 0 && (
                          <div className="mt-3">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs text-gray-600">Processing Progress</span>
                              <span className="text-xs text-gray-600">{file.processing_progress}%</span>
                            </div>
                            <Progress value={file.processing_progress} className="h-2" />
                          </div>
                        )}
                        
                        {/* Pipeline Status Flow */}
                        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                          <div className="flex items-center justify-between text-xs">
                            <div className={`flex items-center gap-1 ${file.status === 'PENDING' ? 'text-yellow-600 font-medium' : 'text-gray-400'}`}>
                              <div className={`w-2 h-2 rounded-full ${file.status === 'PENDING' ? 'bg-yellow-500' : 'bg-gray-300'}`} />
                              PENDING
                            </div>
                            <div className="flex-1 h-px bg-gray-300 mx-2" />
                            <div className={`flex items-center gap-1 ${file.status === 'PROCESSING' ? 'text-blue-600 font-medium' : file.status === 'DOCUMENT_STORED' || file.status === 'INDEXING' || file.status === 'READY' ? 'text-green-600' : 'text-gray-400'}`}>
                              <div className={`w-2 h-2 rounded-full ${file.status === 'PROCESSING' ? 'bg-blue-500' : file.status === 'DOCUMENT_STORED' || file.status === 'INDEXING' || file.status === 'READY' ? 'bg-green-500' : 'bg-gray-300'}`} />
                              PROCESSING
                            </div>
                            <div className="flex-1 h-px bg-gray-300 mx-2" />
                            <div className={`flex items-center gap-1 ${file.status === 'DOCUMENT_STORED' ? 'text-blue-600 font-medium' : file.status === 'INDEXING' || file.status === 'READY' ? 'text-green-600' : 'text-gray-400'}`}>
                              <div className={`w-2 h-2 rounded-full ${file.status === 'DOCUMENT_STORED' ? 'bg-blue-500' : file.status === 'INDEXING' || file.status === 'READY' ? 'bg-green-500' : 'bg-gray-300'}`} />
                              DOCUMENT_STORED
                            </div>
                            <div className="flex-1 h-px bg-gray-300 mx-2" />
                            <div className={`flex items-center gap-1 ${file.status === 'INDEXING' ? 'text-purple-600 font-medium' : file.status === 'READY' ? 'text-green-600' : 'text-gray-400'}`}>
                              <div className={`w-2 h-2 rounded-full ${file.status === 'INDEXING' ? 'bg-purple-500' : file.status === 'READY' ? 'bg-green-500' : 'bg-gray-300'}`} />
                              INDEXING
                            </div>
                            <div className="flex-1 h-px bg-gray-300 mx-2" />
                            <div className={`flex items-center gap-1 ${file.status === 'READY' ? 'text-green-600 font-medium' : 'text-gray-400'}`}>
                              <div className={`w-2 h-2 rounded-full ${file.status === 'READY' ? 'bg-green-500' : 'bg-gray-300'}`} />
                              READY
                            </div>
                          </div>
                        </div>
                        
                        {file.error_message && (
                          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded">
                            <p className="text-sm text-red-700">{file.error_message}</p>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2 ml-4">
                      {/* Process button for PENDING, FAILED states */}
                      {(file.status === 'PENDING' || file.status === 'FAILED') && (
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleProcessFile(file.id)}
                          disabled={actionLoading[`process_${file.id}`]}
                        >
                          {actionLoading[`process_${file.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          ) : (
                            <Play className="h-4 w-4 mr-1" />
                          )}
                          Process
                        </Button>
                      )}
                      
                      {/* Index button for DOCUMENT_STORED state */}
                      {file.status === 'DOCUMENT_STORED' && (
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleIndexFile(file.id)}
                          disabled={actionLoading[`index_${file.id}`]}
                        >
                          {actionLoading[`index_${file.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          ) : (
                            <Upload className="h-4 w-4 mr-1" />
                          )}
                          Index to Vector DB
                        </Button>
                      )}
                      
                      {/* Retry Indexing button for FAILED state with indexing failure */}
                      {file.status === 'FAILED' && file.comments && file.comments.toLowerCase().includes('indexing') && (
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleIndexFile(file.id)}
                          disabled={actionLoading[`index_${file.id}`]}
                          className="border-orange-200 text-orange-700 hover:bg-orange-50"
                        >
                          {actionLoading[`index_${file.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          ) : (
                            <RefreshCw className="h-4 w-4 mr-1" />
                          )}
                          Retry Indexing
                        </Button>
                      )}
                      
                      {/* Show processing status for PROCESSING and INDEXING */}
                      {(file.status === 'PROCESSING' || file.status === 'INDEXING') && (
                        <Button variant="outline" size="sm" disabled>
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          {file.status === 'PROCESSING' ? 'Processing...' : 'Indexing...'}
                        </Button>
                      )}
                      
                      {/* Ready status - no action needed */}
                      {file.status === 'READY' && (
                        <Button variant="outline" size="sm" disabled>
                          <CheckCircle className="h-4 w-4 mr-1" />
                          Ready for Search
                        </Button>
                      )}
                      
                      {/* Reprocess button - Show for processed files that might need reprocessing */}
                      {['READY', 'FAILED', 'DOCUMENT_STORED'].includes(file.status) && (
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => {
                            setIsReprocessModalOpen(true);
                            setReprocessFileData(file);
                          }}
                          disabled={actionLoading[`reprocess_${file.id}`]}
                          className="text-purple-600 hover:text-purple-700 border-purple-200 hover:bg-purple-50"
                        >
                          {actionLoading[`reprocess_${file.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          ) : (
                            <RotateCcw className="h-4 w-4 mr-1" />
                          )}
                          Reprocess
                        </Button>
                      )}
                      
                      {/* Delete Vector DB - Show for files that might have vector docs */}
                      {['READY', 'FAILED'].includes(file.status) && (
                        <Button 
                          variant="outline" 
                          size="sm"
                          onClick={() => handleDeleteVectorDb(file.id)}
                          disabled={actionLoading[`delete_vectordb_${file.id}`]}
                          className="text-orange-600 hover:text-orange-700 border-orange-200 hover:bg-orange-50"
                        >
                          {actionLoading[`delete_vectordb_${file.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-1" />
                          ) : (
                            <HardDrive className="h-4 w-4 mr-1" />
                          )}
                          Delete Vector DB
                        </Button>
                      )}
                      
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleViewDocuments(file.id)}
                        disabled={viewLoading}
                      >
                        {viewLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                        ) : (
                          <Eye className="h-4 w-4 mr-1" />
                        )}
                        View
                      </Button>
                      
                      <Button 
                        variant="ghost" 
                        size="sm"
                        onClick={() => handleDeleteFile(file.id)}
                        disabled={actionLoading[`delete_${file.id}`]}
                        className="text-red-600 hover:text-red-700"
                      >
                        {actionLoading[`delete_${file.id}`] ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                        ) : (
                          <Trash2 className="h-4 w-4 mr-1" />
                        )}
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Pagination Controls */}
      {filteredFiles.length > 0 && (
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-gray-700">
            Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalCount)} of {totalCount} files
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadSourceFiles(currentPage - 1)}
              disabled={currentPage === 1 || loading}
            >
              Previous
            </Button>
            
            {totalPages > 1 && (
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
                      onClick={() => loadSourceFiles(pageNum)}
                      disabled={loading}
                      className="min-w-[40px]"
                    >
                      {pageNum}
                    </Button>
                  );
                })}
              </div>
            )}
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadSourceFiles(currentPage + 1)}
              disabled={currentPage === totalPages || loading}
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

      {/* Upload Modal - Enhanced with file upload and collection selection */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Add New Source File</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsUploadModalOpen(false);
                    setSelectedFile(null);
                    setUploadMethod('url');
                  }}
                  disabled={actionLoading.add || isUploading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Upload Method Selection */}
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Upload Method
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      value="url"
                      checked={uploadMethod === 'url'}
                      onChange={(e) => setUploadMethod(e.target.value as 'url' | 'file')}
                      className="text-blue-600"
                    />
                    <span className="text-sm">URL</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      value="file"
                      checked={uploadMethod === 'file'}
                      onChange={(e) => setUploadMethod(e.target.value as 'url' | 'file')}
                      className="text-blue-600"
                    />
                    <span className="text-sm">Upload PDF File</span>
                  </label>
                </div>
              </div>

              {/* Conditional Fields based on upload method */}
              {uploadMethod === 'url' ? (
                <>
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      File Name *
                    </label>
                    <Input
                      value={uploadForm.file_name}
                      onChange={(e) => setUploadForm({...uploadForm, file_name: e.target.value})}
                      placeholder="e.g., ozempic_prescribing_info.pdf"
                    />
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      File URL *
                    </label>
                    <Input
                      value={uploadForm.file_url}
                      onChange={(e) => setUploadForm({...uploadForm, file_url: e.target.value})}
                      placeholder="https://example.com/document.pdf"
                    />
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      Select PDF File *
                    </label>
                    <Input
                      type="file"
                      accept=".pdf"
                      onChange={handleFileChange}
                      className="cursor-pointer"
                    />
                    {selectedFile && (
                      <p className="text-sm text-gray-600 mt-1">
                        Selected: {selectedFile.name} ({(selectedFile.size / 1024 / 1024).toFixed(2)} MB)
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-700 mb-2 block">
                      File Name (optional)
                    </label>
                    <Input
                      value={uploadForm.file_name}
                      onChange={(e) => setUploadForm({...uploadForm, file_name: e.target.value})}
                      placeholder="Leave blank to use uploaded file name"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Drug Name
                </label>
                <Input
                  value={uploadForm.drug_name}
                  onChange={(e) => setUploadForm({...uploadForm, drug_name: e.target.value})}
                  placeholder="e.g., Ozempic, Lipitor, Advil"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Add to Collection
                </label>
                <Select
                  value={uploadForm.collection_id?.toString() || 'none'}
                  onValueChange={(value) => setUploadForm({...uploadForm, collection_id: value === 'none' ? undefined : parseInt(value)})}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a collection (optional)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {collections.map((collection) => (
                      <SelectItem key={collection.id} value={collection.id.toString()}>
                        {collection.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  US MA Date
                </label>
                <Input
                  value={uploadForm.us_ma_date}
                  onChange={(e) => setUploadForm({...uploadForm, us_ma_date: e.target.value})}
                  placeholder="DD/MM/YYYY (e.g., 27/03/2021)"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Description
                </label>
                <Textarea
                  value={uploadForm.description}
                  onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                  placeholder="Brief description of the document..."
                  rows={3}
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsUploadModalOpen(false);
                    setSelectedFile(null);
                    setUploadMethod('url');
                  }}
                  disabled={actionLoading.add || isUploading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleAddSource}
                  disabled={
                    (uploadMethod === 'url' && (!uploadForm.file_name || !uploadForm.file_url)) ||
                    (uploadMethod === 'file' && !selectedFile) ||
                    actionLoading.add ||
                    isUploading
                  }
                  className="flex items-center gap-2"
                >
                  {actionLoading.add || isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {isUploading ? 'Uploading...' : 'Add Source'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* FIXED: Custom Delete Confirmation Modal (replaces browser confirm) */}
      {isDeleteFileModalOpen && deleteFileData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center justify-between text-xl">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-gradient-to-r from-red-600 to-rose-600 rounded-lg flex items-center justify-center">
                    <Trash2 className="h-5 w-5 text-white" />
                  </div>
                  <span>Confirm Delete Source File</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsDeleteFileModalOpen(false);
                    setDeleteFileData(null);
                  }}
                  disabled={actionLoading[`delete_${deleteFileData.id}`]}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* File Information */}
              <div className="bg-gray-50 p-4 rounded-lg border">
                <h4 className="font-medium text-gray-900 mb-2">Source File Details</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">File Name:</span>
                    <span className="font-medium text-gray-900 break-all max-w-xs text-right">
                      {deleteFileData.drug_name ? `${deleteFileData.drug_name}-${deleteFileData.file_name}` : deleteFileData.file_name}
                    </span>
                </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Drug Name:</span>
                    <span className="font-medium text-gray-900">{deleteFileData.drug_name || 'N/A'}</span>
                          </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Current Status:</span>
                    <Badge variant={getStatusBadgeVariant(deleteFileData.status)}>{deleteFileData.status}</Badge>
                              </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Created:</span>
                    <span className="font-medium text-gray-900">{new Date(deleteFileData.created_at).toLocaleDateString()}</span>
                              </div>
                          </div>
                        </div>

              {/* Warning Information */}
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                        <div>
                    <h4 className="font-medium text-red-900 mb-2">This action will permanently:</h4>
                    <ul className="text-sm text-red-800 space-y-1">
                      <li className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                        Delete the source file record from the database
                      </li>
                      <li className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                        Remove all associated document chunks and metadata
                      </li>
                      <li className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                        Delete all vector database entries for this file
                      </li>
                      <li className="flex items-center gap-2">
                        <div className="w-1.5 h-1.5 bg-red-600 rounded-full"></div>
                        Remove the file from all search results
                      </li>
                    </ul>
                    <p className="text-red-800 font-medium mt-3">
                      ⚠️ This action cannot be undone.
                            </p>
                          </div>
                        </div>
                            </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsDeleteFileModalOpen(false);
                    setDeleteFileData(null);
                  }}
                  disabled={actionLoading[`delete_${deleteFileData.id}`]}
                >
                  Cancel
                </Button>
                <Button
                  onClick={confirmDeleteFile}
                  disabled={actionLoading[`delete_${deleteFileData.id}`]}
                  className="flex items-center gap-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700"
                >
                  {actionLoading[`delete_${deleteFileData.id}`] ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Delete Source File
                </Button>
                </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Bulk Upload Modal */}
      {isBulkUploadModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-4xl max-h-[90vh] flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Bulk Upload from Excel File</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsBulkUploadModalOpen(false);
                    setSelectedExcelFile(null);
                    setExcelData([]);
                    setExcelPreviewData([]);
                  }}
                  disabled={bulkUploadLoading || isFileProcessing}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h4 className="font-medium text-blue-900 mb-2">Instructions</h4>
                <ul className="text-sm text-blue-800 space-y-1">
                  <li>• Download the Excel template to see the required format</li>
                  <li>• Required columns: <code>file_name</code> and <code>file_url</code></li>
                  <li>• Optional columns: <code>drug_name</code>, <code>comments</code></li>
                  <li>• Upload your Excel file (.xlsx or .xls) and preview the data before uploading</li>
                </ul>
              </div>

              <div className="flex justify-center">
                <Button
                  variant="outline"
                  size="lg"
                  onClick={handleDownloadTemplate}
                  className="flex items-center gap-2"
                >
                  <Download className="h-5 w-5" />
                  Download Excel Template
                </Button>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Select Excel File
                </label>
                <Input
                  type="file"
                  accept=".xlsx,.xls"
                  onChange={handleExcelFileChange}
                  disabled={isFileProcessing || bulkUploadLoading}
                  className="w-full"
                />
                {isFileProcessing && (
                  <p className="text-sm text-blue-600 mt-2 flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Processing Excel file...
                  </p>
                )}
              </div>

              {/* Preview Data */}
              {excelPreviewData.length > 0 && (
                <div>
                  <h4 className="font-medium text-gray-900 mb-3">
                    Preview Data ({excelPreviewData.length} rows)
                  </h4>
                  <div className="border rounded-lg max-h-64 overflow-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Row</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">File Name</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">File URL</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Drug Name</th>
                          <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Comments</th>
                        </tr>
                      </thead>
                      <tbody>
                        {excelPreviewData.slice(0, 10).map((item, index) => (
                          <tr key={index} className="border-b">
                            <td className="px-3 py-2 text-gray-600">{item.row}</td>
                            <td className="px-3 py-2 font-medium">{item.file_name}</td>
                            <td className="px-3 py-2 text-blue-600 truncate max-w-xs">
                              {item.file_url}
                            </td>
                            <td className="px-3 py-2 text-gray-600">{item.drug_name || '-'}</td>
                            <td className="px-3 py-2 text-gray-600 truncate max-w-xs">
                              {item.comments || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {excelPreviewData.length > 10 && (
                      <div className="p-3 text-center text-sm text-gray-500 bg-gray-50 border-t">
                        ... and {excelPreviewData.length - 10} more rows
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsBulkUploadModalOpen(false);
                    setSelectedExcelFile(null);
                    setExcelData([]);
                    setExcelPreviewData([]);
                  }}
                  disabled={bulkUploadLoading || isFileProcessing}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleBulkUpload}
                  disabled={!selectedExcelFile || excelData.length === 0 || bulkUploadLoading || isFileProcessing}
                  className="flex items-center gap-2"
                >
                  {bulkUploadLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FileUp className="h-4 w-4" />
                  )}
                  Upload {excelData.length} Files
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Bulk Upload Result Modal */}
      {isBulkResultModalOpen && bulkUploadResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-4xl max-h-[90vh] flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Bulk Upload Results</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsBulkResultModalOpen(false);
                    setBulkUploadResult(null);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto space-y-6">
              {/* Summary */}
              <div className="grid grid-cols-3 gap-4">
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-blue-600">{bulkUploadResult.total_items}</div>
                    <div className="text-sm text-blue-800">Total Items</div>
                  </CardContent>
                </Card>
                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{bulkUploadResult.successful_items}</div>
                    <div className="text-sm text-green-800">Successful</div>
                  </CardContent>
                </Card>
                <Card className="bg-red-50 border-red-200">
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-red-600">{bulkUploadResult.failed_items}</div>
                    <div className="text-sm text-red-800">Failed</div>
                  </CardContent>
                </Card>
              </div>

              {/* Successful Items */}
              {bulkUploadResult.success_details && bulkUploadResult.success_details.length > 0 && (
                <div>
                  <h4 className="font-medium text-green-900 mb-3 flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    Successfully Uploaded ({bulkUploadResult.success_details.length})
                  </h4>
                  <div className="space-y-2">
                    {bulkUploadResult.success_details.map((item: any) => (
                      <div key={item.id} className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-medium text-green-900">Row {item.row}: {item.file_name}</span>
                            {item.drug_name && (
                              <span className="text-sm text-green-700 ml-2">({item.drug_name})</span>
                            )}
                          </div>
                          <div className="text-sm text-green-600">ID: {item.id}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Failed Items */}
              {bulkUploadResult.failure_details && bulkUploadResult.failure_details.length > 0 && (
                <div>
                  <h4 className="font-medium text-red-900 mb-3 flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-red-600" />
                    Failed Items ({bulkUploadResult.failure_details.length})
                  </h4>
                  <div className="space-y-2">
                    {bulkUploadResult.failure_details.map((item: any, index: number) => (
                      <div key={index} className="bg-red-50 border border-red-200 rounded-lg p-3">
                        <div className="mb-2">
                          <span className="font-medium text-red-900">Row {item.row}: {item.item.file_name}</span>
                        </div>
                        <div className="text-sm text-red-700 bg-red-100 p-2 rounded">
                          <strong>Error:</strong> {item.error}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="flex justify-end pt-4">
                <Button
                  onClick={() => {
                    setIsBulkResultModalOpen(false);
                    setBulkUploadResult(null);
                  }}
                  className="flex items-center gap-2"
                >
                  <CheckCircle className="h-4 w-4" />
                  Close
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* View Documents Modal */}
      {isViewModalOpen && viewingDocuments && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-6xl max-h-[90vh] flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Document Details - {viewingDocuments.source_file.file_name}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsViewModalOpen(false);
                    setViewingDocuments(null);
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
              <div className="text-sm text-gray-600">
                <p><strong>Drug:</strong> {viewingDocuments.source_file.drug_name || 'N/A'}</p>
                <div><strong>Status:</strong> <Badge variant={getStatusBadgeVariant(viewingDocuments.source_file.status)}>{viewingDocuments.source_file.status}</Badge></div>
                <p><strong>Total Documents:</strong> {viewingDocuments.total_documents}</p>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-auto">
              {viewingDocuments.documents.length === 0 ? (
                <div className="text-center py-8">
                  <FileX className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                  <p className="text-gray-600">No document chunks found for this source file.</p>
                  </div>
              ) : (
                <div className="space-y-4">
                  {viewingDocuments.documents.map((doc, index) => (
                    <Card key={doc.id} className="border-l-4 border-l-blue-500">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-lg flex items-center justify-between">
                          <span>Chunk #{index + 1}</span>
                          <div className="flex items-center gap-2 text-sm text-gray-500">
                            <Calendar className="h-4 w-4" />
                            {new Date(doc.created_at).toLocaleDateString()}
                  </div>
                        </CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {/* Metadata Section */}
                        <div>
                          <h4 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                            <Info className="h-4 w-4" />
                            Metadata
                          </h4>
                          <div className="bg-gray-50 p-3 rounded-lg">
                            <div className="grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <span className="font-medium text-gray-700">File Name:</span>
                                <p className="text-gray-600">{doc.metadata.file_name || 'N/A'}</p>
                  </div>
                              <div>
                                <span className="font-medium text-gray-700">Page Number:</span>
                                <p className="text-gray-600">{doc.metadata.page_number || 'N/A'}</p>
                  </div>
                              <div>
                                <span className="font-medium text-gray-700">Drug Name:</span>
                                <p className="text-gray-600">{doc.metadata.drug_name || 'N/A'}</p>
                </div>
                  <div>
                                <span className="font-medium text-gray-700">Content Length:</span>
                                <p className="text-gray-600">{doc.doc_content.length} characters</p>
                  </div>
                </div>
              </div>
              </div>

                        {/* Document Content Section */}
                  <div>
                          <h4 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                            <FileText className="h-4 w-4" />
                            Document Content
                          </h4>
                          <div className="bg-white border rounded-lg p-4 max-h-64 overflow-y-auto">
                            <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                              {doc.doc_content}
                            </p>
                </div>
              </div>

                        {/* Original Content Section (if available) */}
                        {doc.metadata.original_content && (
                  <div>
                            <h4 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                              <Copy className="h-4 w-4" />
                              Original Content
                            </h4>
                            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 max-h-64 overflow-y-auto">
                              <p className="text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
                                {doc.metadata.original_content}
                              </p>
                  </div>
                </div>
                        )}
                      </CardContent>
                    </Card>
                  ))}
              </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Reprocess Confirmation Modal */}
      {isReprocessModalOpen && reprocessFileData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center justify-between text-xl">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-gradient-to-r from-purple-600 to-purple-600 rounded-lg flex items-center justify-center">
                    <RotateCcw className="h-5 w-5 text-white" />
                  </div>
                  <span>Confirm Reprocess File</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsReprocessModalOpen(false);
                    setReprocessFileData(null);
                  }}
                  disabled={actionLoading[`reprocess_${reprocessFileData.id}`]}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <h3 className="font-medium text-purple-900 mb-2">File Details</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-purple-700">File Name:</span>
                    <span className="font-medium text-purple-900">{reprocessFileData.file_name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-purple-700">Current Status:</span>
                    <Badge variant={getStatusBadgeVariant(reprocessFileData.status)}>
                      {reprocessFileData.status}
                    </Badge>
                  </div>
                  {reprocessFileData.drug_name && (
                  <div className="flex justify-between">
                      <span className="text-purple-700">Drug Name:</span>
                      <span className="font-medium text-purple-900">{reprocessFileData.drug_name}</span>
                  </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-purple-700">Created:</span>
                    <span className="font-medium text-purple-900">
                      {new Date(reprocessFileData.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>

              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-amber-900 mb-1">Reprocessing Information</h4>
                    <p className="text-sm text-amber-800">
                      This will restart the processing pipeline for this file. The current status will change to "PROCESSING" 
                      and the file will go through document extraction and indexing again.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsReprocessModalOpen(false);
                    setReprocessFileData(null);
                  }}
                  disabled={actionLoading[`reprocess_${reprocessFileData.id}`]}
                >
                  Cancel
                </Button>
                <Button
                  onClick={() => handleReprocessFile(reprocessFileData.id)}
                  disabled={actionLoading[`reprocess_${reprocessFileData.id}`]}
                  className="bg-gradient-to-r from-purple-600 to-purple-600 hover:from-purple-700 hover:to-purple-700 text-white"
                >
                  {actionLoading[`reprocess_${reprocessFileData.id}`] ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Reprocessing...
                    </>
                  ) : (
                    <>
                      <RotateCcw className="h-4 w-4 mr-2" />
                      Confirm Reprocess
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
      </div>
    </div>
  );
} 