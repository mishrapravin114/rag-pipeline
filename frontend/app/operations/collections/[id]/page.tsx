// Minor update
"use client";

// Declare global types for Google APIs
declare global {
  interface Window {
    gapi: any;
    google: any;
  }
}

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  ArrowLeft,
  FileText,
  Plus,
  Search,
  Trash2,
  Calendar,
  X,
  Loader2,
  AlertCircle,
  Info,
  CheckCircle,
  FileUp,
  Edit2,
  MessageSquare,
  ExternalLink,
  Download,
  Database,
  Play,
  FileOutput
} from 'lucide-react';
import { apiService } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { ChatModalProfessional } from '@/components/dashboard/ChatModalProfessional';
import { EnhancedSourceDocuments } from '@/components/chat/EnhancedSourceDocuments';
import { API_BASE_URL } from '@/config/api';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { MetadataResultsTab } from '@/components/collections/MetadataResultsTab';
import { ExtractionHistoryTab } from '@/components/collections/ExtractionHistoryTab';
import { ExtractMetadataTab } from '@/components/collections/ExtractMetadataTab';

interface Collection {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
}

interface Document {
  id: number;
  file_name: string;
  file_url: string;
  entity_name?: string;
  status: string;
  collection_status?: string;
  error_message?: string;
  is_indexed_in_collection?: boolean;
  indexed_collections?: string[];
  us_ma_date?: string;
  created_at: string;
}

