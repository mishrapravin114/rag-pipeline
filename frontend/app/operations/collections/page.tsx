// Minor update
// Minor update
"use client";

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Progress } from '@/components/ui/progress';
import { 
  Plus, 
  Search, 
  FolderOpen,
  Edit2, 
  Trash2,
  FileText,
  Calendar,
  X,
  Save,
  Loader2,
  AlertCircle,
  Info,
  Database,
  RefreshCw,
  Play,
  Eye,
  CheckCircle
} from 'lucide-react';
import { apiService } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';

interface Collection {
  id: number;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  document_count?: number;
  indexed_count?: number;
  pending_count?: number;
  indexing_status?: 'idle' | 'processing' | 'completed' | 'failed';
  active_job_id?: string;
  active_job_progress?: number;
}

interface IndexingJob {
  jobId: string;
  collectionId: number;
  totalDocuments: number;
  processedDocuments: number;
  failedDocuments: number;
  currentDocument?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number;
}

interface CollectionForm {
  name: string;
  description: string;
}

export default function CollectionsPage() {
  const router = useRouter();
  const { user } = useAuth();
  
  const [collections, setCollections] = useState<Collection[]>([]);
  const [filteredCollections, setFilteredCollections] = useState<Collection[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reindexingCollections, setReindexingCollections] = useState<Set<number>>(new Set());
  
  // Indexing states
  const [activeJobs, setActiveJobs] = useState<Map<number, IndexingJob>>(new Map());
  const [selectedCollections, setSelectedCollections] = useState<Set<number>>(new Set());
  const [indexingStatus, setIndexingStatus] = useState<Map<number, string>>(new Map()); // Track indexing status per collection
  
  
  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [deleteSourceFiles, setDeleteSourceFiles] = useState(false);
  
  // Form state
  const [collectionForm, setCollectionForm] = useState<CollectionForm>({
    name: '',
    description: ''
  });
  
  // Action loading states
  const [actionLoading, setActionLoading] = useState<{ [key: string]: boolean }>({});

  // Load collections
  const loadCollections = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Loading collections...');
      const result = await apiService.getCollections();
      console.log('Collections result:', result);
      setCollections(result.collections || []);
      
      // Check for active jobs in collection data
      const jobsFromCollections = new Map<number, IndexingJob>();
      console.log('Checking collections for active jobs...');
      result.collections?.forEach(collection => {
        console.log(`Collection ${collection.id}: active_job_id=${collection.active_job_id}, status=${collection.indexing_status}, progress=${collection.active_job_progress}`);
        if (collection.active_job_id && (collection.indexing_status === 'processing' || collection.indexing_status === 'pending')) {
          console.log(`Setting up active job for collection ${collection.id}`);
          
          // Calculate totalDocuments from the collection counts
          const totalDocuments = collection.pending_count + collection.indexed_count;
          const processedDocuments = collection.indexed_count;
          
          jobsFromCollections.set(collection.id, {
            jobId: collection.active_job_id,
            collectionId: collection.id,
            totalDocuments: totalDocuments || 1, // At least 1 to avoid division by zero
            processedDocuments: processedDocuments || 0,
            failedDocuments: 0,
            currentDocument: undefined,
            status: collection.indexing_status as 'processing' | 'pending',
            progress: totalDocuments > 0 ? (processedDocuments / totalDocuments * 100) : 0
          });
          
          // Store in sessionStorage
          sessionStorage.setItem(`indexing_job_${collection.id}`, collection.active_job_id);
        }
      });
      
      // Merge with existing active jobs
      if (jobsFromCollections.size > 0) {
        console.log('Found jobs from collections data:', jobsFromCollections);
        setActiveJobs(prev => {
          const merged = new Map(prev);
          jobsFromCollections.forEach((job, collectionId) => {
            merged.set(collectionId, job);
          });
          console.log('Updated activeJobs map:', merged);
          return merged;
        });
      } else {
        console.log('No active jobs found in collections data');
      }
      
    } catch (error) {
      console.error('Error loading collections:', error);
      setError('Failed to load collections. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  // Removed WebSocket and active jobs loading - job status is now included in collections data
  
  // Load on mount and when page becomes visible
  useEffect(() => {
    loadCollections();
    
    // Reload when navigating back to this page
    const handleFocus = () => {
      console.log('Page focused, reloading collections');
      loadCollections();
    };
    
    window.addEventListener('focus', handleFocus);
    
    return () => {
      window.removeEventListener('focus', handleFocus);
    };
  }, []);

  // Removed automatic polling - will use on-demand progress viewer instead

  // Filter collections based on search
  useEffect(() => {
    console.log('Filtering collections:', collections, 'with search term:', searchTerm);
    const filtered = collections.filter(collection => 
      collection.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (collection.description && collection.description.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setFilteredCollections(filtered);
  }, [collections, searchTerm]);

  // Create new collection
  const handleCreateCollection = async () => {
    if (!collectionForm.name.trim()) {
      setError('Collection name is required');
      return;
    }

    try {
      setActionLoading({ ...actionLoading, create: true });
      
      const newCollection = await apiService.createCollection({
        name: collectionForm.name,
        description: collectionForm.description || undefined
      });

      setCollections([newCollection, ...collections]);
      setIsCreateModalOpen(false);
      setCollectionForm({ name: '', description: '' });
      setError(null);
      
    } catch (error) {
      console.error('Error creating collection:', error);
      setError('Failed to create collection. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, create: false });
    }
  };

  // Update collection
  const handleUpdateCollection = async () => {
    if (!selectedCollection || !collectionForm.name.trim()) {
      setError('Collection name is required');
      return;
    }

    try {
      setActionLoading({ ...actionLoading, update: true });
      
      const updatedCollection = await apiService.updateCollection(selectedCollection.id, {
        name: collectionForm.name,
        description: collectionForm.description || undefined
      });

      setCollections(collections.map(col => 
        col.id === selectedCollection.id ? updatedCollection : col
      ));
      setIsEditModalOpen(false);
      setSelectedCollection(null);
      setCollectionForm({ name: '', description: '' });
      setError(null);
      
    } catch (error) {
      console.error('Error updating collection:', error);
      setError('Failed to update collection. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, update: false });
    }
  };

  // Delete collection
  const handleDeleteCollection = async () => {
    if (!selectedCollection) return;

    try {
      setActionLoading({ ...actionLoading, delete: true });
      
      const result = await apiService.deleteCollection(selectedCollection.id, deleteSourceFiles);
      
      setCollections(collections.filter(col => col.id !== selectedCollection.id));
      setIsDeleteModalOpen(false);
      setSelectedCollection(null);
      setDeleteSourceFiles(false); // Reset checkbox
      setError(null);
      
      // Show success message with details
      if (deleteSourceFiles && result.deleted_source_files > 0) {
        console.log(`Deleted collection with ${result.deleted_source_files} source files`);
      }
      
    } catch (error) {
      console.error('Error deleting collection:', error);
      setError('Failed to delete collection. Please try again.');
    } finally {
      setActionLoading({ ...actionLoading, delete: false });
    }
  };

  // Open edit modal
  const openEditModal = (collection: Collection) => {
    setSelectedCollection(collection);
    setCollectionForm({
      name: collection.name,
      description: collection.description || ''
    });
    setIsEditModalOpen(true);
  };

  // Open delete modal
  const openDeleteModal = (collection: Collection) => {
    setSelectedCollection(collection);
    setIsDeleteModalOpen(true);
  };
  
  // Handle collection selection
  const handleCollectionSelection = (collectionId: number, checked: boolean) => {
    setSelectedCollections(prev => {
      const newSet = new Set(prev);
      if (checked) {
        newSet.add(collectionId);
      } else {
        newSet.delete(collectionId);
      }
      return newSet;
    });
  };
  
  // Start indexing for a collection
  const startIndexing = async (collectionId: number) => {
    try {
      const collection = collections.find(c => c.id === collectionId);
      if (!collection) return;
      
      // Set status to processing immediately
      setIndexingStatus(prev => new Map(prev).set(collectionId, 'processing'));
      
      // Start indexing
      const result = await apiService.indexCollectionDocuments(collectionId, []);
      console.log(`Started indexing job ${result.job_id} for collection ${collectionId}`);
      
      // Store job ID for tracking
      setActiveJobs(prev => {
        const newJobs = new Map(prev);
        newJobs.set(collectionId, {
          jobId: result.job_id,
          collectionId,
          totalDocuments: result.total_documents || 0,
          processedDocuments: 0,
          failedDocuments: 0,
          status: 'processing',
          progress: 0
        });
        return newJobs;
      });
      
      // Store job ID in sessionStorage for persistence
      sessionStorage.setItem(`indexing_job_${collectionId}`, result.job_id);
      
    } catch (err) {
      console.error('Error in startIndexing:', err);
      setError('Failed to start indexing. Please try again.');
      setIndexingStatus(prev => new Map(prev).set(collectionId, 'failed'));
      
      // Clear failed status after 3 seconds
      setTimeout(() => {
        setIndexingStatus(prev => {
          const newStatus = new Map(prev);
          newStatus.delete(collectionId);
          return newStatus;
        });
      }, 3000);
    }
  };
  
  // Start re-indexing for a collection (for READY documents)
  const startReindexing = async (collectionId: number) => {
    // Clear any previous errors
    setError(null);
    
    // Add to reindexing set to show loading state
    setReindexingCollections(prev => new Set(prev).add(collectionId));
    
    try {
      const collection = collections.find(c => c.id === collectionId);
      if (!collection) {
        throw new Error('Collection not found');
      }
      
      console.log(`Starting reindex for collection ${collectionId}: ${collection.name}`);
      
      // Get collection details to find all document IDs
      let collectionDetails;
      try {
        collectionDetails = await apiService.getCollectionDetails(collectionId);
        console.log('Collection details:', collectionDetails);
      } catch (detailsError) {
        console.error('Failed to get collection details:', detailsError);
        throw new Error('Unable to fetch collection details. Please check your connection.');
      }
      
      // Check if documents exist
      if (!collectionDetails.documents || collectionDetails.documents.length === 0) {
        throw new Error('This collection has no documents to reindex');
      }
      
      // Look for documents that are indexed in this collection (collection_status = "INDEXED")
      const indexedDocumentIds = collectionDetails.documents
        .filter((doc: any) => doc.collection_status === 'INDEXED' || (doc.status === 'DOCUMENT_STORED' && doc.is_indexed_in_collection))
        .map((doc: any) => doc.id);
      
      console.log(`Found ${indexedDocumentIds.length} indexed documents out of ${collectionDetails.documents.length} total`);
      console.log('Documents details:', collectionDetails.documents.map(doc => ({
        id: doc.id,
        name: doc.file_name,
        status: doc.status,
        collection_status: doc.collection_status,
        is_indexed_in_collection: doc.is_indexed_in_collection
      })));
      
      if (indexedDocumentIds.length === 0) {
        throw new Error('No indexed documents found to reindex. Please index documents first.');
      }
      
      // Call the reindex endpoint with all indexed document IDs
      console.log(`Calling reindex API with ${indexedDocumentIds.length} document IDs`);
      let result;
      try {
        result = await apiService.reindexDocuments(collectionId, indexedDocumentIds);
        console.log('Reindex API response:', result);
      } catch (apiError: any) {
        console.error('Reindex API error:', apiError);
        if (apiError.response?.status === 400) {
          throw new Error('Invalid request. Please ensure documents are properly indexed.');
        } else if (apiError.response?.status === 404) {
          throw new Error('Collection or documents not found.');
        } else if (apiError.message) {
          throw new Error(apiError.message);
        } else {
          throw new Error('Failed to start reindexing. Please try again.');
        }
      }
      
      // Update local state to show indexing started
      setActiveJobs(prev => {
        const newJobs = new Map(prev);
        newJobs.set(collectionId, {
          jobId: result.job_id,
          collectionId,
          totalDocuments: result.total_documents,
          processedDocuments: 0,
          failedDocuments: 0,
          status: 'processing',
          progress: 0
        });
        return newJobs;
      });
      
      // Show success toast/notification
      console.log(`Successfully started reindexing ${result.total_documents} documents`);
    } catch (err) {
      console.error('Failed to start re-indexing:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      // Remove from reindexing set
      setReindexingCollections(prev => {
        const newSet = new Set(prev);
        newSet.delete(collectionId);
        return newSet;
      });
    }
  };
  
  // Cancel indexing for a collection
  const cancelIndexing = async (collectionId: number) => {
    const job = activeJobs.get(collectionId);
    if (!job) return;
    
    try {
      await apiService.cancelIndexingJob(job.jobId);
      
      // Remove from active jobs
      setActiveJobs(prev => {
        const newJobs = new Map(prev);
        newJobs.delete(collectionId);
        return newJobs;
      });
    } catch (err) {
      console.error('Failed to cancel indexing:', err);
      setError('Failed to cancel indexing. Please try again.');
    }
  };
  
  // Handle bulk indexing
  const handleBulkIndex = async () => {
    const collectionIds = Array.from(selectedCollections);
    
    for (const collectionId of collectionIds) {
      await startIndexing(collectionId);
    }
    
    // Clear selection
    setSelectedCollections(new Set());
  };
  
  // Refresh all collection statuses
  const refreshAllStatuses = async () => {
    await loadCollections();
    
    // Refresh active job statuses
    for (const [collectionId, job] of activeJobs) {
      try {
        const status = await apiService.getCollectionIndexingStatus(collectionId, job.jobId);
        setActiveJobs(prev => {
          const newJobs = new Map(prev);
          newJobs.set(collectionId, {
            ...job,
            processedDocuments: status.processed_documents,
            failedDocuments: status.failed_documents,
            progress: status.progress,
            status: status.status
          });
          return newJobs;
        });
      } catch (err) {
        console.error(`Failed to refresh status for collection ${collectionId}:`, err);
      }
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
        <span className="text-gray-600">Loading collections...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="page-title">DocXAI Collections</h1>
            <p className="text-blue-700 mt-1">
              Organize and manage document collections for focused searches and analysis
            </p>
          </div>
          <Button 
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
          >
            <Plus className="h-4 w-4" />
            Create Collection
          </Button>
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

        {/* Search Bar */}
        <Card className="mb-6 shadow-tech border-0">
          <CardContent className="p-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search collections by name or description..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 border-gray-200 focus:border-blue-400 transition-colors"
              />
            </div>
          </CardContent>
        </Card>

        {/* Collections Grid */}
        {filteredCollections.length === 0 ? (
          <Card className="shadow-tech border-0">
            <CardContent className="text-center p-12">
              <FolderOpen className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {searchTerm ? 'No collections found' : 'No collections yet'}
              </h3>
              <p className="text-gray-600 mb-6">
                {searchTerm 
                  ? 'Try adjusting your search terms'
                  : 'Create your first collection to organize documents'
                }
              </p>
              {!searchTerm && (
                <Button 
                  onClick={() => setIsCreateModalOpen(true)}
                  className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create Collection
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Bulk Actions Toolbar - Removed per user request */}
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {filteredCollections.map((collection) => {
                const isIndexing = activeJobs.has(collection.id);
                const job = activeJobs.get(collection.id);
                const isSelected = selectedCollections.has(collection.id);
                
                // Log for debugging
                if (collection.active_job_id || collection.indexing_status === 'processing' || collection.indexing_status === 'pending') {
                  console.log(`Collection ${collection.id} rendering:`, {
                    active_job_id: collection.active_job_id,
                    indexing_status: collection.indexing_status,
                    isIndexing,
                    job,
                    activeJobsSize: activeJobs.size
                  });
                }
                
                return (
                  <Card 
                    key={collection.id} 
                    className={`shadow-tech hover:shadow-tech-lg transition-all duration-300 border-0 ${isSelected ? 'ring-2 ring-blue-500' : ''} ${isIndexing ? 'bg-gradient-to-br from-blue-50 to-indigo-50' : 'bg-white'}`}
                  >
                    <CardHeader className="pb-4">
                      <CardTitle className="flex items-center justify-between">
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                          <span className="truncate cursor-pointer text-lg font-semibold text-gray-900 hover:text-blue-600 transition-colors" 
                                onClick={() => router.push(`/operations/collections/${collection.id}`)}>
                            {collection.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditModal(collection)}
                            disabled={isIndexing}
                            className="btn-professional-subtle hover:text-blue-600"
                          >
                            <Edit2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openDeleteModal(collection)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50 transition-colors"
                            disabled={isIndexing}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      {collection.description && (
                        <p className="text-sm text-gray-600 line-clamp-2 min-h-[2.5rem]">
                          {collection.description}
                        </p>
                      )}
                      
                      {/* Document counts badges */}
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline" className="text-xs px-2 py-0.5">
                          <FileText className="h-3 w-3 mr-1" />
                          {collection.document_count || 0} docs
                        </Badge>
                        {collection.indexed_count !== undefined && collection.indexed_count > 0 && (
                          <Badge variant="success" className="text-xs px-2 py-0.5">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            {collection.indexed_count} AI Ready
                          </Badge>
                        )}
                        {collection.pending_count !== undefined && collection.pending_count > 0 && (
                          <Badge variant="warning" className="text-xs px-2 py-0.5">
                            <Database className="h-3 w-3 mr-1" />
                            {collection.pending_count} pending
                          </Badge>
                        )}
                        {collection.stored_count !== undefined && collection.stored_count > 0 && (
                          <Badge variant="info" className="text-xs px-2 py-0.5">
                            <Database className="h-3 w-3 mr-1" />
                            {collection.stored_count} stored
                          </Badge>
                        )}
                      </div>
                      
                      
                      
                      {/* Action buttons */}
                      <div className="flex flex-wrap items-center gap-2 pt-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/operations/collections/${collection.id}`);
                          }}
                          className="btn-professional-subtle"
                        >
                          <Eye className="h-4 w-4 mr-2" />
                          View Documents
                        </Button>
                        
                        {/* Show In Progress button if job is running */}
                        {(collection.indexing_status === 'pending' || collection.indexing_status === 'processing') && (
                          <Button
                            size="sm"
                            disabled
                            className="bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-700 cursor-not-allowed"
                          >
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                            In Progress
                          </Button>
                        )}
                        
                        {/* Show Start Indexing button if there are pending or stored documents and no active job */}
                        {((collection.pending_count !== undefined && collection.pending_count > 0) || 
                          (collection.stored_count !== undefined && collection.stored_count > 0)) && 
                          collection.indexing_status !== 'pending' && 
                          collection.indexing_status !== 'processing' && (
                          <Button
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              startIndexing(collection.id);
                            }}
                            disabled={indexingStatus.get(collection.id) === 'processing'}
                            className="bg-gradient-to-r from-green-600 to-emerald-600 text-white hover:from-green-700 hover:to-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <Play className="h-4 w-4 mr-2" />
                            Make AI Ready
                          </Button>
                        )}
                        
                        
                        
                      </div>
                      
                      <div className="flex items-center justify-between text-xs text-gray-500 pt-3 border-t border-gray-100">
                        <div className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          <span>Created {new Date(collection.created_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          </>
        )}

        {/* Create Collection Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-lg shadow-2xl border-0">
              <CardHeader className="border-b">
                <CardTitle className="flex items-center justify-between text-xl font-semibold">
                  <span>Create New Collection</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsCreateModalOpen(false);
                      setCollectionForm({ name: '', description: '' });
                    }}
                    disabled={actionLoading.create}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block">
                    Collection Name *
                  </label>
                  <Input
                    className="mt-1.5"
                    value={collectionForm.name}
                    onChange={(e) => setCollectionForm({...collectionForm, name: e.target.value})}
                    placeholder="e.g., Cardiovascular Drugs, Q4 2024 Approvals"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 block">
                    Description
                  </label>
                  <Textarea
                    className="mt-1.5 resize-none"
                    value={collectionForm.description}
                    onChange={(e) => setCollectionForm({...collectionForm, description: e.target.value})}
                    placeholder="Brief description of this collection..."
                    rows={3}
                  />
                </div>

                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <Info className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="text-sm text-blue-800">
                      <p className="font-medium mb-1">What are collections?</p>
                      <p>Collections are AI-powered workspaces in DocXAI that let you group related documents for smarter search and analysis.</p>
                    </div>
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsCreateModalOpen(false);
                      setCollectionForm({ name: '', description: '' });
                    }}
                    disabled={actionLoading.create}
                    className="btn-professional-subtle"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleCreateCollection}
                    disabled={!collectionForm.name.trim() || actionLoading.create}
                    className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
                  >
                    {actionLoading.create ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Create Collection
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Edit Collection Modal */}
        {isEditModalOpen && selectedCollection && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-lg shadow-2xl border-0">
              <CardHeader className="border-b">
                <CardTitle className="flex items-center justify-between text-xl font-semibold">
                  <span>Edit Collection</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsEditModalOpen(false);
                      setSelectedCollection(null);
                      setCollectionForm({ name: '', description: '' });
                    }}
                    disabled={actionLoading.update}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="text-sm font-medium text-gray-700 block">
                    Collection Name *
                  </label>
                  <Input
                    className="mt-1.5"
                    value={collectionForm.name}
                    onChange={(e) => setCollectionForm({...collectionForm, name: e.target.value})}
                    placeholder="e.g., Cardiovascular Drugs, Q4 2024 Approvals"
                  />
                </div>

                <div>
                  <label className="text-sm font-medium text-gray-700 block">
                    Description
                  </label>
                  <Textarea
                    className="mt-1.5 resize-none"
                    value={collectionForm.description}
                    onChange={(e) => setCollectionForm({...collectionForm, description: e.target.value})}
                    placeholder="Brief description of this collection..."
                    rows={3}
                  />
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsEditModalOpen(false);
                      setSelectedCollection(null);
                      setCollectionForm({ name: '', description: '' });
                    }}
                    disabled={actionLoading.update}
                    className="btn-professional-subtle"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleUpdateCollection}
                    disabled={!collectionForm.name.trim() || actionLoading.update}
                    className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
                  >
                    {actionLoading.update ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    Save Changes
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Delete Collection Modal */}
        {isDeleteModalOpen && selectedCollection && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <Card className="w-full max-w-lg shadow-2xl border-0">
              <CardHeader className="pb-4 border-b">
                <CardTitle className="flex items-center justify-between text-xl font-semibold">
                  <span>Delete Collection</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      setIsDeleteModalOpen(false);
                      setSelectedCollection(null);
                      setDeleteSourceFiles(false);
                    }}
                    disabled={actionLoading.delete}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                    <div>
                      <p className="text-red-800 font-medium mb-1">
                        Are you sure you want to delete "{selectedCollection.name}"?
                      </p>
                      <p className="text-sm text-red-700">
                        This will remove the collection and all document associations from ChromaDB.
                      </p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
                  <label className="flex items-start gap-3 cursor-pointer">
                    <Checkbox
                      checked={deleteSourceFiles}
                      onCheckedChange={(checked) => setDeleteSourceFiles(checked as boolean)}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="font-medium text-gray-900">
                        Also delete source files
                      </p>
                      <p className="text-sm text-gray-600 mt-1">
                        This will permanently delete all document files associated with this collection from the server. 
                        This action cannot be undone.
                      </p>
                    </div>
                  </label>
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <Button
                    variant="outline"
                    onClick={() => {
                      setIsDeleteModalOpen(false);
                      setSelectedCollection(null);
                      setDeleteSourceFiles(false);
                    }}
                    disabled={actionLoading.delete}
                    className="btn-professional-subtle"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleDeleteCollection}
                    disabled={actionLoading.delete}
                    className="bg-red-600 hover:bg-red-700 text-white btn-professional"
                  >
                    {actionLoading.delete ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Trash2 className="h-4 w-4 mr-2" />
                    )}
                    Delete Collection
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