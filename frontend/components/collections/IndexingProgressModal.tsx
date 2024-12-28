import { useState, useEffect, useCallback } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Pause, 
  Play,
  X,
  RotateCcw,
  AlertCircle
} from 'lucide-react';
import { apiService } from '@/services/api';
import { useIndexingProgress } from '@/hooks/useIndexingProgress';
import { cn } from '@/lib/utils';

interface IndexingProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  jobId: string;
  collectionId: number;
  collectionName: string;
}

interface DocumentProgress {
  id: number;
  name: string;
  status: 'pending' | 'processing' | 'indexed' | 'failed';
  error?: string;
  progress?: number;
}

export const IndexingProgressModal = ({ 
  isOpen, 
  onClose, 
  jobId, 
  collectionId,
  collectionName
}: IndexingProgressModalProps) => {
  const [isPaused, setIsPaused] = useState(false);
  const [documents, setDocuments] = useState<DocumentProgress[]>([]);
  const [retryingDocs, setRetryingDocs] = useState<Set<number>>(new Set());
  const { progress, isConnected, error, retry: retryConnection } = useIndexingProgress(collectionId, jobId, isOpen);
  
  // Remove auto-close functionality - let user close manually
  useEffect(() => {
    if (progress?.status && ['completed', 'failed', 'cancelled'].includes(progress.status)) {
      console.log('Job completed, status:', progress.status);
      // Don't auto-close - let user review results and close manually
    }
  }, [progress?.status]);
  
  // Update documents from progress data
  useEffect(() => {
    if (progress?.documents) {
      // Convert documents to the expected format
      const formattedDocs: DocumentProgress[] = progress.documents.map(doc => ({
        id: doc.id,
        name: doc.name,
        status: doc.status as DocumentProgress['status'],
        error: doc.error,
        progress: doc.status === 'processing' ? Math.floor((progress.processedDocuments / progress.totalDocuments) * 100) : undefined
      }));
      setDocuments(formattedDocs);
    }
  }, [progress]);
  
  // Update pause state from progress
  useEffect(() => {
    if (progress?.status === 'paused') {
      setIsPaused(true);
    } else if (progress?.status === 'processing') {
      setIsPaused(false);
    }
  }, [progress?.status]);
  
  const handlePause = async () => {
    try {
      await apiService.pauseIndexingJob(jobId);
      setIsPaused(true);
    } catch (error) {
      console.error('Failed to pause indexing:', error);
    }
  };
  
  const handleResume = async () => {
    try {
      await apiService.resumeIndexingJob(jobId);
      setIsPaused(false);
    } catch (error) {
      console.error('Failed to resume indexing:', error);
    }
  };
  
  const handleCancel = async () => {
    if (confirm('Are you sure you want to cancel the remaining documents?')) {
      try {
        await apiService.cancelIndexingJob(jobId);
        onClose();
      } catch (error) {
        console.error('Failed to cancel indexing:', error);
      }
    }
  };
  
  const handleRetryDocument = useCallback(async (documentId: number) => {
    setRetryingDocs(prev => new Set(prev).add(documentId));
    try {
      // For now, we'll simulate retry by updating local state
      // In a real implementation, this would call an API endpoint
      setDocuments(prev => prev.map(doc => 
        doc.id === documentId ? { ...doc, status: 'pending' as const } : doc
      ));
      
      // TODO: Implement actual retry API call when backend endpoint is available
      // await apiService.retryFailedDocument(jobId, documentId);
    } catch (error) {
      console.error('Failed to retry document:', error);
    } finally {
      setRetryingDocs(prev => {
        const next = new Set(prev);
        next.delete(documentId);
        return next;
      });
    }
  }, [jobId]);
  
  const handleRetryAllFailed = useCallback(async () => {
    const failedDocs = documents.filter(d => d.status === 'failed');
    if (failedDocs.length === 0) return;
    
    if (confirm(`Retry all ${failedDocs.length} failed documents?`)) {
      for (const doc of failedDocs) {
        await handleRetryDocument(doc.id);
      }
    }
  }, [documents, handleRetryDocument]);
  
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'processing':
        return <Loader2 className="h-4 w-4 animate-spin-smooth loading-spinner text-blue-600" />;
      case 'indexed':
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Clock className="h-4 w-4 text-gray-400" />;
    }
  };
  
  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'processing':
        return <Badge variant="default" className="bg-blue-600">Processing</Badge>;
      case 'indexed':
        return <Badge variant="success">Indexed</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'pending':
        return <Badge variant="secondary">Pending</Badge>;
      default:
        return null;
    }
  };
  
  const completedCount = documents.filter(d => d.status === 'indexed').length;
  const failedCount = documents.filter(d => d.status === 'failed').length;
  const pendingCount = documents.filter(d => d.status === 'pending').length;
  const processingCount = documents.filter(d => d.status === 'processing').length;
  
  const overallProgress = progress?.progress || 0;
  const isCompleted = progress?.status === 'completed';
  const isCancelled = progress?.status === 'cancelled';
  const isFailed = progress?.status === 'failed';
  
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center justify-between pr-6">
            <div>
              <span className="text-lg font-semibold">Indexing Documents</span>
              <p className="text-sm text-gray-600 font-normal mt-0.5">
                Collection: <span className="font-medium">{collectionName}</span>
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <div className="flex gap-2 text-sm">
                {completedCount > 0 && (
                  <Badge variant="success" className="flex items-center gap-1">
                    <CheckCircle className="h-3 w-3" />
                    {completedCount} completed
                  </Badge>
                )}
                {processingCount > 0 && (
                  <Badge variant="default" className="bg-blue-600 flex items-center gap-1">
                    <Loader2 className="h-3 w-3 animate-spin-smooth loading-spinner" />
                    {processingCount} processing
                  </Badge>
                )}
                {pendingCount > 0 && (
                  <Badge variant="secondary" className="flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {pendingCount} pending
                  </Badge>
                )}
                {failedCount > 0 && (
                  <Badge variant="destructive" className="flex items-center gap-1">
                    <XCircle className="h-3 w-3" />
                    {failedCount} failed
                  </Badge>
                )}
              </div>
              {isConnected && (
                <span className="text-xs text-green-600 flex items-center gap-1">
                  <div className="w-1.5 h-1.5 bg-green-600 rounded-full animate-pulse" />
                  Live updates
                </span>
              )}
            </div>
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6">
          {/* Completion message for completed jobs */}
          {progress?.status === 'completed' && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3 animate-fade-in">
              <CheckCircle className="h-6 w-6 text-green-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-semibold text-green-800">Indexing Completed Successfully!</p>
                <p className="text-xs text-green-700 mt-0.5">
                  All documents have been indexed. You can now close this window.
                </p>
              </div>
            </div>
          )}
          
          {/* Overall progress */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex justify-between mb-3">
              <div>
                <span className="text-sm font-semibold text-gray-900">Overall Progress</span>
                <p className="text-xs text-gray-500 mt-0.5">
                  {progress?.status === 'processing' ? 'Indexing documents...' : 
                   progress?.status === 'completed' ? 'Indexing completed' :
                   progress?.status === 'failed' ? 'Indexing failed' :
                   progress?.status === 'cancelled' ? 'Indexing cancelled' : 'Preparing...'}
                </p>
              </div>
              <div className="text-right">
                <span className="text-lg font-bold text-gray-900">
                  {overallProgress.toFixed(0)}%
                </span>
                <p className="text-xs text-gray-600">
                  {progress?.processedDocuments || 0} of {progress?.totalDocuments || 0}
                </p>
              </div>
            </div>
            <Progress value={overallProgress} className="h-4 mb-3" />
            {progress?.currentDocument && (
              <div className="flex items-center gap-2 bg-blue-50 rounded-md px-3 py-2 shadow-sm">
                <Loader2 className="h-4 w-4 animate-spin-smooth loading-spinner text-blue-600" />
                <p className="text-sm text-blue-800">
                  Processing: <span className="font-medium">{progress.currentDocument}</span>
                </p>
              </div>
            )}
          </div>
          
          {/* Error message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-start gap-2">
              <XCircle className="h-4 w-4 text-red-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-800">Error</p>
                <p className="text-xs text-red-700 mt-0.5">{error}</p>
              </div>
              <Button 
                variant="ghost" 
                size="sm" 
                onClick={retryConnection}
                className="h-7 px-2 text-red-700 hover:text-red-800"
              >
                <RotateCcw className="h-3 w-3" />
              </Button>
            </div>
          )}
          
          {/* Document list */}
          {documents.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-sm font-medium">Document Status</h4>
                {failedCount > 0 && (
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={handleRetryAllFailed}
                    className="text-xs"
                  >
                    <RotateCcw className="h-3 w-3 mr-1" />
                    Retry All Failed
                  </Button>
                )}
              </div>
              <ScrollArea className="h-[300px] border rounded-lg">
                <div className="p-4 space-y-2">
                  {documents.map((doc) => (
                    <div 
                      key={doc.id} 
                      className={cn(
                        "flex items-center justify-between p-3 rounded-lg transition-all duration-200 relative overflow-hidden",
                        {
                          'bg-blue-50 border border-blue-200 shadow-sm': doc.status === 'processing',
                          'bg-red-50 border border-red-200': doc.status === 'failed',
                          'bg-green-50 border border-green-200': doc.status === 'indexed',
                          'bg-gray-50 border border-gray-200': doc.status === 'pending'
                        }
                      )}
                    >
                      {/* Progress bar overlay for processing documents */}
                      {doc.status === 'processing' && (
                        <div className="absolute inset-0 pointer-events-none">
                          <div className="absolute inset-0 bg-blue-400 opacity-10 animate-pulse" />
                          <div 
                            className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-400/30 to-transparent transition-all duration-1000 ease-out"
                            style={{ width: `${doc.progress || 0}%` }}
                          />
                        </div>
                      )}
                      
                      <div className="flex items-center gap-3 flex-1 relative z-10">
                        {getStatusIcon(doc.status)}
                        <div className="flex-1">
                          <p className={cn(
                            "text-sm",
                            {
                              'font-semibold text-blue-700': doc.status === 'processing',
                              'text-red-700': doc.status === 'failed',
                              'text-green-700': doc.status === 'indexed',
                              'text-gray-600': doc.status === 'pending'
                            }
                          )}>
                            {doc.name}
                          </p>
                          {doc.error && (
                            <div className="flex items-start gap-1 mt-1">
                              <AlertCircle className="h-3 w-3 text-red-500 mt-0.5 flex-shrink-0" />
                              <p className="text-xs text-red-600">{doc.error}</p>
                            </div>
                          )}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-2 ml-4">
                        {doc.status === 'processing' && doc.progress && (
                          <div className="w-24">
                            <Progress value={doc.progress} className="h-2" />
                            <p className="text-xs text-gray-500 mt-1 text-center">{doc.progress}%</p>
                          </div>
                        )}
                        
                        {doc.status === 'indexed' && (
                          <span className="text-sm text-green-600 font-medium">Completed</span>
                        )}
                        
                        {doc.status === 'failed' && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRetryDocument(doc.id)}
                            disabled={retryingDocs.has(doc.id)}
                            className="h-7 px-2"
                          >
                            {retryingDocs.has(doc.id) ? (
                              <Loader2 className="h-3 w-3 animate-spin-smooth loading-spinner text-blue-600" />
                            ) : (
                              <>
                                <RotateCcw className="h-3 w-3 mr-1" />
                                Retry
                              </>
                            )}
                          </Button>
                        )}
                        
                        {doc.status === 'pending' && (
                          <span className="text-sm text-gray-500">Waiting...</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
          
          {/* Action buttons */}
          <div className="flex justify-between pt-4 border-t">
            <div className="flex gap-2">
              {/* Cancel button - show only when processing */}
              {progress?.status === 'processing' && (
                <Button 
                  variant="destructive" 
                  onClick={handleCancel}
                >
                  <X className="h-4 w-4 mr-2" />
                  Cancel Indexing
                </Button>
              )}
              
              {/* Retry connection button */}
              {!isConnected && error && (
                <Button variant="outline" size="sm" onClick={retryConnection}>
                  <RotateCcw className="h-4 w-4 mr-2" />
                  Retry Connection
                </Button>
              )}
            </div>
            
            <div className="flex items-center gap-3">
              {/* Status indicator */}
              <div className="flex items-center gap-2">
                {progress?.status === 'processing' && (
                  <span className="text-sm text-gray-600 flex items-center gap-2 font-medium">
                    <Loader2 className="h-4 w-4 animate-spin-smooth loading-spinner text-blue-600" />
                    Processing...
                  </span>
                )}
                {progress?.status === 'completed' && (
                  <span className="text-sm text-green-600 flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    Completed
                  </span>
                )}
                {progress?.status === 'failed' && (
                  <span className="text-sm text-red-600 flex items-center gap-2">
                    <XCircle className="h-4 w-4" />
                    Failed
                  </span>
                )}
                {progress?.status === 'cancelled' && (
                  <span className="text-sm text-gray-600 flex items-center gap-2">
                    <X className="h-4 w-4" />
                    Cancelled
                  </span>
                )}
              </div>
              
              {/* Close button - always enabled */}
              <Button 
                onClick={onClose} 
                variant={progress?.status === 'completed' ? 'default' : 'outline'}
                className={progress?.status === 'completed' ? 'animate-pulse' : ''}
              >
                {progress?.status === 'processing' ? 'Close' : 
                 progress?.status === 'completed' ? 'Close (Complete)' : 
                 progress?.status === 'failed' ? 'Close (Failed)' : 
                 progress?.status === 'cancelled' ? 'Close (Cancelled)' : 'Close'}
              </Button>
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};