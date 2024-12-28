import { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '@/services/api';

interface IndexingProgress {
  jobId: string;
  collectionId: number;
  totalDocuments: number;
  processedDocuments: number;
  failedDocuments: number;
  currentDocument?: string;
  progress: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  documents: Array<{
    id: number;
    name: string;
    status: 'pending' | 'processing' | 'indexed' | 'failed';
    error?: string;
  }>;
}

export const useIndexingProgress = (collectionId: number, jobId?: string, enabled: boolean = true) => {
  const [progress, setProgress] = useState<IndexingProgress | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // Fetch job status
  const fetchJobStatus = useCallback(async () => {
    if (!jobId || !enabled) return;
    
    try {
      const status = await apiService.getIndexingStatus(collectionId, jobId);
      
      if (status) {
        // Map the API response to our progress interface
        const progressData: IndexingProgress = {
          jobId: status.job_id || jobId,
          collectionId: status.collection_id || collectionId,
          totalDocuments: status.total_documents || 0,
          processedDocuments: status.processed_documents || 0,
          failedDocuments: status.failed_documents || 0,
          currentDocument: status.current_document,
          progress: status.progress || (status.total_documents > 0 
            ? (status.processed_documents / status.total_documents * 100) 
            : 0),
          status: status.status || 'processing',
          documents: status.documents || []
        };
        
        setProgress(progressData);
        setError(null);
        
        // Stop polling if job is complete
        if (['completed', 'failed', 'cancelled'].includes(status.status)) {
          console.log('Job completed with status:', status.status);
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
            setIsPolling(false);
          }
        }
      }
    } catch (err) {
      console.error('Error fetching job status:', err);
      setError('Failed to fetch job status');
    }
  }, [collectionId, jobId, enabled]);
  
  // Set up polling
  useEffect(() => {
    if (!jobId || !enabled) {
      // Clear any existing interval
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setProgress(null);
      setIsPolling(false);
      setError(null);
      return;
    }
    
    // Fetch immediately
    fetchJobStatus();
    setIsPolling(true);
    
    // Set up polling interval (5 seconds)
    intervalRef.current = setInterval(() => {
      fetchJobStatus();
    }, 5000);
    
    // Cleanup on unmount or when dependencies change
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsPolling(false);
    };
  }, [jobId, collectionId, enabled, fetchJobStatus]);
  
  // Retry function to manually trigger a fetch
  const retry = useCallback(() => {
    setError(null);
    fetchJobStatus();
  }, [fetchJobStatus]);
  
  return {
    progress,
    isConnected: isPolling, // For backward compatibility
    error,
    retry
  };
};