// Minor update
// Minor update
'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useRouter, useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  Search,
  Plus,
  Loader2,
  AlertCircle,
  LayoutGrid,
  List,
  Download,
  Upload,
  Filter,
  Database,
  FileText,
  Settings2,
  ChevronRight
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';
import { ConfigurationList } from '@/components/metadata-groups/ConfigurationList';
import { BulkOperationsToolbar } from '@/components/metadata-groups/BulkOperationsToolbar';
import { MultiGroupAssignmentModal } from '@/components/metadata-groups/MultiGroupAssignmentModal';
import { ConfigurationEditModal } from '@/components/metadata-groups/ConfigurationEditModal';
import { cn } from '@/lib/utils';

interface MetadataConfig {
  id: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: string;
  validation_rules: any;
  is_active: boolean;
  is_in_group?: boolean;
  display_order?: number;
  groups?: string[];
  group_count?: number;
}

interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  configuration_count: number;
  configurations?: Array<{
    id: number;
    metadata_name: string;
    description: string;
    extraction_prompt: string;
    extraction_prompt_version: number;
    data_type: string;
    validation_rules: any;
    is_active: boolean;
    display_order: number;
    created_at: string;
    updated_at: string;
    created_by: number;
  }>;
}

export default function ManageFieldsV2Page() {
  const { token, isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const groupId = useMemo(() => {
    const id = params.id as string;
    return id ? parseInt(id) : null;
  }, [params.id]);

  // State
  const [group, setGroup] = useState<MetadataGroup | null>(null);
  const [allGroups, setAllGroups] = useState<MetadataGroup[]>([]);
  const [groupConfigurations, setGroupConfigurations] = useState<MetadataConfig[]>([]);
  const [allConfigurations, setAllConfigurations] = useState<MetadataConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [activeTab, setActiveTab] = useState('group');
  const [viewMode, setViewMode] = useState<'card' | 'list'>('list');
  const [selectedConfigs, setSelectedConfigs] = useState<Set<number>>(new Set());
  
  // Modals
  const [isMultiGroupModalOpen, setIsMultiGroupModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<MetadataConfig | null>(null);
  const [editMode, setEditMode] = useState<'create' | 'edit' | 'clone'>('edit');
  const [singleConfigForAssignment, setSingleConfigForAssignment] = useState<MetadataConfig | null>(null);

  // Filtered configurations
  const filteredGroupConfigs = useMemo(() => {
    return groupConfigurations.filter(config =>
      config.metadata_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      config.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [groupConfigurations, searchTerm]);

  const filteredAllConfigs = useMemo(() => {
    return allConfigurations
      .filter(config =>
        config.metadata_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        config.description?.toLowerCase().includes(searchTerm.toLowerCase())
      )
      .sort((a, b) => a.metadata_name.localeCompare(b.metadata_name));
  }, [allConfigurations, searchTerm]);

  // Load initial data
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, authLoading, router]);

  useEffect(() => {
    if (isAuthenticated && token && groupId) {
      loadPageData();
    }
  }, [isAuthenticated, token, groupId]);

  const loadPageData = async () => {
    try {
      setLoading(true);
      
      // Load group details
      const groupData = await apiService.getMetadataGroup(groupId!, token);
      setGroup(groupData);
      
      // Load all groups for multi-group assignment
      const allGroupsResponse = await apiService.getMetadataGroups(1, 1000, '', token);
      setAllGroups(allGroupsResponse.groups || []);
      
      // Load configurations in this group
      const groupConfigIds = new Set(groupData.configurations?.map((config: any) => config.id) || []);
      const groupConfigs = groupData.configurations?.map((config: any) => ({
        id: config.id,
        metadata_name: config.metadata_name,
        description: config.description || '',
        extraction_prompt: config.extraction_prompt,
        data_type: config.data_type || 'text',
        validation_rules: config.validation_rules,
        is_active: config.is_active,
        is_in_group: true,
        display_order: config.display_order,
        groups: new Array(config.group_count || 1).fill('')
      })) || [];
      
      setGroupConfigurations(groupConfigs);
      
      // Load all configurations
      const allFieldsResponse = await apiService.getAllMetadataFields(1, 1000, '', token);
      const allConfigs = allFieldsResponse.fields.map((field: MetadataConfig) => ({
        ...field,
        is_in_group: groupConfigIds.has(field.id),
        groups: new Array(field.group_count || 0).fill('')
      }));
      
      setAllConfigurations(allConfigs);
      
    } catch (error) {
      console.error('Error loading page data:', error);
      toast({
        title: "Error",
        description: "Failed to load page data",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  // Selection handlers
  const handleSelectionChange = (id: number, selected: boolean) => {
    const newSelection = new Set(selectedConfigs);
    if (selected) {
      newSelection.add(id);
    } else {
      newSelection.delete(id);
    }
    setSelectedConfigs(newSelection);
  };

  const handleSelectAll = (selected: boolean) => {
    const configs = activeTab === 'group' ? filteredGroupConfigs : filteredAllConfigs;
    if (selected) {
      setSelectedConfigs(new Set(configs.map(c => c.id)));
    } else {
      setSelectedConfigs(new Set());
    }
  };

  // CRUD operations
  const handleCreate = () => {
    setEditingConfig(null);
    setEditMode('create');
    setIsEditModalOpen(true);
  };

  const handleEdit = (config: MetadataConfig) => {
    setEditingConfig(config);
    setEditMode('edit');
    setIsEditModalOpen(true);
  };

  const handleClone = (config: MetadataConfig) => {
    setEditingConfig(config);
    setEditMode('clone');
    setIsEditModalOpen(true);
  };

  const handleSaveConfig = async (config: MetadataConfig) => {
    try {
      if (editMode === 'create' || editMode === 'clone') {
        // Create new configuration
        const response = await apiService.createMetadataField({
          metadata_name: config.metadata_name,
          description: config.description,
          extraction_prompt: config.extraction_prompt,
          data_type: config.data_type,
          is_active: config.is_active
        }, token);
        
        // Add to current group
        await apiService.addMetadataToGroup(groupId!, {
          metadata_config_id: response.id,
          display_order: 0
        }, token);
        
        toast({
          title: "Success",
          description: `Configuration ${editMode === 'create' ? 'created' : 'cloned'} successfully`
        });
      } else {
        // Update existing configuration
        await apiService.updateMetadataField(config.id!, {
          metadata_name: config.metadata_name,
          description: config.description,
          extraction_prompt: config.extraction_prompt,
          data_type: config.data_type,
          is_active: config.is_active
        }, token);
        
        toast({
          title: "Success",
          description: "Configuration updated successfully"
        });
      }
      
      setIsEditModalOpen(false);
      loadPageData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to save configuration",
        variant: "destructive"
      });
    }
  };

  // Toggle individual configuration active status
  const handleToggleActive = async (config: MetadataConfig) => {
    try {
      const newActiveStatus = !config.is_active;
      await apiService.updateMetadataField(config.id, { is_active: newActiveStatus }, token);
      toast({
        title: "Success",
        description: `${newActiveStatus ? 'Activated' : 'Deactivated'} "${config.metadata_name}"`
      });
      loadPageData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || `Failed to ${config.is_active ? 'deactivate' : 'activate'} configuration`,
        variant: "destructive"
      });
    }
  };

  // Bulk operations
  const handleBulkActivate = async () => {
    const selectedIds = Array.from(selectedConfigs);
    for (const id of selectedIds) {
      try {
        await apiService.updateMetadataField(id, { is_active: true }, token);
      } catch (error) {
        console.error(`Failed to activate config ${id}`, error);
      }
    }
    toast({ title: "Success", description: `Activated ${selectedIds.length} configurations` });
    loadPageData();
    setSelectedConfigs(new Set());
  };

  const handleBulkDeactivate = async () => {
    const selectedIds = Array.from(selectedConfigs);
    for (const id of selectedIds) {
      try {
        await apiService.updateMetadataField(id, { is_active: false }, token);
      } catch (error) {
        console.error(`Failed to deactivate config ${id}`, error);
      }
    }
    toast({ title: "Success", description: `Deactivated ${selectedIds.length} configurations` });
    loadPageData();
    setSelectedConfigs(new Set());
  };

  const handleBulkDelete = async () => {
    const selectedIds = Array.from(selectedConfigs);
    for (const id of selectedIds) {
      try {
        await apiService.deleteMetadataField(id, token);
      } catch (error) {
        console.error(`Failed to delete config ${id}`, error);
      }
    }
    toast({ title: "Success", description: `Deleted ${selectedIds.length} configurations` });
    loadPageData();
    setSelectedConfigs(new Set());
  };

  const handleDeleteSingleConfig = async (config: MetadataConfig) => {
    try {
      await apiService.deleteMetadataField(config.id, token);
      toast({ 
        title: "Success", 
        description: `Deleted configuration "${config.metadata_name}"`
      });
      loadPageData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || `Failed to delete configuration "${config.metadata_name}"`,
        variant: "destructive"
      });
    }
  };

  const handleMultiGroupAssign = async (configIds: number[], groupIds: number[]) => {
    try {
      // For each group, bulk assign the configurations
      const assignmentPromises = groupIds.map(groupId => 
        apiService.bulkAssignConfigurationsToGroup(groupId, configIds, token)
      );
      
      // Wait for all assignments to complete
      const results = await Promise.allSettled(assignmentPromises);
      
      // Count successful assignments
      const successCount = results.filter(r => r.status === 'fulfilled').length;
      const failedCount = results.filter(r => r.status === 'rejected').length;
      
      if (failedCount > 0) {
        toast({
          title: "Partial Success",
          description: `Assigned to ${successCount} groups. Failed for ${failedCount} groups.`,
          variant: "warning"
        });
      } else {
        toast({
          title: "Success",
          description: `Successfully assigned ${configIds.length} configurations to ${groupIds.length} groups`
        });
      }
      
      setIsMultiGroupModalOpen(false);
      setSelectedConfigs(new Set());
      setSingleConfigForAssignment(null);
      loadPageData();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.message || "Failed to assign configurations to groups",
        variant: "destructive"
      });
    }
  };

  const handleAssignGroupsClick = (config?: MetadataConfig) => {
    if (config) {
      // Single config assignment from dropdown menu
      setSingleConfigForAssignment(config);
    } else {
      // Bulk assignment from toolbar
      setSingleConfigForAssignment(null);
    }
    setIsMultiGroupModalOpen(true);
  };

  const handleReorderConfigurations = async (reorderedConfigs: MetadataConfig[]) => {
    try {
      // Find the original positions to compare
      const originalOrderMap = new Map(groupConfigurations.map((config, index) => [config.id, index]));
      
      // Update local state immediately for responsive UI
      setGroupConfigurations(reorderedConfigs);
      
      // Make API calls to update the order for each configuration that moved
      const reorderPromises = reorderedConfigs.map(async (config, newIndex) => {
        const originalIndex = originalOrderMap.get(config.id);
        
        if (originalIndex !== undefined && originalIndex !== newIndex) {
          return apiService.reorderMetadataConfigurationInGroup(groupId!, config.id, newIndex, token);
        }
        return null;
      });
      
      // Wait for all reorder operations to complete (filter out null values)
      const validPromises = reorderPromises.filter(p => p !== null);
      const results = await Promise.allSettled(validPromises);
      
      // Check if any failed
      const failedCount = results.filter(r => r && r.status === 'rejected').length;
      
      if (failedCount > 0) {
        toast({
          title: "Warning",
          description: "Some configurations could not be reordered. Please refresh the page.",
          variant: "warning"
        });
        // Reload to ensure consistency
        loadPageData();
      } else {
        toast({
          title: "Success",
          description: "Configurations reordered successfully"
        });
      }
    } catch (error: any) {
      toast({
        title: "Error",
        description: "Failed to reorder configurations",
        variant: "destructive"
      });
      // Reload to restore correct order
      loadPageData();
    }
  };

  const handleExport = () => {
    // Implement export functionality
    toast({
      title: "Export Started",
      description: "Preparing Excel file for download..."
    });
  };

  const handleImport = () => {
    // Implement import functionality
    router.push(`/operations/metadata-groups/${groupId}/import`);
  };

  if (authLoading || !groupId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto" />
          <p className="mt-3 text-sm text-gray-500">Loading metadata configuration...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const displayedConfigs = activeTab === 'group' ? filteredGroupConfigs : filteredAllConfigs;
  const selectedConfigsArray = singleConfigForAssignment 
    ? [singleConfigForAssignment]
    : displayedConfigs.filter(c => selectedConfigs.has(c.id));

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 space-y-4">
        {/* Header Section - Modern and Compact */}
        <div className="space-y-3">
          {/* Breadcrumb Navigation */}
          <button
            onClick={() => router.push('/operations/metadata-groups')}
            className="inline-flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            <span>Groups</span>
          </button>
          
          {/* Modern Header */}
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                {group && (
                  <>
                    <h1 className="text-2xl font-semibold text-gray-900">
                      {group.name}
                    </h1>
                    <p className="text-sm text-gray-500">Manage metadata fields</p>
                    
                    <div className="flex items-center gap-4 pt-3">
                      <div className="flex items-center gap-1.5">
                        <Database className="h-4 w-4 text-gray-400" />
                        <span className="text-sm font-medium text-gray-900">{group.configuration_count}</span>
                        <span className="text-sm text-gray-500">fields</span>
                      </div>
                      
                      {group.description && (
                        <>
                          <span className="text-gray-300">•</span>
                          <span className="text-sm text-gray-600">{group.description}</span>
                        </>
                      )}
                    </div>
                  </>
                )}
              </div>
              
              <div className="flex items-center gap-2">
                <Button 
                  onClick={handleImport}
                  variant="outline"
                  size="sm"
                  className="border-gray-200 hover:bg-gray-50 text-gray-700"
                >
                  <Upload className="h-3.5 w-3.5 mr-1.5" />
                  Import
                </Button>
                <Button 
                  onClick={handleCreate} 
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700 text-white"
                >
                  <Plus className="h-3.5 w-3.5 mr-1.5" />
                  Add Field
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Bulk Operations - More Compact */}
        <BulkOperationsToolbar
          selectedCount={selectedConfigs.size}
          totalCount={displayedConfigs.length}
          onActivate={handleBulkActivate}
          onDeactivate={handleBulkDeactivate}
          onDelete={handleBulkDelete}
          onAssignGroups={() => handleAssignGroupsClick()}
          onExport={handleExport}
          onImport={handleImport}
          onClearSelection={() => setSelectedConfigs(new Set())}
        />

        {/* Search and View Controls - Modern Minimal Design */}
        <div className="flex flex-col sm:flex-row items-center gap-3 bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div className="relative flex-1 w-full">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search fields..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9 h-9 bg-gray-50 border-gray-200 focus:bg-white focus:border-blue-300 focus:ring-1 focus:ring-blue-200"
            />
          </div>
          
          <div className="flex items-center gap-2">
            {/* View Mode Toggle - Segmented Control Style */}
            <div className="flex items-center bg-gray-100 rounded-md p-0.5">
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded transition-colors",
                  viewMode === 'list' 
                    ? "bg-white text-blue-600 shadow-sm" 
                    : "text-gray-600 hover:text-gray-900"
                )}
              >
                <List className="h-3.5 w-3.5" />
                List
              </button>
              <button
                onClick={() => setViewMode('card')}
                className={cn(
                  "inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded transition-colors",
                  viewMode === 'card' 
                    ? "bg-white text-blue-600 shadow-sm" 
                    : "text-gray-600 hover:text-gray-900"
                )}
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                Grid
              </button>
            </div>
            
            <div className="h-5 w-px bg-gray-200" />
            
            <Button
              variant="ghost"
              size="sm"
              className="text-gray-600 hover:text-gray-900 hover:bg-gray-100"
            >
              <Filter className="h-3.5 w-3.5 mr-1.5" />
              Filters
            </Button>
          </div>
        </div>

        {/* Modern Tabs - Clean Underline Style */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm">
            <div className="flex space-x-0 p-1">
              <button
                onClick={() => setActiveTab('group')}
                className={cn(
                  "inline-flex items-center gap-2 py-2.5 px-4 text-sm font-medium transition-all rounded-md",
                  activeTab === 'group'
                    ? "bg-blue-100 text-blue-900 shadow-sm border border-blue-200"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                )}
              >
                <Database className="h-4 w-4" />
                Assigned Fields
                <span className={cn(
                  "inline-flex items-center justify-center px-2 py-0.5 text-xs font-medium rounded-full",
                  activeTab === 'group' ? "bg-blue-700 text-white" : "bg-gray-100 text-gray-600"
                )}>
                  {groupConfigurations.length}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('all')}
                className={cn(
                  "inline-flex items-center gap-2 py-2.5 px-4 text-sm font-medium transition-all rounded-md",
                  activeTab === 'all'
                    ? "bg-blue-100 text-blue-900 shadow-sm border border-blue-200"
                    : "text-gray-600 hover:text-gray-900 hover:bg-gray-50"
                )}
              >
                <FileText className="h-4 w-4" />
                Available Fields
                <span className={cn(
                  "inline-flex items-center justify-center px-2 py-0.5 text-xs font-medium rounded-full",
                  activeTab === 'all' ? "bg-blue-700 text-white" : "bg-gray-100 text-gray-600"
                )}>
                  {allConfigurations.length}
                </span>
              </button>
            </div>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-12 bg-white border border-gray-200 rounded-lg shadow-sm">
              <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
              <p className="mt-3 text-sm text-gray-500">Loading metadata fields...</p>
            </div>
          ) : (
            <>
              <TabsContent value="group" className="mt-4">
                <div className="bg-gradient-to-br from-blue-50/30 via-white to-indigo-50/30 p-6 rounded-lg border border-blue-100">
                  {filteredGroupConfigs.length === 0 ? (
                    <div className="text-center py-12 bg-white/80 backdrop-blur-sm border border-dashed border-gray-300 rounded-lg">
                      <Database className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                      <h3 className="text-base font-medium text-gray-900 mb-1">
                        {searchTerm ? 'No matching fields found' : 'No fields assigned yet'}
                      </h3>
                      <p className="text-sm text-gray-600 max-w-sm mx-auto mb-4">
                        {searchTerm 
                          ? 'Try adjusting your search criteria.' 
                          : 'Add metadata fields to define the data structure.'}
                      </p>
                      {!searchTerm && (
                        <Button 
                          size="sm"
                          className="bg-blue-600 hover:bg-blue-700 text-white" 
                          onClick={handleCreate}
                        >
                          <Plus className="h-3.5 w-3.5 mr-1.5" />
                          Create Field
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ConfigurationList
                      configurations={filteredGroupConfigs}
                      selectedConfigs={selectedConfigs}
                      onSelectionChange={handleSelectionChange}
                      onSelectAll={handleSelectAll}
                      onEdit={handleEdit}
                      onClone={handleClone}
                      onDelete={handleDeleteSingleConfig}
                      onToggleActive={handleToggleActive}
                      onAssignGroups={handleAssignGroupsClick}
                      onReorder={handleReorderConfigurations}
                      viewMode={viewMode}
                    />
                  )}
                </div>
              </TabsContent>

              <TabsContent value="all" className="mt-4">
                <div className="bg-gradient-to-br from-gray-50/50 via-white to-slate-50/50 p-6 rounded-lg border border-gray-200">
                  {filteredAllConfigs.length === 0 ? (
                    <div className="text-center py-12 bg-white/80 backdrop-blur-sm border border-dashed border-gray-300 rounded-lg">
                      <FileText className="h-10 w-10 text-gray-400 mx-auto mb-3" />
                      <h3 className="text-base font-medium text-gray-900 mb-1">
                        No available fields
                      </h3>
                      <p className="text-sm text-gray-600 max-w-sm mx-auto mb-4">
                        {searchTerm 
                          ? 'No fields match your search criteria.' 
                          : 'All fields are assigned. Create new ones to see them here.'}
                      </p>
                      {!searchTerm && (
                        <Button 
                          size="sm"
                          className="bg-blue-600 hover:bg-blue-700 text-white" 
                          onClick={handleCreate}
                        >
                          <Plus className="h-3.5 w-3.5 mr-1.5" />
                          Create Field
                        </Button>
                      )}
                    </div>
                  ) : (
                    <ConfigurationList
                      configurations={filteredAllConfigs}
                      selectedConfigs={selectedConfigs}
                      onSelectionChange={handleSelectionChange}
                      onSelectAll={handleSelectAll}
                      onEdit={handleEdit}
                      onClone={handleClone}
                      onDelete={handleDeleteSingleConfig}
                      onToggleActive={handleToggleActive}
                      onAssignGroups={handleAssignGroupsClick}
                      viewMode={viewMode}
                      onReorder={undefined} // Disable drag and drop for available fields
                      hideGroupCount={true} // Hide group count for available fields
                    />
                  )}
                </div>
              </TabsContent>
            </>
          )}
        </Tabs>

        {/* Modals */}
        <MultiGroupAssignmentModal
          isOpen={isMultiGroupModalOpen}
          onClose={() => {
            setIsMultiGroupModalOpen(false);
            setSingleConfigForAssignment(null);
          }}
          configurations={selectedConfigsArray}
          groups={allGroups}
          onAssign={handleMultiGroupAssign}
        />

        <ConfigurationEditModal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          configuration={editingConfig}
          onSave={handleSaveConfig}
          mode={editMode}
        />
      </div>
    </div>
  );
}