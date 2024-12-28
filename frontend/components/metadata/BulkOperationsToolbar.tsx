'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  Download,
  Upload,
  Trash2,
  ToggleLeft,
  ToggleRight,
  Edit,
  CheckSquare,
  Square,
  MoreHorizontal,
  FileSpreadsheet,
  Archive,
  RefreshCw,
  Copy,
  Eye,
  EyeOff
} from 'lucide-react';
import { ImportPreviewModal } from './ImportPreviewModal';
import { apiService } from '@/services/api';

interface BulkOperationsToolbarProps {
  selectedItems: number[];
  totalItems: number;
  onSelectAll: (selected: boolean) => void;
  onRefresh: () => void;
  onBulkAction: (action: string, items: number[]) => Promise<void>;
  isLoading?: boolean;
  className?: string;
}

export const BulkOperationsToolbar: React.FC<BulkOperationsToolbarProps> = ({
  selectedItems,
  totalItems,
  onSelectAll,
  onRefresh,
  onBulkAction,
  isLoading = false,
  className
}) => {
  const [isImportModalOpen, setIsImportModalOpen] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [bulkActionLoading, setBulkActionLoading] = useState<string | null>(null);

  const hasSelection = selectedItems.length > 0;
  const allSelected = selectedItems.length === totalItems && totalItems > 0;
  const indeterminate = hasSelection && !allSelected;

  const handleExport = async (type: 'all' | 'selected') => {
    setExportLoading(true);
    try {
      let blob: Blob;
      if (type === 'all') {
        blob = await apiService.exportMetadataConfigs();
      } else {
        blob = await apiService.exportMetadataConfigs(selectedItems);
      }
      
      // Create download link
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const timestamp = new Date().toISOString().split('T')[0];
      a.download = `metadata_configs_${type}_${timestamp}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
    } finally {
      setExportLoading(false);
    }
  };

  const handleBulkAction = async (action: string) => {
    setBulkActionLoading(action);
    try {
      await onBulkAction(action, selectedItems);
      // Clear selection after successful bulk action
      onSelectAll(false);
    } catch (error) {
      console.error(`Bulk action ${action} failed:`, error);
    } finally {
      setBulkActionLoading(null);
    }
  };

  const handleImportComplete = (result: any) => {
    setIsImportModalOpen(false);
    onRefresh(); // Refresh the list after import
  };

  return (
    <>
      <Card className={cn("border-0 shadow-sm", className)}>
        <CardContent className="p-4">
          <div className="flex items-center justify-between gap-4">
            {/* Selection Controls */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={allSelected}
                  indeterminate={indeterminate}
                  onCheckedChange={(checked) => onSelectAll(checked as boolean)}
                  disabled={isLoading || totalItems === 0}
                />
                <span className="text-sm text-gray-600">
                  {hasSelection ? (
                    <span className="font-medium">{selectedItems.length} selected</span>
                  ) : (
                    'Select all'
                  )}
                </span>
              </div>

              {hasSelection && (
                <>
                  <div className="h-6 w-px bg-gray-300" />
                  
                  {/* Bulk Actions */}
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleBulkAction('activate')}
                      disabled={bulkActionLoading !== null}
                      className="text-green-700 hover:bg-green-50 border-green-200"
                    >
                      {bulkActionLoading === 'activate' ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <ToggleRight className="h-4 w-4" />
                      )}
                      <span className="ml-2">Activate</span>
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleBulkAction('deactivate')}
                      disabled={bulkActionLoading !== null}
                      className="text-orange-700 hover:bg-orange-50 border-orange-200"
                    >
                      {bulkActionLoading === 'deactivate' ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <ToggleLeft className="h-4 w-4" />
                      )}
                      <span className="ml-2">Deactivate</span>
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleBulkAction('duplicate')}
                      disabled={bulkActionLoading !== null}
                      className="text-blue-700 hover:bg-blue-50 border-blue-200"
                    >
                      {bulkActionLoading === 'duplicate' ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                      <span className="ml-2">Duplicate</span>
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleBulkAction('delete')}
                      disabled={bulkActionLoading !== null}
                      className="text-red-700 hover:bg-red-50 border-red-200"
                    >
                      {bulkActionLoading === 'delete' ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                      <span className="ml-2">Delete</span>
                    </Button>
                  </div>

                  <div className="h-6 w-px bg-gray-300" />
                </>
              )}
            </div>

            {/* Import/Export Actions */}
            <div className="flex items-center gap-2">
              {/* Export Dropdown */}
              <Select onValueChange={handleExport} disabled={exportLoading}>
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder={
                    exportLoading ? (
                      <div className="flex items-center gap-2">
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        <span>Exporting...</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Download className="h-4 w-4" />
                        <span>Export</span>
                      </div>
                    )
                  } />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="h-4 w-4" />
                      <span>Export All</span>
                    </div>
                  </SelectItem>
                  <SelectItem 
                    value="selected" 
                    disabled={!hasSelection}
                  >
                    <div className="flex items-center gap-2">
                      <CheckSquare className="h-4 w-4" />
                      <span>Export Selected ({selectedItems.length})</span>
                    </div>
                  </SelectItem>
                </SelectContent>
              </Select>

              {/* Import Button */}
              <Button
                variant="outline"
                onClick={() => setIsImportModalOpen(true)}
                disabled={isLoading}
                className="border-blue-200 text-blue-700 hover:bg-blue-50"
              >
                <Upload className="h-4 w-4 mr-2" />
                Import
              </Button>

              {/* Refresh Button */}
              <Button
                variant="outline"
                size="icon"
                onClick={onRefresh}
                disabled={isLoading}
              >
                <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
              </Button>
            </div>
          </div>

          {/* Bulk Action Info */}
          {bulkActionLoading && (
            <div className="mt-3 flex items-center gap-2 text-sm text-gray-600">
              <RefreshCw className="h-3 w-3 animate-spin" />
              <span>Processing bulk action...</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Import Preview Modal */}
      <ImportPreviewModal
        isOpen={isImportModalOpen}
        onClose={() => setIsImportModalOpen(false)}
        onImportComplete={handleImportComplete}
      />
    </>
  );
};