export default function CollectionDetailsPage() {
  const router = useRouter();
  const params = useParams();
  const collectionId = parseInt(params.id as string);
  const { user } = useAuth();
  
  const [collection, setCollection] = useState<Collection | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [availableDocuments, setAvailableDocuments] = useState<Document[]>([]);
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // API pagination data
  const [apiTotalDocuments, setApiTotalDocuments] = useState(0);
  const [apiTotalPages, setApiTotalPages] = useState(1);
  
  // Modal states
  const [isAddDocumentsModalOpen, setIsAddDocumentsModalOpen] = useState(false);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [addDocsActiveTab, setAddDocsActiveTab] = useState<'existing' | 'upload' | 'bulk'>('existing');
  
  // File upload states
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [filePreviewData, setFilePreviewData] = useState<Array<{
    file: File;
    entityName: string;
    originalEntityName: string;
  }>>([]);
  const [uploadProgress, setUploadProgress] = useState<{ [key: string]: number }>({});
  const [isUploading, setIsUploading] = useState(false);
  
  // Bulk upload states
  const [selectedExcelFile, setSelectedExcelFile] = useState<File | null>(null);
  const [excelData, setExcelData] = useState<Array<{
    file_name: string;
    file_url: string;
    entity_name?: string;
    comments?: string;
    us_ma_date?: string;
  }>>([]);
  const [excelPreviewData, setExcelPreviewData] = useState<any[]>([]);
  const [isFileProcessing, setIsFileProcessing] = useState(false);
  const [bulkUploadLoading, setBulkUploadLoading] = useState(false);
  const [bulkUploadResult, setBulkUploadResult] = useState<any>(null);
  const [isBulkResultModalOpen, setIsBulkResultModalOpen] = useState(false);
  
  // Pagination and search states for Add Documents modal
  const [modalSearchTerm, setModalSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalAvailableDocuments, setTotalAvailableDocuments] = useState(0);
  const [modalLoading, setModalLoading] = useState(false);
  const ITEMS_PER_PAGE = 10;
  
  // Pagination states for documents list
  const [documentsPage, setDocumentsPage] = useState(1);
  const [documentsPerPage, setDocumentsPerPage] = useState(50);
  const [totalDocumentsCount, setTotalDocumentsCount] = useState(0);
  
  // Action loading states
  const [actionLoading, setActionLoading] = useState<{ [key: string]: boolean }>({});
  
  // Chat modal state
  const [isChatModalOpen, setIsChatModalOpen] = useState(false);
  
  // Google Drive state
  const [isGooglePickerApiLoaded, setGooglePickerApiLoaded] = useState(false);

  // Vector details modal state
  const [isVectorDetailsModalOpen, setIsVectorDetailsModalOpen] = useState(false);
  const [vectorDetails, setVectorDetails] = useState<any>(null);
  const [vectorDetailsLoading, setVectorDetailsLoading] = useState(false);
  const [vectorDetailsPage, setVectorDetailsPage] = useState(1);
  const VECTOR_PAGE_SIZE = 10;

  // Active tab state
  const [activeTab, setActiveTab] = useState('documents');


  // Load collection details
  const loadCollectionDetails = async (page?: number, pageSize?: number) => {
    try {
      setLoading(true);
      setError(null);
      
      const result = await apiService.getCollectionDetails(
        collectionId,
        page || documentsPage,
        pageSize || documentsPerPage,
        searchTerm,
        statusFilter
      );
      setCollection(result.collection);
      // Fix file URLs to include the full backend URL
      const documentsWithFullUrls = (result.documents || []).map((doc: Document) => ({
        ...doc,
        file_url: doc.file_url.startsWith('http') 
          ? doc.file_url 
          : `${API_BASE_URL}${doc.file_url}`
      }));
      
      setDocuments(documentsWithFullUrls);
      setApiTotalDocuments(result.total_documents);
      setApiTotalPages(result.total_pages);
      setTotalDocumentsCount(result.total_documents);
      
    } catch (error) {
      console.error('Error loading collection details:', error);
      setError('Failed to load collection details. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Load available documents for adding with pagination and search
  const loadAvailableDocuments = async (page: number = 1, search: string = '') => {
    try {
      setModalLoading(true);
      const offset = (page - 1) * ITEMS_PER_PAGE;
      
      // Load documents with READY, DOCUMENT_STORED, or PENDING status
      // We'll make multiple requests and combine the results
      const statuses = ['READY', 'DOCUMENT_STORED', 'PENDING'];
      const allDocuments: any[] = [];
      let totalCount = 0;
      
      for (const status of statuses) {
        try {
          const result = await apiService.getSourceFiles({ 
            status: status, 
            limit: 1000, // Get more to ensure we have enough after filtering
            offset: 0,
            search: search || undefined,
            exclude_collection: collectionId
          });
          allDocuments.push(...result.source_files);
          totalCount += result.total_count;
        } catch (error) {
          console.error(`Error loading ${status} documents:`, error);
        }
      }
      
      // Remove duplicates based on ID and fix URLs
      const uniqueDocuments = Array.from(
        new Map(allDocuments.map(doc => [doc.id, {
          ...doc,
          file_url: doc.file_url.startsWith('http') 
            ? doc.file_url 
            : `${API_BASE_URL}${doc.file_url}`
        }])).values()
      );
      
      // Sort by created_at descending
      uniqueDocuments.sort((a, b) => 
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      
      // Apply pagination on the client side
      const paginatedDocuments = uniqueDocuments.slice(offset, offset + ITEMS_PER_PAGE);
      
      setAvailableDocuments(paginatedDocuments);
      setTotalAvailableDocuments(uniqueDocuments.length);
      setCurrentPage(page);
    } catch (error) {
      console.error('Error loading available documents:', error);
      setError('Failed to load available documents');
    } finally {
      setModalLoading(false);
    }
  };

  // Set filtered documents from API response
  useEffect(() => {
    setFilteredDocuments(documents);
  }, [documents]);

  // Load available documents when modal opens
  useEffect(() => {
    if (isAddDocumentsModalOpen) {
      setModalSearchTerm('');
      setCurrentPage(1);
      loadAvailableDocuments(1, '');
      // Reset file upload states
      setSelectedFiles([]);
      setFilePreviewData([]);
      setUploadProgress({});
      // Reset bulk upload states
      setSelectedExcelFile(null);
      setExcelData([]);
      setExcelPreviewData([]);
      setAddDocsActiveTab('existing');
    }
  }, [isAddDocumentsModalOpen]);

  // Debounced search effect
  useEffect(() => {
    if (!isAddDocumentsModalOpen) return;
    
    const debounceTimer = setTimeout(() => {
      loadAvailableDocuments(1, modalSearchTerm);
    }, 300);

    return () => clearTimeout(debounceTimer);
  }, [modalSearchTerm]);

  // Reload when pagination or search term changes
  useEffect(() => {
    if (collectionId) {
      loadCollectionDetails();
    }
  }, [collectionId, documentsPage, documentsPerPage, searchTerm]);
  
  // Reload when status filter changes
  useEffect(() => {
    if (collectionId) {
      setDocumentsPage(1);
      loadCollectionDetails(1, documentsPerPage);
    }
  }, [statusFilter]);


  // Add documents to collection
  const handleAddDocuments = async () => {
    if (selectedDocumentIds.length === 0) {
      setError('Please select at least one document to add');
      return;
    }

    try {
      setActionLoading({ ...actionLoading, add: true });
      
      await apiService.addDocumentsToCollection(collectionId, selectedDocumentIds);
      
      // Reload collection details
      await loadCollectionDetails();
      
      setIsAddDocumentsModalOpen(false);
      setSelectedDocumentIds([]);
      setError(null);
      
    } catch (error) {
      console.error('Error adding documents:', error);
      setError('Failed to add documents. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, add: false });
    }
  };

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    const pdfFiles = files.filter(file => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf'));
    
    if (pdfFiles.length !== files.length) {
      setError('Only PDF files are allowed');
    }
    
    setSelectedFiles(pdfFiles);
    
    // Extract entity names from filenames
    const previewData = pdfFiles.map(file => {
      const fileName = file.name;
      const entityName = fileName.split('_')[0] || fileName.replace('.pdf', '');
      return {
        file,
        entityName,
        originalEntityName: entityName
      };
    });
    
    setFilePreviewData(previewData);
  };

  // Update entity name for a file
  const updateEntityName = (index: number, newEntityName: string) => {
    const updated = [...filePreviewData];
    updated[index].entityName = newEntityName;
    setFilePreviewData(updated);
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
          const processedData: typeof excelData = [];
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
            const item = {
              file_name: fileName.toString().trim(),
              file_url: fileUrl.toString().trim(),
              entity_name: (rowData.entity_name || rowData.entityname || rowData['entity name'] || '')?.toString().trim() || undefined,
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
      
      const result = await apiService.bulkUploadToCollection(collectionId, excelData);
      
      setBulkUploadResult(result);
      setIsAddDocumentsModalOpen(false);
      setIsBulkResultModalOpen(true);
      
      // Reset form
      setSelectedExcelFile(null);
      setExcelData([]);
      setExcelPreviewData([]);
      
      // Refresh the collection details if there were successful uploads
      if (result.successful_items > 0) {
        await loadCollectionDetails();
      }
      
    } catch (error) {
      console.error('Error in bulk upload:', error);
      setError('Failed to process bulk upload. Please try again.');
    } finally {
      setBulkUploadLoading(false);
    }
  };

  // Handle file upload and add to collection
  const handleUploadAndAdd = async () => {
    if (filePreviewData.length === 0) {
      setError('Please select files to upload');
      return;
    }

    try {
      setIsUploading(true);
      setError(null);
      const uploadedFileIds: number[] = [];
      
      // Upload files one by one
      for (let i = 0; i < filePreviewData.length; i++) {
        const { file, entityName } = filePreviewData[i];
        const formData = new FormData();
        formData.append('file', file);
        formData.append('entity_name', entityName);
        formData.append('collection_id', collectionId.toString());
        
        try {
          // Update progress
          setUploadProgress(prev => ({ ...prev, [file.name]: 0 }));
          
          const result = await apiService.uploadSourceFile(formData);
          uploadedFileIds.push(result.id);
          
          // Update progress to 100%
          setUploadProgress(prev => ({ ...prev, [file.name]: 100 }));
        } catch (error) {
          console.error(`Failed to upload ${file.name}:`, error);
          setError(`Failed to upload ${file.name}`);
          // Continue with other files
        }
      }
      
      if (uploadedFileIds.length > 0) {
        // Add uploaded files to collection
        await apiService.addDocumentsToCollection(collectionId, uploadedFileIds);
        
        // Reload collection details
        await loadCollectionDetails();
        
        // Close modal and reset states
        setIsAddDocumentsModalOpen(false);
        setSelectedFiles([]);
        setFilePreviewData([]);
        setUploadProgress({});
      }
      
    } catch (error) {
      console.error('Error uploading files:', error);
      setError('Failed to upload files. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };

  // Remove document from collection
  const handleRemoveDocument = async (documentId: number) => {
    try {
      setActionLoading({ ...actionLoading, [`remove_${documentId}`]: true });
      
      await apiService.removeDocumentFromCollection(collectionId, documentId);
      
      // Reload collection details to refresh the list
      await loadCollectionDetails();
      setError(null);
      
    } catch (error) {
      console.error('Error removing document:', error);
      setError('Failed to remove document. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, [`remove_${documentId}`]: false });
    }
  };


  // Chat with collection
  const handleChatWithCollection = () => {
    // Open chat modal with all documents from the collection
    setIsChatModalOpen(true);
  };

  // Load metadata groups with pagination and search
  const loadMetadataGroups = async (page: number = 1, search: string = '') => {
    try {
      setMetadataGroupsLoading(true);
      const result = await apiService.getMetadataGroups(page, metadataGroupsPageSize, search);
      console.log('Metadata groups result:', result);
      
      // Ensure we have the correct response format
      if (result && typeof result === 'object' && 'groups' in result) {
        const groupsArray = Array.isArray(result.groups) ? result.groups : [];
        console.log('Setting metadata groups:', groupsArray);
        setMetadataGroups(groupsArray);
        setMetadataGroupsTotal(result.total || 0);
        setMetadataGroupsTotalPages(Math.ceil((result.total || 0) / metadataGroupsPageSize));
      } else {
        // Fallback for old API format (direct array)
        const groupsArray = Array.isArray(result) ? result : [];
        console.log('Setting metadata groups (fallback):', groupsArray);
        setMetadataGroups(groupsArray);
        setMetadataGroupsTotal(groupsArray.length);
        setMetadataGroupsTotalPages(1);
      }
      setMetadataGroupsPage(page);
    } catch (error) {
      console.error('Error loading metadata groups:', error);
      toast.error('Failed to load metadata groups');
      // Ensure state is valid even on error
      setMetadataGroups([]);
      setMetadataGroupsTotal(0);
      setMetadataGroupsTotalPages(0);
    } finally {
      setMetadataGroupsLoading(false);
    }
  };


  
  // Load vector database details
  const handleViewDetails = async (page: number = 1) => {
    try {
      setVectorDetailsLoading(true);
      if (!isVectorDetailsModalOpen) {
        setIsVectorDetailsModalOpen(true);
      }
      
      const details = await apiService.getCollectionVectorDetails(collectionId, page, VECTOR_PAGE_SIZE);
      setVectorDetails(details);
      setVectorDetailsPage(page);
      
    } catch (error) {
      console.error('Error loading vector details:', error);
      setError('Failed to load vector database details');
      setIsVectorDetailsModalOpen(false);
    } finally {
      setVectorDetailsLoading(false);
    }
  };

  const handleGoogleDriveImport = async () => {
    try {
      const authStatus = await apiService.checkGoogleAuth();
      if (!authStatus.authenticated) {
        const response = await apiService.getGoogleAuthUrl();
        const authWindow = window.open(response.url, '_blank', 'width=500,height=600');
        
        // Check if auth window closed and refresh user profile
        const checkInterval = setInterval(async () => {
          if (authWindow?.closed) {
            clearInterval(checkInterval);
            // Refresh user profile to get the Google access token
            const profile = await apiService.getUserProfile();
            if (profile.google_access_token) {
              // Update the user in auth state
              window.location.reload(); // Reload to refresh auth state
            }
          }
        }, 1000);
        return;
      }
      loadGooglePicker();
    } catch (error) {
      console.error('Error with Google Drive import:', error);
    }
  };

  const loadGooglePicker = () => {
    if (isGooglePickerApiLoaded && window.google && window.google.picker) {
      createPicker();
      return;
    }

    // Check if gapi is already loaded
    if (window.gapi) {
      window.gapi.load('picker', {
        callback: () => {
          setGooglePickerApiLoaded(true);
          createPicker();
        },
        onerror: () => {
          console.error('Failed to load Google Picker API');
          toast.error('Failed to load Google Picker', {
            description: 'Please refresh the page and try again',
            duration: 5000,
          });
        }
      });
      return;
    }

    // Load the Google API client library
    const script = document.createElement('script');
    script.src = 'https://apis.google.com/js/api.js';
    script.onload = () => {
      // Load the picker API
      window.gapi.load('picker', {
        callback: () => {
          setGooglePickerApiLoaded(true);
          createPicker();
        },
        onerror: () => {
          console.error('Failed to load Google Picker API');
          toast.error('Failed to load Google Picker', {
            description: 'Please refresh the page and try again',
            duration: 5000,
          });
        }
      });
    };
    script.onerror = () => {
      console.error('Failed to load Google API script');
      toast.error('Failed to load Google API', {
        description: 'Check your internet connection',
        duration: 5000,
      });
    };
    document.body.appendChild(script);
  };

  const createPicker = async () => {
    // Get the latest user profile to ensure we have the token
    const profile = await apiService.getUserProfile();
    if (!profile.google_access_token) {
      console.error('No Google access token found');
      // Re-trigger authentication
      handleGoogleDriveImport();
      return;
    }

    // Make sure google.picker is available
    if (!window.google || !window.google.picker) {
      console.error('Google Picker API not loaded');
      setGooglePickerApiLoaded(false);
      loadGooglePicker();
      return;
    }

    try {
      // Create the picker with minimal configuration
      const picker = new window.google.picker.PickerBuilder()
        .addView(window.google.picker.ViewId.DOCS)
        .setOAuthToken(profile.google_access_token)
        .setCallback(pickerCallback)
        .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
        .build();
      
      picker.setVisible(true);
    } catch (error) {
      console.error('Error creating Google Picker:', error);
      toast.error('Failed to open Google Drive picker', {
        description: 'Please try again or check your Google Drive permissions',
        duration: 4000,
      });
    }
  };

  const pickerCallback = async (data: any) => {
    console.log('Picker callback triggered with action:', data.action);
    if (data.action === window.google.picker.Action.PICKED) {
      const fileIds = data.docs.map((doc: any) => doc.id);
      console.log('Selected file IDs from picker:', fileIds);
      try {
        const result = await apiService.uploadFromGoogleDrive(fileIds);
        console.log('Google Drive upload result:', result);
        
        if (result.failedFiles && result.failedFiles.length > 0) {
          // Show error toast for failed files
          result.failedFiles.forEach((f: any) => {
            toast.error(`Failed to download file`, {
              description: f.error,
              duration: 5000,
            });
          });
        }
        
        if (result.totalDownloaded > 0) {
          // Extract file IDs from downloaded files
          const downloadedFileIds = result.downloadedFiles
            .map((file: any) => file.id)
            .filter((id: any) => id !== undefined && id !== null);
          
          console.log('Downloaded files:', result.downloadedFiles);
          console.log('File IDs to add to collection:', downloadedFileIds);
          console.log('Adding to collection ID:', collectionId);
          
          if (downloadedFileIds.length === 0) {
            console.error('No file IDs found in the response!');
            toast.error('Files uploaded but IDs not returned', {
              description: 'Backend response missing file IDs',
              duration: 5000,
            });
            await loadCollectionDetails();
            return;
          }
          
          // Add the downloaded files to the collection
          try {
            const addResult = await apiService.addDocumentsToCollection(collectionId, downloadedFileIds);
            console.log('Add to collection result:', addResult);
          } catch (addError) {
            console.error('Error adding documents to collection:', addError);
            toast.error('Files uploaded but failed to add to collection', {
              description: 'Please try adding them manually from the documents list',
              duration: 5000,
            });
            // Still refresh to show the uploaded files
            await loadCollectionDetails();
            return;
          }
          
          // Show success notification
          toast.success(`Successfully added ${result.totalDownloaded} file(s) to collection`, {
            description: result.totalDownloaded === 1 
              ? result.downloadedFiles[0].originalFileName 
              : `${result.totalDownloaded} files added`,
            duration: 4000,
          });
          
          await loadCollectionDetails();
          console.log('Collection details reloaded');
          setIsAddDocumentsModalOpen(false);
        }
      } catch (error) {
        console.error('Error uploading from Google Drive:', error);
        toast.error('Failed to upload files from Google Drive', {
          description: error instanceof Error ? error.message : 'An unexpected error occurred',
          duration: 5000,
        });
      }
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

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
        <span className="text-gray-600">Loading collection...</span>
      </div>
    );
  }

  if (!collection) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="text-center p-8">
            <AlertCircle className="h-12 w-12 text-red-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Collection Not Found</h3>
            <p className="text-gray-600 mb-6">The collection you're looking for doesn't exist.</p>
            <Button onClick={() => router.push('/operations/collections')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Collections
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            onClick={() => router.push('/operations/collections')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Collections
          </Button>
          
          <div className="flex items-start justify-between">
            <div>
              <h1 className="page-title">{collection.name}</h1>
              {collection.description && (
                <p className="text-blue-700 mt-1">{collection.description}</p>
              )}
              <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
                <span className="flex items-center gap-1">
                  <Calendar className="h-4 w-4" />
                  Created: {new Date(collection.created_at).toLocaleDateString()}
                </span>
                <span className="flex items-center gap-1">
                  <FileText className="h-4 w-4" />
                  {apiTotalDocuments} documents
                  <button
                    onClick={() => handleViewDetails(1)}
                    className="ml-1 text-gray-500 hover:text-gray-700 transition-colors"
                    title="View vector database details"
                  >
                    <Info className="h-4 w-4" />
                  </button>
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <Button
                variant="outline"
                onClick={() => router.push(`/operations/collections`)}
                className="flex items-center gap-2"
              >
                <Edit2 className="h-4 w-4" />
                Edit Collection
              </Button>
              <Button
                onClick={handleChatWithCollection}
                className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white"
                disabled={documents.filter(doc => doc.collection_status === 'INDEXED').length === 0}
              >
                <MessageSquare className="h-4 w-4" />
                Chat with Collection
              </Button>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <Card className="border-red-200 bg-red-50 mb-6">
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

        {/* Search and Actions */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <div className="flex flex-col md:flex-row gap-4">
              <div className="flex-1">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    placeholder="Search documents in collection..."
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        setSearchTerm(searchInput);
                        setDocumentsPage(1);
                      }
                    }}
                    className="pl-10"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => {
                    setSearchTerm(searchInput);
                    setDocumentsPage(1);
                  }}
                  className="px-3"
                  title="Search"
                >
                  <Search className="h-4 w-4" />
                </Button>
                {(searchInput || searchTerm) && (
                  <Button
                    variant="ghost"
                    onClick={() => {
                      setSearchInput('');
                      setSearchTerm('');
                      setDocumentsPage(1);
                    }}
                    className="px-3"
                    title="Clear search"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                )}
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Filter by status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Documents</SelectItem>
                  <SelectItem value="indexed">AI Ready</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="not_indexed">Not AI Ready</SelectItem>
                </SelectContent>
              </Select>
              <Button
                onClick={() => setIsAddDocumentsModalOpen(true)}
                className="flex items-center gap-2"
              >
                <Plus className="h-4 w-4" />
                Add Documents
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Tabs for Documents and Metadata Results */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-1 mb-6">
            <TabsList className="grid grid-cols-4 w-full bg-transparent p-0 h-auto gap-1">
              <TabsTrigger 
                value="documents" 
                className="flex items-center justify-center gap-2 py-2.5 px-4 text-sm font-medium rounded-md transition-all duration-200 data-[state=active]:bg-blue-100 data-[state=active]:text-blue-900 data-[state=active]:shadow-sm data-[state=active]:border data-[state=active]:border-blue-200 data-[state=inactive]:text-gray-600 data-[state=inactive]:hover:text-gray-900 data-[state=inactive]:hover:bg-gray-50"
              >
                <FileText className="h-4 w-4" />
                <span>Documents</span>
                <span className="inline-flex items-center justify-center px-2 py-0.5 text-xs font-medium rounded-full data-[state=active]:bg-blue-700 data-[state=active]:text-white data-[state=inactive]:bg-gray-100 data-[state=inactive]:text-gray-600">
                  {apiTotalDocuments}
                </span>
              </TabsTrigger>
              <TabsTrigger 
                value="extract-metadata" 
                className="flex items-center justify-center gap-2 py-2.5 px-4 text-sm font-medium rounded-md transition-all duration-200 data-[state=active]:bg-blue-100 data-[state=active]:text-blue-900 data-[state=active]:shadow-sm data-[state=active]:border data-[state=active]:border-blue-200 data-[state=inactive]:text-gray-600 data-[state=inactive]:hover:text-gray-900 data-[state=inactive]:hover:bg-gray-50"
              >
                <Play className="h-4 w-4" />
                <span>Extract Metadata</span>
              </TabsTrigger>
              <TabsTrigger 
                value="metadata" 
                className="flex items-center justify-center gap-2 py-2.5 px-4 text-sm font-medium rounded-md transition-all duration-200 data-[state=active]:bg-blue-100 data-[state=active]:text-blue-900 data-[state=active]:shadow-sm data-[state=active]:border data-[state=active]:border-blue-200 data-[state=inactive]:text-gray-600 data-[state=inactive]:hover:text-gray-900 data-[state=inactive]:hover:bg-gray-50"
              >
                <Database className="h-4 w-4" />
                <span>Metadata Results</span>
              </TabsTrigger>
              <TabsTrigger 
                value="extraction-history" 
                className="flex items-center justify-center gap-2 py-2.5 px-4 text-sm font-medium rounded-md transition-all duration-200 data-[state=active]:bg-blue-100 data-[state=active]:text-blue-900 data-[state=active]:shadow-sm data-[state=active]:border data-[state=active]:border-blue-200 data-[state=inactive]:text-gray-600 data-[state=inactive]:hover:text-gray-900 data-[state=inactive]:hover:bg-gray-50"
              >
                <Calendar className="h-4 w-4" />
                <span>Extraction History</span>
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="documents">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    Documents in Collection
                {searchTerm && (
                  <span className="text-sm font-normal text-gray-600">
                    - Searching for "{searchTerm}"
                  </span>
                )}
              </CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {filteredDocuments.length === 0 ? (
              <div className="text-center p-12">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">
                  {searchTerm ? 'No documents found' : 'No documents in collection'}
                </h3>
                <p className="text-gray-600 mb-6">
                  {searchTerm 
                    ? 'Try adjusting your search terms'
                    : 'Add documents to this collection to get started'
                  }
                </p>
                {!searchInput && (
                  <Button onClick={() => setIsAddDocumentsModalOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Add Documents
                  </Button>
                )}
              </div>
            ) : (
              <div className="divide-y divide-gray-200">
                {filteredDocuments.map((doc) => (
                  <div key={doc.id} className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <Link 
                          href={doc.file_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="group"
                        >
                          <h3 className="text-lg font-medium text-gray-900 mb-1 group-hover:text-blue-600 transition-colors flex items-center gap-2">
                            {doc.entity_name ? `${doc.entity_name} - ${doc.file_name}` : doc.file_name}
                            <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </h3>
                          <p className="text-sm text-blue-600 hover:text-blue-800 hover:underline transition-colors mb-2">
                            {doc.file_url}
                          </p>
                        </Link>
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <span className="font-medium text-gray-800">File Status:</span>
                          <Badge 
                            variant={
                              doc.collection_status === 'INDEXED' ? 'success' :
                              doc.collection_status === 'NOT_INDEXED' ? 'secondary' :
                              doc.collection_status === 'FAILED' ? 'destructive' :
                              doc.collection_status === 'PENDING' ? 'warning' :
                              'outline'
                            }
                          >
                            {doc.collection_status === 'INDEXED' ? 'AI Ready' : 
                             doc.collection_status === 'NOT_INDEXED' ? 'Not Processed' : 
                             doc.collection_status}
                          </Badge>
                          <span className="font-medium text-gray-800">Date Added:</span>
                          <span>{new Date(doc.created_at).toLocaleDateString()}</span>
                        </div>
                        {/* Show error message if document failed */}
                        {doc.collection_status === 'FAILED' && doc.error_message && (
                          <div className="mt-2 text-xs text-red-600 bg-red-50 p-2 rounded">
                            <span className="font-medium">Error:</span> {doc.error_message}
                          </div>
                        )}
                      </div>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveDocument(doc.id)}
                        disabled={actionLoading[`remove_${doc.id}`]}
                        className="text-red-600 hover:text-red-700"
                      >
                        {actionLoading[`remove_${doc.id}`] ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
          {apiTotalDocuments > 0 && (
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <p className="text-sm text-gray-600">
                    Showing {((documentsPage - 1) * documentsPerPage) + 1} to{' '}
                    {Math.min(documentsPage * documentsPerPage, apiTotalDocuments)} of{' '}
                    {apiTotalDocuments} documents
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-gray-600">Page size:</span>
                    <Select value={documentsPerPage.toString()} onValueChange={(value) => {
                      setDocumentsPerPage(parseInt(value));
                      setDocumentsPage(1);
                    }}>
                      <SelectTrigger className="w-[80px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="50">50</SelectItem>
                        <SelectItem value="100">100</SelectItem>
                        <SelectItem value="200">200</SelectItem>
                        <SelectItem value="500">500</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDocumentsPage(documentsPage - 1)}
                    disabled={documentsPage === 1}
                  >
                    Previous
                  </Button>
                  <span className="text-sm text-gray-600 px-2">
                    Page {documentsPage} of {apiTotalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setDocumentsPage(documentsPage + 1)}
                    disabled={documentsPage === apiTotalPages}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          )}
            </Card>
          </TabsContent>

          <TabsContent value="extract-metadata">
            <ExtractMetadataTab 
              collectionId={collectionId}
              collectionName={collection?.name || ''}
              totalDocuments={apiTotalDocuments}
              onExtractionStarted={() => setActiveTab('extraction-history')}
            />
          </TabsContent>

          <TabsContent value="metadata">
            <MetadataResultsTab 
              collectionId={collectionId}
              collectionName={collection?.name || ''}
            />
          </TabsContent>

          <TabsContent value="extraction-history">
            <ExtractionHistoryTab 
              collectionId={collectionId}
              collectionName={collection?.name || ''}
            />
          </TabsContent>
        </Tabs>

        {/* Add Documents Modal */}
        {isAddDocumentsModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-4xl max-h-[90vh] flex flex-col">
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>Add Documents to Collection</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsAddDocumentsModalOpen(false);
                      setSelectedDocumentIds([]);
                    }}
                    disabled={actionLoading.add || isUploading}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              
              {/* Tab Navigation */}
              <div className="px-6 border-b">
                <div className="flex space-x-8">
                  <button
                    className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                      addDocsActiveTab === 'existing' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setAddDocsActiveTab('existing')}
                  >
                    Select Existing Documents
                  </button>
                  <button
                    className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                      addDocsActiveTab === 'upload' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setAddDocsActiveTab('upload')}
                  >
                    <FileUp className="h-4 w-4 inline mr-1" />
                    Upload New Documents
                  </button>
                  <button
                    className={`py-2 px-1 border-b-2 font-medium text-sm transition-colors ${
                      addDocsActiveTab === 'bulk' 
                        ? 'border-blue-600 text-blue-600' 
                        : 'border-transparent text-gray-500 hover:text-gray-700'
                    }`}
                    onClick={() => setAddDocsActiveTab('bulk')}
                  >
                    <FileUp className="h-4 w-4 inline mr-1" />
                    Bulk Upload
                  </button>
                </div>
              </div>
              
              <CardContent className="flex-1 overflow-auto">
                {addDocsActiveTab === 'existing' ? (
                  // Existing documents tab content
                  <>
                    <div className="mb-4 space-y-3">
                      <p className="text-sm text-gray-600">
                        Select documents to add to this collection. Showing documents with READY, DOCUMENT_STORED, or PENDING status.
                      </p>
                      
                      {/* Total count display */}
                      <div className="flex items-center justify-between">
                        <Badge variant="secondary" className="px-3 py-1">
                          <CheckCircle className="h-3 w-3 mr-1" />
                          {totalAvailableDocuments} available documents
                        </Badge>
                      </div>
                      
                      {/* Search input */}
                      <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                        <Input
                          placeholder="Search available documents..."
                          value={modalSearchTerm}
                          onChange={(e) => setModalSearchTerm(e.target.value)}
                          className="pl-10"
                        />
                      </div>
                    </div>
                    
                    {modalLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                  </div>
                ) : availableDocuments.length === 0 ? (
                  <div className="text-center py-8">
                    <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">No available documents to add.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {availableDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                          selectedDocumentIds.includes(doc.id)
                            ? 'bg-blue-50 border-blue-300'
                            : 'hover:bg-gray-50'
                        }`}
                        onClick={() => {
                          if (selectedDocumentIds.includes(doc.id)) {
                            setSelectedDocumentIds(selectedDocumentIds.filter(id => id !== doc.id));
                          } else {
                            setSelectedDocumentIds([...selectedDocumentIds, doc.id]);
                          }
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="checkbox"
                            checked={selectedDocumentIds.includes(doc.id)}
                            onChange={() => {}}
                            className="h-4 w-4 text-blue-600"
                          />
                          <div className="flex-1">
                            <h4 className="font-medium text-gray-900">
                              {doc.entity_name ? `${doc.entity_name} - ${doc.file_name}` : doc.file_name}
                            </h4>
                            <p className="text-sm text-gray-600">{doc.file_url}</p>
                          </div>
                          <Badge variant={getStatusBadgeVariant(doc.status)}>
                            {doc.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                  </>
                ) : addDocsActiveTab === 'upload' ? (
                  // Upload documents tab content
                  <div className="space-y-4">
                    <div className="mb-4">
                      <p className="text-sm text-gray-600 mb-4">
                        Upload PDF files directly to this collection. Entity names will be extracted from filenames (text before underscore).
                      </p>
                      
                      {/* File input */}
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                        <FileUp className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                        <p className="text-sm text-gray-600 mb-2">
                          Click to select PDF files or drag and drop
                        </p>
                        <input
                          type="file"
                          accept=".pdf"
                          multiple
                          onChange={handleFileSelect}
                          className="hidden"
                          id="file-upload"
                          disabled={isUploading}
                        />
                        <div className="flex justify-center items-center gap-4">
                          <label
                            htmlFor="file-upload"
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            Select Files
                          </label>
                          <Button
                              onClick={handleGoogleDriveImport}
                              className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                              <Download className="h-4 w-4 mr-2" />
                              Add from Google Drive
                          </Button>
                        </div>
                      </div>
                    </div>
                    
                    {/* File preview table */}
                    {filePreviewData.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 mb-3">
                          Selected Files ({filePreviewData.length})
                        </h4>
                        <div className="border rounded-lg overflow-hidden">
                          <table className="min-w-full divide-y divide-gray-200">
                            <thead className="bg-gray-50">
                              <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  File Name
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Entity Name
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Size
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                  Status
                                </th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {filePreviewData.map((item, index) => (
                                <tr key={index}>
                                  <td className="px-4 py-3 text-sm text-gray-900">
                                    {item.file.name}
                                  </td>
                                  <td className="px-4 py-3">
                                    <Input
                                      value={item.entityName}
                                      onChange={(e) => updateEntityName(index, e.target.value)}
                                      className="w-full max-w-xs text-sm"
                                      disabled={isUploading}
                                    />
                                  </td>
                                  <td className="px-4 py-3 text-sm text-gray-500">
                                    {(item.file.size / 1024 / 1024).toFixed(2)} MB
                                  </td>
                                  <td className="px-4 py-3">
                                    {uploadProgress[item.file.name] !== undefined ? (
                                      <div className="flex items-center gap-2">
                                        {uploadProgress[item.file.name] === 100 ? (
                                          <CheckCircle className="h-4 w-4 text-green-600" />
                                        ) : (
                                          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                                        )}
                                        <span className="text-sm">
                                          {uploadProgress[item.file.name]}%
                                        </span>
                                      </div>
                                    ) : (
                                      <Badge variant="outline">Pending</Badge>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        
                        {error && (
                          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                            <div className="flex items-center gap-2">
                              <AlertCircle className="h-4 w-4 text-red-600" />
                              <p className="text-sm text-red-800">{error}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  // Bulk upload tab content
                  <div className="space-y-4">
                    <div className="mb-4">
                      <p className="text-sm text-gray-600 mb-4">
                        Upload multiple documents at once using an Excel file. Download the template to see the required format.
                      </p>
                      
                      {/* Download template button */}
                      <div className="flex justify-center mb-6">
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
                      
                      {/* File input */}
                      <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
                        <FileUp className="h-12 w-12 text-gray-400 mx-auto mb-3" />
                        <p className="text-sm text-gray-600 mb-2">
                          Click to select Excel file or drag and drop
                        </p>
                        <input
                          type="file"
                          accept=".xlsx,.xls"
                          onChange={handleExcelFileChange}
                          className="hidden"
                          id="excel-upload"
                          disabled={isFileProcessing || bulkUploadLoading}
                        />
                        <label
                          htmlFor="excel-upload"
                          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          Select Excel File
                        </label>
                        {isFileProcessing && (
                          <p className="text-sm text-blue-600 mt-2 flex items-center justify-center gap-2">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Processing Excel file...
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* File preview table */}
                    {excelPreviewData.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-gray-900 mb-3">
                          Preview Data ({excelPreviewData.length} rows)
                        </h4>
                        <div className="border rounded-lg max-h-64 overflow-auto">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-50 sticky top-0">
                              <tr>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Row</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">File Name</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">File URL</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Entity Name</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">Comments</th>
                                <th className="px-3 py-2 text-left font-medium text-gray-700 border-b">US MA Date</th>
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
                                  <td className="px-3 py-2 text-gray-600">{item.entity_name || '-'}</td>
                                  <td className="px-3 py-2 text-gray-600 truncate max-w-xs">
                                    {item.comments || '-'}
                                  </td>
                                  <td className="px-3 py-2 text-gray-600">{item.us_ma_date || '-'}</td>
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
                        
                        {error && (
                          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md">
                            <div className="flex items-center gap-2">
                              <AlertCircle className="h-4 w-4 text-red-600" />
                              <p className="text-sm text-red-800">{error}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
              <div className="p-6 border-t space-y-4">
                {addDocsActiveTab === 'existing' ? (
                  <>
                    {/* Pagination controls for existing documents */}
                    {totalAvailableDocuments > ITEMS_PER_PAGE && (
                      <div className="flex items-center justify-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => loadAvailableDocuments(currentPage - 1, modalSearchTerm)}
                          disabled={currentPage === 1 || modalLoading}
                        >
                          Previous
                        </Button>
                        <span className="text-sm text-gray-600 px-4">
                          Page {currentPage} of {Math.ceil(totalAvailableDocuments / ITEMS_PER_PAGE)}
                        </span>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => loadAvailableDocuments(currentPage + 1, modalSearchTerm)}
                          disabled={currentPage === Math.ceil(totalAvailableDocuments / ITEMS_PER_PAGE) || modalLoading}
                        >
                          Next
                        </Button>
                      </div>
                    )}
                    
                    {/* Action buttons for existing documents */}
                    <div className="flex items-center justify-between">
                      <p className="text-sm text-gray-600">
                        {selectedDocumentIds.length} document(s) selected
                      </p>
                      <div className="flex gap-3">
                        <Button
                          variant="outline"
                          onClick={() => {
                            setIsAddDocumentsModalOpen(false);
                            setSelectedDocumentIds([]);
                          }}
                          disabled={actionLoading.add}
                        >
                          Cancel
                        </Button>
                        <Button
                          onClick={handleAddDocuments}
                          disabled={selectedDocumentIds.length === 0 || actionLoading.add}
                          className="flex items-center gap-2"
                        >
                          {actionLoading.add ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Plus className="h-4 w-4" />
                          )}
                          Add {selectedDocumentIds.length} Document(s)
                        </Button>
                      </div>
                    </div>
                  </>
                ) : addDocsActiveTab === 'upload' ? (
                  // Action buttons for upload tab
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-gray-600">
                      {filePreviewData.length} file(s) selected
                    </p>
                    <div className="flex gap-3">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setIsAddDocumentsModalOpen(false);
                          setSelectedFiles([]);
                          setFilePreviewData([]);
                        }}
                        disabled={isUploading}
                      >
                        Cancel
                      </Button>
                      <Button
                        onClick={handleUploadAndAdd}
                        disabled={filePreviewData.length === 0 || isUploading}
                        className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white"
                      >
                        {isUploading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <FileUp className="h-4 w-4" />
                        )}
                        Upload & Add {filePreviewData.length} File(s)
                      </Button>
                    </div>
                  </div>
                ) : (
                  // Action buttons for bulk upload tab
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-gray-600">
                      {excelPreviewData.length} file(s) to upload
                    </p>
                    <div className="flex gap-3">
                      <Button
                        variant="outline"
                        onClick={() => {
                          setIsAddDocumentsModalOpen(false);
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
                        disabled={excelData.length === 0 || bulkUploadLoading || isFileProcessing}
                        className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white"
                      >
                        {bulkUploadLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <FileUp className="h-4 w-4" />
                        )}
                        Upload & Add {excelData.length} File(s)
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}
        
        {/* Chat Modal */}
        {isChatModalOpen && apiTotalDocuments > 0 && collection && (
          <ChatModalProfessional
            isOpen={isChatModalOpen}
            onClose={() => setIsChatModalOpen(false)}
            sourceFileIds={[]}  // Pass empty array to query entire collection
            entityNames={documents.filter(doc => doc.collection_status === 'INDEXED').map(doc => doc.entity_name || doc.file_name)}
            collectionName={collection.name}
            collectionId={collection.id}
            isCollectionChat={true}  // Collection page chat uses old endpoint
          />
        )}
        
        {/* Vector Details Modal */}
        {isVectorDetailsModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
                    <Info className="h-5 w-5" />
                    Vector Database Details
                  </h2>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setIsVectorDetailsModalOpen(false)}
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </div>
              </div>
              
              <div className="p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
                {vectorDetailsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                    <span className="ml-3 text-gray-600">Loading vector details...</span>
                  </div>
                ) : vectorDetails ? (
                  <div className="space-y-6">
                    {/* Collection Info */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-lg">Collection Information</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-2">
                        <div>
                          <span className="text-sm text-gray-500">Collection Name:</span>
                          <p className="font-medium">{vectorDetails.collection_name}</p>
                        </div>
                        <div>
                          <span className="text-sm text-gray-500">ChromaDB Collection:</span>
                          <p className="font-mono text-sm bg-gray-100 p-2 rounded">
                            {vectorDetails.chromadb_collection_name}
                          </p>
                        </div>
                        <div>
                          <span className="text-sm text-gray-500">Status:</span>
                          <Badge className={`ml-2 ${
                            vectorDetails.status === 'active' 
                              ? 'bg-green-100 text-green-800' 
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {vectorDetails.status || 'Unknown'}
                          </Badge>
                        </div>
                      </CardContent>
                    </Card>
                    
                    {/* Vector Statistics */}
                    {vectorDetails.vector_stats && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">Vector Statistics</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <span className="text-sm text-gray-500">Total Vectors:</span>
                              <p className="text-2xl font-bold text-blue-600">
                                {vectorDetails.vector_stats.total_vectors.toLocaleString()}
                              </p>
                            </div>
                            <div>
                              <span className="text-sm text-gray-500">Unique Documents:</span>
                              <p className="text-2xl font-bold text-green-600">
                                {vectorDetails.vector_stats.unique_documents}
                              </p>
                            </div>
                          </div>
                          
                          <div>
                            <span className="text-sm text-gray-500">Average Chunks per Document:</span>
                            <p className="text-lg font-medium">
                              {vectorDetails.vector_stats.average_chunks_per_document.toFixed(1)}
                            </p>
                          </div>
                          
                          {/* Documents list will be shown below */}
                        </CardContent>
                      </Card>
                    )}
                    
                    {/* Documents List */}
                    {vectorDetails.documents && (
                      <Card>
                        <CardHeader>
                          <CardTitle className="text-lg">
                            Indexed Documents ({vectorDetails.documents.total})
                          </CardTitle>
                        </CardHeader>
                        <CardContent>
                          <div className="space-y-3">
                            {vectorDetails.documents.items.length > 0 ? (
                              <>
                                <div className="divide-y divide-gray-200">
                                  {vectorDetails.documents.items.map((doc, idx) => (
                                    <div key={doc.document_id} className="py-3 flex items-center justify-between">
                                      <div className="flex-1">
                                        <p className="text-sm font-medium text-gray-900">
                                          {doc.file_name}
                                        </p>
                                        {doc.entity_name && (
                                          <p className="text-xs text-gray-500">
                                            Entity: {doc.entity_name}
                                          </p>
                                        )}
                                      </div>
                                      <div className="text-right">
                                        <span className="text-sm text-gray-600">
                                          {doc.chunk_count} chunks
                                        </span>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                                
                                {/* Pagination */}
                                {vectorDetails.documents.total_pages > 1 && (
                                  <div className="flex items-center justify-between pt-4 border-t">
                                    <p className="text-sm text-gray-600">
                                      Showing {((vectorDetails.documents.page - 1) * vectorDetails.documents.page_size) + 1} to{' '}
                                      {Math.min(vectorDetails.documents.page * vectorDetails.documents.page_size, vectorDetails.documents.total)} of{' '}
                                      {vectorDetails.documents.total} documents
                                    </p>
                                    <div className="flex items-center gap-2">
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleViewDetails(vectorDetailsPage - 1)}
                                        disabled={vectorDetailsPage === 1 || vectorDetailsLoading}
                                      >
                                        Previous
                                      </Button>
                                      <span className="text-sm text-gray-600">
                                        Page {vectorDetails.documents.page} of {vectorDetails.documents.total_pages}
                                      </span>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => handleViewDetails(vectorDetailsPage + 1)}
                                        disabled={vectorDetailsPage === vectorDetails.documents.total_pages || vectorDetailsLoading}
                                      >
                                        Next
                                      </Button>
                                    </div>
                                  </div>
                                )}
                              </>
                            ) : (
                              <p className="text-sm text-gray-500 text-center py-4">
                                No documents found in vector database
                              </p>
                            )}
                          </div>
                        </CardContent>
                      </Card>
                    )}
                    
                    {/* Database Sync Status */}
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-lg">Database Sync Status</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="text-sm text-gray-500">Documents in Database:</span>
                            <p className="text-lg font-medium">
                              {vectorDetails.database_stats.documents_in_collection}
                            </p>
                          </div>
                          {vectorDetails.database_stats.synced !== undefined && (
                            <Badge className={
                              vectorDetails.database_stats.synced
                                ? 'bg-green-100 text-green-800'
                                : 'bg-yellow-100 text-yellow-800'
                            }>
                              {vectorDetails.database_stats.synced ? (
                                <>
                                  <CheckCircle className="h-4 w-4 mr-1" />
                                  Synced
                                </>
                              ) : (
                                <>
                                  <AlertCircle className="h-4 w-4 mr-1" />
                                  Out of Sync
                                </>
                              )}
                            </Badge>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                    
                    {/* Error Message */}
                    {vectorDetails.error && (
                      <Card className="border-red-200 bg-red-50">
                        <CardContent className="p-4">
                          <div className="flex items-start gap-3">
                            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                            <div>
                              <p className="text-sm font-medium text-red-800">Error</p>
                              <p className="text-sm text-red-600">{vectorDetails.error}</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">Failed to load vector details</p>
                  </div>
                )}
              </div>
            </div>
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
                              {item.entity_name && (
                                <span className="text-sm text-green-700 ml-2">({item.entity_name})</span>
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
      </div>
    </div>
  );
}