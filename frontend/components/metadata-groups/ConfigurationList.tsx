'use client';

import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Edit2, 
  Trash2, 
  Copy, 
  MoreVertical,
  GripVertical,
  Eye,
  EyeOff,
  Tag
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';

interface MetadataConfig {
  id: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: string;
  is_active: boolean;
  is_in_group?: boolean;
  display_order?: number;
  groups?: string[];
}

interface ConfigurationListProps {
  configurations: MetadataConfig[];
  selectedConfigs: Set<number>;
  onSelectionChange: (id: number, selected: boolean) => void;
  onSelectAll: (selected: boolean) => void;
  onEdit: (config: MetadataConfig) => void;
  onClone: (config: MetadataConfig) => void;
  onDelete: (config: MetadataConfig) => void;
  onToggleActive: (config: MetadataConfig) => void;
  onAssignGroups: (config: MetadataConfig) => void;
  onReorder?: (configs: MetadataConfig[]) => void;
  loading?: Record<string, boolean>;
  viewMode?: 'card' | 'list';
  hideGroupCount?: boolean;
}

const dataTypeColors: Record<string, string> = {
  text: 'bg-gradient-to-r from-blue-100 to-blue-50 text-blue-800 border-blue-200',
  number: 'bg-gradient-to-r from-green-100 to-green-50 text-green-800 border-green-200',
  date: 'bg-gradient-to-r from-purple-100 to-purple-50 text-purple-800 border-purple-200',
  boolean: 'bg-gradient-to-r from-yellow-100 to-yellow-50 text-yellow-800 border-yellow-200',
};

const dataTypeIcons: Record<string, React.ReactNode> = {
  text: 'Aa',
  number: '#',
  date: '📅',
  boolean: '✓',
};

