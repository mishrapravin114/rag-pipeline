// Minor update
"use client";

import React, { useState, useEffect } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { 
  Plus, 
  Search, 
  Settings, 
  Edit, 
  Trash2, 
  Eye, 
  EyeOff, 
  Save,
  X,
  Database,
  FileText,
  Filter,
  Download,
  Upload,
  AlertCircle,
  CheckCircle,
  Check
} from 'lucide-react';
import { apiService } from '../../../services/api';
import { BulkOperationsToolbar } from '@/components/metadata/BulkOperationsToolbar';
import { cn } from '@/lib/utils';

interface MetadataConfig {
  id: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  is_active: boolean;
  data_type: 'text' | 'number' | 'date' | 'boolean' | 'array';
  validation_rules?: string;
  created_by: number;
  created_at: string;
  updated_at: string;
}

interface NewMetadataConfig {
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: 'text' | 'number' | 'date' | 'boolean' | 'array';
  validation_rules: string;
  is_active: boolean;
}

const ConfigureMetadataPage = () => {
  const [configs, setConfigs] = useState<MetadataConfig[]>([]);
  const [filteredConfigs, setFilteredConfigs] = useState<MetadataConfig[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingConfig, setEditingConfig] = useState<MetadataConfig | null>(null);
  const [filterActive, setFilterActive] = useState<boolean | null>(null);
  const [selectedConfigs, setSelectedConfigs] = useState<number[]>([]);
  
  const [newConfig, setNewConfig] = useState<NewMetadataConfig>({
    metadata_name: '',
    description: '',
    extraction_prompt: '',
    data_type: 'text',
    validation_rules: '',
    is_active: true
  });

  // Export/Import state (now handled by BulkOperationsToolbar)
  const [importResult, setImportResult] = useState<any>(null);
  const [isImportResultModalOpen, setIsImportResultModalOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Delete confirmation state
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [configToDelete, setConfigToDelete] = useState<MetadataConfig | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const { user, token } = useAuth();

  // Load configurations on component mount
  useEffect(() => {
    loadConfigurations();
  }, []);

  // Clear messages after 5 seconds
  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  const loadConfigurations = async () => {
    try {
      setLoading(true);
      const data = await apiService.getAllMetadataConfigs();
      setConfigs(data);
    } catch (error) {
      console.error('Error loading configurations:', error);
      setError('Failed to load configurations');
    } finally {
      setLoading(false);
    }
  };

  // Filter configs based on search and active status
  useEffect(() => {
    let filtered = configs;

    if (searchTerm) {
      filtered = filtered.filter(config =>
        config.metadata_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        config.description.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    if (filterActive !== null) {
      filtered = filtered.filter(config => config.is_active === filterActive);
    }

    setFilteredConfigs(filtered);
  }, [configs, searchTerm, filterActive]);

  const handleCreateConfig = async () => {
    try {
      await apiService.createMetadataConfig(newConfig);
      setSuccess('Configuration created successfully');
      await loadConfigurations();
      setIsCreateModalOpen(false);
      setNewConfig({
        metadata_name: '',
        description: '',
        extraction_prompt: '',
        data_type: 'text',
        validation_rules: '',
        is_active: true
      });
    } catch (error: any) {
      setError(error.message || 'Failed to create configuration');
    }
  };

  const handleEditConfig = (config: MetadataConfig) => {
    setEditingConfig(config);
    setNewConfig({
      metadata_name: config.metadata_name,
      description: config.description,
      extraction_prompt: config.extraction_prompt,
      data_type: config.data_type,
      validation_rules: config.validation_rules || '',
      is_active: config.is_active
    });
  };

  const handleUpdateConfig = async () => {
    if (!editingConfig) return;

    try {
      await apiService.updateMetadataConfig(editingConfig.id, newConfig);
      setSuccess('Configuration updated successfully');
      await loadConfigurations();
      setEditingConfig(null);
      setNewConfig({
        metadata_name: '',
        description: '',
        extraction_prompt: '',
        data_type: 'text',
        validation_rules: '',
        is_active: true
      });
    } catch (error: any) {
      setError(error.message || 'Failed to update configuration');
    }
  };

  const handleDeleteConfig = async (id: number) => {
    try {
      setDeleteLoading(true);
      await apiService.deleteMetadataConfig(id);
      setSuccess('Configuration deleted successfully');
      await loadConfigurations();
      setConfigToDelete(null);
    } catch (error: any) {
      setError(error.message || 'Failed to delete configuration');
    } finally {
      setDeleteLoading(false);
    }
  };

  const toggleConfigStatus = async (id: number) => {
    const config = configs.find(c => c.id === id);
    if (!config) return;

    try {
      const updatedConfig = {
        metadata_name: config.metadata_name,
        description: config.description,
        extraction_prompt: config.extraction_prompt,
        data_type: config.data_type,
        validation_rules: config.validation_rules || '',
        is_active: !config.is_active
      };
      
      await apiService.updateMetadataConfig(id, updatedConfig);
      setSuccess(`Configuration ${updatedConfig.is_active ? 'activated' : 'deactivated'} successfully`);
      await loadConfigurations();
    } catch (error: any) {
      setError(error.message || 'Failed to update configuration status');
    }
  };

  const getDataTypeColor = (type: string) => {
    switch (type) {
      case 'text': return 'bg-blue-100 text-blue-800';
      case 'number': return 'bg-green-100 text-green-800';
      case 'date': return 'bg-purple-100 text-purple-800';
      case 'boolean': return 'bg-orange-100 text-orange-800';
      case 'array': return 'bg-pink-100 text-pink-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  // Selection handlers
  const handleSelectAll = (selected: boolean) => {
    if (selected) {
      setSelectedConfigs(filteredConfigs.map(c => c.id));
    } else {
      setSelectedConfigs([]);
    }
  };

  const handleSelectConfig = (configId: number) => {
    setSelectedConfigs(prev => {
      if (prev.includes(configId)) {
        return prev.filter(id => id !== configId);
      } else {
        return [...prev, configId];
      }
    });
  };

  // Bulk action handler
  const handleBulkAction = async (action: string, configIds: number[]) => {
    try {
      switch (action) {
        case 'activate':
          for (const id of configIds) {
            const config = configs.find(c => c.id === id);
            if (config && !config.is_active) {
              await apiService.updateMetadataConfig(id, { ...config, is_active: true });
            }
          }
          setSuccess(`Activated ${configIds.length} configuration(s)`);
          break;
          
        case 'deactivate':
          for (const id of configIds) {
            const config = configs.find(c => c.id === id);
            if (config && config.is_active) {
              await apiService.updateMetadataConfig(id, { ...config, is_active: false });
            }
          }
          setSuccess(`Deactivated ${configIds.length} configuration(s)`);
          break;
          
        case 'delete':
          for (const id of configIds) {
            await apiService.deleteMetadataConfig(id);
          }
          setSuccess(`Deleted ${configIds.length} configuration(s)`);
          break;
          
        case 'duplicate':
          for (const id of configIds) {
            const config = configs.find(c => c.id === id);
            if (config) {
              await apiService.createMetadataConfig({
                metadata_name: `${config.metadata_name} (Copy)`,
                description: config.description,
                extraction_prompt: config.extraction_prompt,
                data_type: config.data_type,
                validation_rules: config.validation_rules || '',
                is_active: false
              });
            }
          }
          setSuccess(`Duplicated ${configIds.length} configuration(s)`);
          break;
      }
      
      await loadConfigurations();
      setSelectedConfigs([]);
    } catch (error: any) {
      setError(error.message || `Failed to ${action} configurations`);
    }
  };

  // Handle import completion
  const handleImportComplete = (result: any) => {
    setImportResult(result);
    setIsImportResultModalOpen(true);
    
    // Reload configs if there were successful imports
    if (result.successful_imports > 0) {
      loadConfigurations();
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3"></div>
        <span className="text-gray-600">Loading configurations...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="page-title">Configure Metadata Details</h1>
            <p className="text-blue-700 mt-1">
              Manage metadata extraction configurations for pharmaceutical documents processing
            </p>
          </div>
        <Button 
          onClick={() => setIsCreateModalOpen(true)} 
          className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-indigo-600 text-white btn-professional"
        >
          <Plus className="h-4 w-4" />
          Add Configuration
        </Button>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3 mb-4">
          <Check className="h-5 w-5 text-green-600" />
          <span className="text-green-800">{success}</span>
          <button 
            onClick={() => setSuccess(null)}
            className="ml-auto text-green-600 hover:text-green-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3 mb-4">
          <AlertCircle className="h-5 w-5 text-red-600" />
          <span className="text-red-800">{error}</span>
          <button 
            onClick={() => setError(null)}
            className="ml-auto text-red-600 hover:text-red-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Bulk Operations Toolbar */}
      <BulkOperationsToolbar
        selectedItems={selectedConfigs}
        totalItems={configs.length}
        onSelectAll={handleSelectAll}
        onRefresh={loadConfigurations}
        onBulkAction={handleBulkAction}
        isLoading={loading}
        className="mb-4"
      />

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-blue-100 rounded-lg flex items-center justify-center">
                <Database className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Configs</p>
                <p className="text-2xl font-bold text-gray-900">{configs.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-green-100 rounded-lg flex items-center justify-center">
                <CheckCircle className="h-5 w-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Active</p>
                <p className="text-2xl font-bold text-gray-900">
                  {configs.filter(c => c.is_active).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 bg-red-100 rounded-lg flex items-center justify-center">
                <AlertCircle className="h-5 w-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">Inactive</p>
                <p className="text-2xl font-bold text-gray-900">
                  {configs.filter(c => !c.is_active).length}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search configurations by name or description..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-gray-500" />
              <Button
                variant={filterActive === null ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterActive(null)}
                className={filterActive === null ? "bg-blue-600 hover:bg-blue-700 text-white btn-professional-subtle" : "border-blue-200 text-blue-700 hover:bg-blue-50 btn-professional-subtle"}
              >
                All
              </Button>
              <Button
                variant={filterActive === true ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterActive(true)}
                className={filterActive === true ? "bg-blue-600 hover:bg-blue-700 text-white btn-professional-subtle" : "border-blue-200 text-blue-700 hover:bg-blue-50 btn-professional-subtle"}
              >
                Active
              </Button>
              <Button
                variant={filterActive === false ? "default" : "outline"}
                size="sm"
                onClick={() => setFilterActive(false)}
                className={filterActive === false ? "bg-blue-600 hover:bg-blue-700 text-white btn-professional-subtle" : "border-blue-200 text-blue-700 hover:bg-blue-50 btn-professional-subtle"}
              >
                Inactive
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configurations Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            Metadata Configurations ({filteredConfigs.length})
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {filteredConfigs.length === 0 ? (
            <div className="text-center p-8">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No configurations found</h3>
              <p className="text-gray-600">
                {searchTerm ? "Try adjusting your search terms" : "Get started by creating your first metadata configuration"}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="w-12 px-6 py-3">
                      <Checkbox
                        checked={selectedConfigs.length === filteredConfigs.length && filteredConfigs.length > 0}
                        indeterminate={selectedConfigs.length > 0 && selectedConfigs.length < filteredConfigs.length}
                        onCheckedChange={(checked) => handleSelectAll(checked as boolean)}
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Configuration
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Data Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Updated
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredConfigs.map((config) => (
                    <tr key={config.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Checkbox
                          checked={selectedConfigs.includes(config.id)}
                          onCheckedChange={() => handleSelectConfig(config.id)}
                        />
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {config.metadata_name}
                          </div>
                          <div className="text-sm text-gray-500 mt-1">
                            {config.description}
                          </div>
                          {config.validation_rules && (
                            <div className="text-xs text-gray-400 mt-1">
                              Rules: {config.validation_rules}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <Badge 
                          variant="secondary" 
                          className={`${getDataTypeColor(config.data_type)} border-0`}
                        >
                          {config.data_type}
                        </Badge>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={config.is_active}
                            onCheckedChange={() => toggleConfigStatus(config.id)}
                          />
                          <span className={`text-sm font-medium ${
                            config.is_active ? 'text-green-600' : 'text-gray-400'
                          }`}>
                            {config.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {new Date(config.updated_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEditConfig(config)}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setIsDeleteModalOpen(true);
                              setConfigToDelete(config);
                            }}
                            className="text-red-600 hover:text-red-700"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Modal */}
      {(isCreateModalOpen || editingConfig) && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{editingConfig ? 'Edit Configuration' : 'Create New Configuration'}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    setEditingConfig(null);
                    setNewConfig({
                      metadata_name: '',
                      description: '',
                      extraction_prompt: '',
                      data_type: 'text',
                      validation_rules: '',
                      is_active: true
                    });
                  }}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Metadata Name *
                </label>
                <Input
                  value={newConfig.metadata_name}
                  onChange={(e) => setNewConfig({...newConfig, metadata_name: e.target.value})}
                  placeholder="e.g., Drug Name, Manufacturer, Approval Date"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Description *
                </label>
                <Textarea
                  value={newConfig.description}
                  onChange={(e) => setNewConfig({...newConfig, description: e.target.value})}
                  placeholder="Describe what this metadata field captures..."
                  rows={3}
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Data Type *
                </label>
                <select
                  value={newConfig.data_type}
                  onChange={(e) => setNewConfig({...newConfig, data_type: e.target.value as any})}
                  className="w-full p-2 border border-gray-300 rounded-md"
                >
                  <option value="text">Text</option>
                  <option value="number">Number</option>
                  <option value="date">Date</option>
                  <option value="boolean">Boolean</option>
                  <option value="array">Array</option>
                </select>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Extraction Prompt *
                </label>
                <Textarea
                  value={newConfig.extraction_prompt}
                  onChange={(e) => setNewConfig({...newConfig, extraction_prompt: e.target.value})}
                  placeholder="Detailed prompt for AI to extract this metadata from documents..."
                  rows={4}
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Validation Rules
                </label>
                <Input
                  value={newConfig.validation_rules}
                  onChange={(e) => setNewConfig({...newConfig, validation_rules: e.target.value})}
                  placeholder="e.g., Required, Max length: 100, Valid date format"
                />
              </div>

              <div className="flex items-center gap-2">
                <Switch
                  checked={newConfig.is_active}
                  onCheckedChange={(checked) => setNewConfig({...newConfig, is_active: checked})}
                />
                <label className="text-sm font-medium text-gray-700">
                  Active (Enable this configuration)
                </label>
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsCreateModalOpen(false);
                    setEditingConfig(null);
                  }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={editingConfig ? handleUpdateConfig : handleCreateConfig}
                  disabled={!newConfig.metadata_name || !newConfig.description || !newConfig.extraction_prompt}
                  className="flex items-center gap-2"
                >
                  <Save className="h-4 w-4" />
                  {editingConfig ? 'Update' : 'Create'} Configuration
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="fixed top-4 right-4 z-50">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 max-w-md">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div>
                <h4 className="text-sm font-medium text-red-800">Error</h4>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setError(null)}
                className="text-red-600 hover:text-red-700"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </div>
      )}


      {/* Import Result Modal */}
      {isImportResultModalOpen && importResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-4xl max-h-[90vh] flex flex-col">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Import Results</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsImportResultModalOpen(false);
                    setImportResult(null);
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
                    <div className="text-2xl font-bold text-blue-600">{importResult.total_processed}</div>
                    <div className="text-sm text-blue-800">Total Processed</div>
                  </CardContent>
                </Card>
                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-green-600">{importResult.successful_imports}</div>
                    <div className="text-sm text-green-800">Successful</div>
                  </CardContent>
                </Card>
                <Card className="bg-red-50 border-red-200">
                  <CardContent className="p-4 text-center">
                    <div className="text-2xl font-bold text-red-600">{importResult.failed_imports}</div>
                    <div className="text-sm text-red-800">Failed</div>
                  </CardContent>
                </Card>
              </div>

              {/* Successful Imports */}
              {importResult.import_details.successful.length > 0 && (
                <div>
                  <h4 className="font-medium text-green-900 mb-3 flex items-center gap-2">
                    <CheckCircle className="h-5 w-5 text-green-600" />
                    Successfully Imported ({importResult.import_details.successful.length})
                  </h4>
                  <div className="space-y-2">
                    {importResult.import_details.successful.map((item: any) => (
                      <div key={item.row} className="bg-green-50 border border-green-200 rounded-lg p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <span className="font-medium text-green-900">Row {item.row}: {item.metadata_name}</span>
                            <span className="text-sm text-green-700 ml-2">({item.action})</span>
                          </div>
                          <div className="text-sm text-green-600">ID: {item.id}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Failed Imports */}
              {importResult.import_details.failed.length > 0 && (
                <div>
                  <h4 className="font-medium text-red-900 mb-3 flex items-center gap-2">
                    <AlertCircle className="h-5 w-5 text-red-600" />
                    Failed Imports ({importResult.import_details.failed.length})
                  </h4>
                  <div className="space-y-2">
                    {importResult.import_details.failed.map((item: any, index: number) => (
                      <div key={index} className="bg-red-50 border border-red-200 rounded-lg p-3">
                        <div className="mb-2">
                          <span className="font-medium text-red-900">Row {item.row}: {item.metadata_name}</span>
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
                    setIsImportResultModalOpen(false);
                    setImportResult(null);
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

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && configToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-2xl">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Confirm Deletion</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsDeleteModalOpen(false);
                    setConfigToDelete(null);
                  }}
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
                     <h4 className="text-sm font-medium text-red-800 mb-2">
                       Delete Configuration: "{configToDelete.metadata_name}"
                     </h4>
                     <div className="text-sm text-red-700 space-y-1">
                       <p><strong>Description:</strong> {configToDelete.description}</p>
                       <p><strong>Data Type:</strong> {configToDelete.data_type}</p>
                       <p><strong>Status:</strong> {configToDelete.is_active ? 'Active' : 'Inactive'}</p>
                     </div>
                     <p className="text-sm text-red-800 mt-3 font-medium">
                       ⚠️ This action cannot be undone. All associated data will be permanently removed.
                     </p>
                   </div>
                 </div>
               </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsDeleteModalOpen(false);
                    setConfigToDelete(null);
                  }}
                >
                  Cancel
                </Button>
                                 <Button
                   onClick={() => {
                     setIsDeleteModalOpen(false);
                     handleDeleteConfig(configToDelete.id);
                   }}
                   disabled={deleteLoading}
                   className="bg-red-600 hover:bg-red-700 text-white"
                 >
                   {deleteLoading ? (
                     <>
                       <div className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" />
                       Deleting...
                     </>
                   ) : (
                     'Delete'
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

export default ConfigureMetadataPage;