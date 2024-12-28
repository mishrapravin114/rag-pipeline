// Minor update
'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { 
  Eye, 
  EyeOff, 
  Trash2, 
  Tag,
  Download,
  Upload,
  X,
  CheckCircle2
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

interface BulkOperationsToolbarProps {
  selectedCount: number;
  totalCount: number;
  onActivate: () => void;
  onDeactivate: () => void;
  onDelete: () => void;
  onAssignGroups: () => void;
  onExport: () => void;
  onImport: () => void;
  onClearSelection: () => void;
  disabled?: boolean;
  className?: string;
}

export const BulkOperationsToolbar: React.FC<BulkOperationsToolbarProps> = ({
  selectedCount,
  totalCount,
  onActivate,
  onDeactivate,
  onDelete,
  onAssignGroups,
  onExport,
  onImport,
  onClearSelection,
  disabled = false,
  className
}) => {
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);

  const handleDeleteClick = () => {
    if (showConfirmDelete) {
      onDelete();
      setShowConfirmDelete(false);
    } else {
      setShowConfirmDelete(true);
      setTimeout(() => setShowConfirmDelete(false), 3000); // Auto-cancel after 3 seconds
    }
  };

  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className={cn(
      "flex items-center justify-between p-5 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl shadow-md",
      "animate-in slide-in-from-top-2 duration-300",
      className
    )}>
      <div className="flex items-center gap-4">
        <Badge className="bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-800 border-blue-200 shadow-sm px-4 py-1.5">
          <CheckCircle2 className="h-4 w-4 mr-2" />
          <span className="font-semibold">{selectedCount}</span>
          <span className="text-blue-600 mx-1">of</span>
          <span className="font-semibold">{totalCount}</span>
          <span className="text-blue-600 ml-1">selected</span>
        </Badge>
        
        <div className="h-8 w-px bg-blue-200" />
        
        <div className="flex items-center gap-2">
          {/* Status Operations */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button 
                variant="outline" 
                size="sm" 
                disabled={disabled}
                className="bg-white/90 hover:bg-white border-blue-200 hover:border-blue-300 shadow-sm hover:shadow-md transition-all duration-200"
              >
                <Eye className="h-4 w-4 mr-2 text-blue-600" />
                <span className="font-medium">Status</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="shadow-lg border-gray-200">
              <DropdownMenuItem 
                onClick={onActivate}
                className="hover:bg-green-50 focus:bg-green-50"
              >
                <Eye className="h-4 w-4 mr-2 text-green-600" />
                <span className="font-medium">Activate Selected</span>
              </DropdownMenuItem>
              <DropdownMenuItem 
                onClick={onDeactivate}
                className="hover:bg-orange-50 focus:bg-orange-50"
              >
                <EyeOff className="h-4 w-4 mr-2 text-orange-600" />
                <span className="font-medium">Deactivate Selected</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Group Assignment */}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={onAssignGroups}
            disabled={disabled}
            className="bg-white/90 hover:bg-white border-blue-200 hover:border-blue-300 shadow-sm hover:shadow-md transition-all duration-200"
          >
            <Tag className="h-4 w-4 mr-2 text-blue-600" />
            <span className="font-medium">Assign Groups</span>
          </Button>

          {/* Export */}
          <Button 
            variant="outline" 
            size="sm" 
            onClick={onExport}
            disabled={disabled}
            className="bg-white/90 hover:bg-white border-blue-200 hover:border-blue-300 shadow-sm hover:shadow-md transition-all duration-200"
          >
            <Download className="h-4 w-4 mr-2 text-blue-600" />
            <span className="font-medium">Export</span>
          </Button>

          <div className="h-8 w-px bg-blue-200" />

          {/* Delete */}
          <Button 
            variant={showConfirmDelete ? "destructive" : "outline"}
            size="sm" 
            onClick={handleDeleteClick}
            disabled={disabled}
            className={cn(
              !showConfirmDelete && "bg-white/90 hover:bg-red-50 border-red-200 hover:border-red-300 hover:text-red-600 shadow-sm hover:shadow-md transition-all duration-200",
              showConfirmDelete && "shadow-lg animate-pulse"
            )}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            <span className="font-medium">{showConfirmDelete ? "Confirm Delete" : "Delete"}</span>
          </Button>
        </div>
      </div>

      {/* Clear Selection */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onClearSelection}
        className="text-gray-600 hover:text-gray-800 hover:bg-white/60 transition-all duration-200"
      >
        <X className="h-4 w-4 mr-1.5" />
        <span className="font-medium">Clear</span>
      </Button>
    </div>
  );
};