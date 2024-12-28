'use client';

import React, { useEffect, useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  FileSpreadsheet,
  RefreshCw
} from 'lucide-react';

interface ImportProgressProps {
  totalRows: number;
  processedRows: number;
  successCount: number;
  failedCount: number;
  skippedCount: number;
  currentItem?: string;
  status: 'preparing' | 'processing' | 'complete' | 'error';
  elapsedTime?: number;
}

export const ImportProgressTracker: React.FC<ImportProgressProps> = ({
  totalRows,
  processedRows,
  successCount,
  failedCount,
  skippedCount,
  currentItem,
  status,
  elapsedTime = 0
}) => {
  const [progress, setProgress] = useState(0);
  
  useEffect(() => {
    const newProgress = totalRows > 0 ? (processedRows / totalRows) * 100 : 0;
    setProgress(newProgress);
  }, [processedRows, totalRows]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'preparing':
        return <Clock className="h-5 w-5 text-blue-600 animate-pulse" />;
      case 'processing':
        return <RefreshCw className="h-5 w-5 text-blue-600 animate-spin" />;
      case 'complete':
        return <CheckCircle2 className="h-5 w-5 text-green-600" />;
      case 'error':
        return <XCircle className="h-5 w-5 text-red-600" />;
    }
  };

  const getStatusText = () => {
    switch (status) {
      case 'preparing':
        return 'Preparing import...';
      case 'processing':
        return `Processing row ${processedRows} of ${totalRows}`;
      case 'complete':
        return 'Import complete!';
      case 'error':
        return 'Import failed';
    }
  };

  const estimatedTimeRemaining = () => {
    if (processedRows === 0 || status !== 'processing') return null;
    const avgTimePerRow = elapsedTime / processedRows;
    const remainingRows = totalRows - processedRows;
    const estimatedSeconds = Math.ceil(avgTimePerRow * remainingRows);
    return formatTime(estimatedSeconds);
  };

  return (
    <Card className="w-full">
      <CardContent className="p-6 space-y-4">
        {/* Status Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {getStatusIcon()}
            <div>
              <h3 className="font-medium text-gray-900">{getStatusText()}</h3>
              {currentItem && status === 'processing' && (
                <p className="text-sm text-gray-600 mt-0.5">
                  Current: {currentItem}
                </p>
              )}
            </div>
          </div>
          
          <div className="text-right">
            <p className="text-sm text-gray-600">
              Elapsed: {formatTime(elapsedTime)}
            </p>
            {estimatedTimeRemaining() && (
              <p className="text-sm text-gray-500">
                Est. remaining: {estimatedTimeRemaining()}
              </p>
            )}
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600">Progress</span>
            <span className="font-medium">{Math.round(progress)}%</span>
          </div>
          <Progress 
            value={progress} 
            className={cn(
              "h-2 transition-all duration-300",
              status === 'error' && "bg-red-100"
            )}
          />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-3">
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <FileSpreadsheet className="h-5 w-5 text-blue-600 mx-auto mb-1" />
            <p className="text-sm font-medium text-blue-900">{totalRows}</p>
            <p className="text-xs text-blue-600">Total</p>
          </div>
          
          <div className="text-center p-3 bg-green-50 rounded-lg">
            <CheckCircle2 className="h-5 w-5 text-green-600 mx-auto mb-1" />
            <p className="text-sm font-medium text-green-900">{successCount}</p>
            <p className="text-xs text-green-600">Success</p>
          </div>
          
          <div className="text-center p-3 bg-yellow-50 rounded-lg">
            <AlertCircle className="h-5 w-5 text-yellow-600 mx-auto mb-1" />
            <p className="text-sm font-medium text-yellow-900">{skippedCount}</p>
            <p className="text-xs text-yellow-600">Skipped</p>
          </div>
          
          <div className="text-center p-3 bg-red-50 rounded-lg">
            <XCircle className="h-5 w-5 text-red-600 mx-auto mb-1" />
            <p className="text-sm font-medium text-red-900">{failedCount}</p>
            <p className="text-xs text-red-600">Failed</p>
          </div>
        </div>

        {/* Processing Rate */}
        {status === 'processing' && processedRows > 0 && (
          <div className="flex items-center justify-between text-sm text-gray-600 pt-2 border-t">
            <span>Processing rate:</span>
            <span className="font-medium">
              {(processedRows / (elapsedTime || 1)).toFixed(1)} rows/sec
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};