export const ConfigurationList: React.FC<ConfigurationListProps> = ({
  configurations,
  selectedConfigs,
  onSelectionChange,
  onSelectAll,
  onEdit,
  onClone,
  onDelete,
  onToggleActive,
  onAssignGroups,
  onReorder,
  loading = {},
  viewMode = 'card',
  hideGroupCount = false
}) => {
  const [draggedItem, setDraggedItem] = useState<number | null>(null);
  const [dragOverItem, setDragOverItem] = useState<number | null>(null);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedItem(index);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };
  
  const handleDragEnter = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverItem(index);
  };
  
  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    // Only clear if we're leaving the card entirely
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOverItem(null);
    }
  };

  const handleDrop = (e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (draggedItem === null || !onReorder) return;

    const draggedConfig = configurations[draggedItem];
    const newConfigs = [...configurations];
    
    // Remove dragged item
    newConfigs.splice(draggedItem, 1);
    
    // Insert at new position
    const adjustedDropIndex = dropIndex > draggedItem ? dropIndex - 1 : dropIndex;
    newConfigs.splice(adjustedDropIndex, 0, draggedConfig);
    
    // Update display orders
    const updatedConfigs = newConfigs.map((config, index) => ({
      ...config,
      display_order: index
    }));

    onReorder(updatedConfigs);
    setDraggedItem(null);
    setDragOverItem(null);
  };

  const allSelected = configurations.length > 0 && 
    configurations.every(config => selectedConfigs.has(config.id));
  const someSelected = configurations.some(config => selectedConfigs.has(config.id));

  if (viewMode === 'list') {
    return (
      <div className="space-y-3">
        {/* Enhanced Select All Header */}
        <div className="bg-gradient-to-r from-blue-50/50 to-indigo-50/50 border border-blue-200/50 rounded-lg p-4 mb-2">
          <div className="flex items-center gap-3">
            <Checkbox
              checked={allSelected}
              onCheckedChange={onSelectAll}
              className="border-gray-300 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
              aria-label="Select all configurations"
            />
            <span className="font-semibold text-gray-800">
              Select All
            </span>
            <Badge variant="secondary" className="bg-white/90 border-blue-200">
              {selectedConfigs.size} of {configurations.length} selected
            </Badge>
          </div>
        </div>

        {/* List container with same background as assigned fields */}
        <div className="bg-gradient-to-br from-blue-50/30 via-white/50 to-indigo-50/30 rounded-lg p-4 space-y-3">

          {configurations.map((config, index) => (
            <Card 
              key={config.id} 
              className={cn(
                "transition-all duration-300 hover:shadow-lg bg-white/95 backdrop-blur-sm border-gray-200",
                onReorder && "cursor-move hover:scale-[1.01]",
                selectedConfigs.has(config.id) && "ring-2 ring-blue-500 shadow-lg bg-blue-100/50 border-blue-200",
                draggedItem === index && "opacity-75 scale-105 shadow-xl ring-2 ring-blue-400",
                dragOverItem === index && draggedItem !== index && "border-t-4 border-blue-500",
                !config.is_active && "bg-gray-50/90 border-gray-300 opacity-80"
              )}
            draggable={!!onReorder}
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={handleDragOver}
            onDragEnter={(e) => handleDragEnter(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
          >
            <CardContent className="p-5">
              <div className="flex items-start gap-4">
                {onReorder && (
                  <div className="pt-1">
                    <GripVertical className={cn(
                      "h-5 w-5 cursor-move transition-colors duration-200 hover:text-blue-600",
                      config.is_active ? "text-gray-400" : "text-gray-300"
                    )} />
                  </div>
                )}
                
                <div className="pt-0.5">
                  <Checkbox
                    checked={selectedConfigs.has(config.id)}
                    onCheckedChange={(checked) => onSelectionChange(config.id, checked as boolean)}
                    className="border-gray-300 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                    aria-label={`Select ${config.metadata_name}`}
                  />
                </div>

                <div className="flex-1">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h4 className={cn(
                          "font-semibold text-lg",
                          config.is_active ? "text-gray-900" : "text-gray-500"
                        )}>
                          {config.metadata_name}
                        </h4>
                        <Badge 
                          variant="secondary" 
                          className={cn(
                            "text-xs font-medium px-2.5 py-0.5 border",
                            dataTypeColors[config.data_type] || "bg-gray-100 text-gray-800 border-gray-200",
                            !config.is_active && "opacity-60"
                          )}
                        >
                          <span className="mr-1">{dataTypeIcons[config.data_type] || '?'}</span>
                          {config.data_type}
                        </Badge>
                        {!config.is_active && (
                          <Badge variant="outline" className="text-gray-500 bg-gray-100/50 border-gray-300">
                            <EyeOff className="h-3 w-3 mr-1" />
                            Inactive
                          </Badge>
                        )}
                      </div>
                      
                      <p className={cn(
                        "text-sm mb-3 leading-relaxed",
                        config.is_active ? "text-gray-600" : "text-gray-400"
                      )}>
                        {config.description || <span className="italic">No description provided</span>}
                      </p>
                      
                      <div className={cn(
                        "flex items-center gap-4 text-xs pt-2 border-t",
                        config.is_active ? "text-gray-500 border-gray-100" : "text-gray-400 border-gray-100"
                      )}>
                        {!hideGroupCount && (
                          <span className="flex items-center gap-1.5 bg-gray-50 px-2 py-1 rounded">
                            <Tag className="h-3 w-3" />
                            <span className="font-medium">{config.groups?.length || 0}</span> {(config.groups?.length || 0) === 1 ? 'group' : 'groups'}
                          </span>
                        )}
                        <span className="flex-1 truncate italic opacity-80">
                          Prompt: "{config.extraction_prompt.substring(0, 60)}..."
                        </span>
                      </div>
                    </div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          className="h-8 w-8 p-0 hover:bg-gray-100 transition-colors duration-200"
                          disabled={loading[`action_${config.id}`]}
                        >
                          <MoreVertical className="h-4 w-4 text-gray-600" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-56 shadow-lg border-gray-200">
                        <DropdownMenuItem 
                          onClick={() => onEdit(config)}
                          className="hover:bg-blue-50 focus:bg-blue-50 cursor-pointer"
                        >
                          <Edit2 className="h-4 w-4 mr-2 text-blue-600" />
                          <span className="font-medium">Edit Configuration</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => onClone(config)}
                          className="hover:bg-purple-50 focus:bg-purple-50 cursor-pointer"
                        >
                          <Copy className="h-4 w-4 mr-2 text-purple-600" />
                          <span className="font-medium">Clone Configuration</span>
                        </DropdownMenuItem>
                        <DropdownMenuItem 
                          onClick={() => onAssignGroups(config)}
                          className="hover:bg-indigo-50 focus:bg-indigo-50 cursor-pointer"
                        >
                          <Tag className="h-4 w-4 mr-2 text-indigo-600" />
                          <span className="font-medium">Assign to Groups</span>
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="my-1" />
                        <DropdownMenuItem 
                          onClick={() => onToggleActive(config)}
                          className={cn(
                            "cursor-pointer",
                            config.is_active 
                              ? "hover:bg-orange-50 focus:bg-orange-50" 
                              : "hover:bg-green-50 focus:bg-green-50"
                          )}
                        >
                          {config.is_active ? (
                            <>
                              <EyeOff className="h-4 w-4 mr-2 text-orange-600" />
                              <span className="font-medium">Deactivate</span>
                            </>
                          ) : (
                            <>
                              <Eye className="h-4 w-4 mr-2 text-green-600" />
                              <span className="font-medium">Activate</span>
                            </>
                          )}
                        </DropdownMenuItem>
                        <DropdownMenuSeparator className="my-1" />
                        <DropdownMenuItem 
                          onClick={() => onDelete(config)}
                          className="text-red-600 hover:bg-red-50 focus:bg-red-50 cursor-pointer"
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          <span className="font-medium">Delete</span>
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        </div>
      </div>
    );
  }

  // Enhanced Card view
  return (
    <div className="space-y-4">
      {/* Enhanced Select All Header */}
      <div className="bg-gradient-to-r from-blue-50/50 to-indigo-50/50 border border-blue-200/50 rounded-lg p-4 mb-2">
        <div className="flex items-center gap-3">
          <Checkbox
            checked={allSelected}
            onCheckedChange={onSelectAll}
            className="border-gray-300 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
            aria-label="Select all configurations"
          />
          <span className="font-semibold text-gray-800">
            Select All
          </span>
          <Badge variant="secondary" className="bg-white/90 border-blue-200">
            {selectedConfigs.size} of {configurations.length} selected
          </Badge>
        </div>
      </div>

      {/* Grid container with same background as assigned fields */}
      <div className="bg-gradient-to-br from-blue-50/30 via-white/50 to-indigo-50/30 rounded-lg p-6">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {configurations.map((config) => (
            <Card 
              key={config.id}
              className={cn(
                "hover:shadow-lg transition-all duration-300 bg-white/95 backdrop-blur-sm border-gray-200 hover:scale-[1.01] group",
                selectedConfigs.has(config.id) && "ring-2 ring-blue-500 shadow-lg bg-blue-100/50 border-blue-200",
                !config.is_active && "bg-gray-50/90 border-gray-300 hover:shadow-md opacity-80"
              )}
          >
            <CardContent className="p-5">
              <div className="flex items-start justify-between mb-4">
                <Checkbox
                  checked={selectedConfigs.has(config.id)}
                  onCheckedChange={(checked) => onSelectionChange(config.id, checked as boolean)}
                  className="border-gray-300 data-[state=checked]:bg-blue-600 data-[state=checked]:border-blue-600"
                  aria-label={`Select ${config.metadata_name}`}
                />
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button 
                      variant="ghost" 
                      size="sm"
                      className="h-8 w-8 p-0 hover:bg-gray-100 transition-colors duration-200 opacity-0 group-hover:opacity-100"
                      disabled={loading[`action_${config.id}`]}
                    >
                      <MoreVertical className="h-4 w-4 text-gray-600" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 shadow-lg border-gray-200">
                    <DropdownMenuItem 
                      onClick={() => onEdit(config)}
                      className="hover:bg-blue-50 focus:bg-blue-50 cursor-pointer"
                    >
                      <Edit2 className="h-4 w-4 mr-2 text-blue-600" />
                      <span className="font-medium">Edit Configuration</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => onClone(config)}
                      className="hover:bg-purple-50 focus:bg-purple-50 cursor-pointer"
                    >
                      <Copy className="h-4 w-4 mr-2 text-purple-600" />
                      <span className="font-medium">Clone Configuration</span>
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => onAssignGroups(config)}
                      className="hover:bg-indigo-50 focus:bg-indigo-50 cursor-pointer"
                    >
                      <Tag className="h-4 w-4 mr-2 text-indigo-600" />
                      <span className="font-medium">Assign to Groups</span>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator className="my-1" />
                    <DropdownMenuItem 
                      onClick={() => onToggleActive(config)}
                      className={cn(
                        "cursor-pointer",
                        config.is_active 
                          ? "hover:bg-orange-50 focus:bg-orange-50" 
                          : "hover:bg-green-50 focus:bg-green-50"
                      )}
                    >
                      {config.is_active ? (
                        <>
                          <EyeOff className="h-4 w-4 mr-2 text-orange-600" />
                          <span className="font-medium">Deactivate</span>
                        </>
                      ) : (
                        <>
                          <Eye className="h-4 w-4 mr-2 text-green-600" />
                          <span className="font-medium">Activate</span>
                        </>
                      )}
                    </DropdownMenuItem>
                    <DropdownMenuSeparator className="my-1" />
                    <DropdownMenuItem 
                      onClick={() => onDelete(config)}
                      className="text-red-600 hover:bg-red-50 focus:bg-red-50 cursor-pointer"
                    >
                      <Trash2 className="h-4 w-4 mr-2" />
                      <span className="font-medium">Delete</span>
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              <h4 className={cn(
                "font-semibold text-lg mb-2",
                config.is_active ? "text-gray-900" : "text-gray-500"
              )}>
                {config.metadata_name}
              </h4>
              <p className={cn(
                "text-sm mb-4 line-clamp-2 leading-relaxed min-h-[2.5rem]",
                config.is_active ? "text-gray-600" : "text-gray-400"
              )}>
                {config.description || <span className="italic">No description provided</span>}
              </p>
              
              <div className="flex items-center justify-between pt-3 border-t border-gray-100">
                <Badge 
                  variant="secondary" 
                  className={cn(
                    "text-xs font-medium px-2.5 py-0.5 border",
                    dataTypeColors[config.data_type] || "bg-gray-100 text-gray-800 border-gray-200",
                    !config.is_active && "opacity-60"
                  )}
                >
                  <span className="mr-1">{dataTypeIcons[config.data_type] || '?'}</span>
                  {config.data_type}
                </Badge>
                <div className="flex items-center gap-2">
                  {!config.is_active && (
                    <Badge variant="outline" className="text-gray-500 text-xs bg-gray-100/50 border-gray-300">
                      <EyeOff className="h-3 w-3" />
                    </Badge>
                  )}
                  {!hideGroupCount && (
                    <Badge variant="outline" className="text-xs bg-gray-50 border-gray-200">
                      <Tag className="h-3 w-3 mr-1 text-gray-600" />
                      <span className="font-medium">{config.groups?.length || 0}</span>
                    </Badge>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
        </div>
      </div>
    </div>
  );
};