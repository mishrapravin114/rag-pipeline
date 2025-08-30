// Minor update
// Minor update
"use client";

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useAuth } from '@/hooks/useAuth';
import { useRouter, useParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  Search,
  Plus,
  Minus,
  Loader2,
  AlertCircle,
  Check
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';

interface MetadataConfig {
  id: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: string;
  validation_rules: any;
  is_in_group?: boolean;
  display_order?: number;
}

interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  metadata_count: number;
  items?: Array<{
    id: number;
    metadata_config_id: number;
    metadata_name: string;
    extraction_prompt: string;
    display_order: number;
  }>;
}

export default function ManageMetadataFieldsPage() {
  const { token, isAuthenticated, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const params = useParams();
  const groupId = useMemo(() => {
    const id = params.id as string;
    return id ? parseInt(id) : null;
  }, [params.id]);

  const [group, setGroup] = useState<MetadataGroup | null>(null);
  const [metadataFields, setMetadataFields] = useState<MetadataConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoadComplete, setInitialLoadComplete] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalFields, setTotalFields] = useState(0);
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({});
  const pageSize = 20;

  // Handle authentication redirect
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.push('/auth/login');
    }
  }, [isAuthenticated, authLoading, router]);

  // Debounce search term
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchTerm(searchTerm);
    }, 500);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Reset page when search changes
  useEffect(() => {
    if (initialLoadComplete && debouncedSearchTerm !== searchTerm) {
      setCurrentPage(1);
    }
  }, [debouncedSearchTerm, searchTerm, initialLoadComplete]);

  // Load page data
  const loadPageData = useCallback(async () => {
    if (!isAuthenticated || !token || !groupId || authLoading) {
      return;
    }

    try {
      setLoading(true);
      
      // Get group details first
      const groupData = await apiService.getMetadataGroup(groupId, token);
      setGroup(groupData);
      
      // Now get all metadata fields
      const allFieldsResponse = await apiService.getAllMetadataFields(
        currentPage,
        pageSize,
        debouncedSearchTerm,
        token
      );
      
      // Get fields already in the group from the group data
      const groupFieldsInGroup = groupData.items || [];
      const groupFieldIds = new Set(groupFieldsInGroup.map((item: any) => item.metadata_config_id));
      
      // Mark which fields are already in the group
      const fieldsWithGroupStatus = allFieldsResponse.fields.map((field: MetadataConfig) => ({
        ...field,
        is_in_group: groupFieldIds.has(field.id),
        display_order: groupFieldsInGroup.find((item: any) => item.metadata_config_id === field.id)?.display_order
      }));
      
      setMetadataFields(fieldsWithGroupStatus);
      setTotalFields(allFieldsResponse.total);
      setTotalPages(Math.ceil(allFieldsResponse.total / pageSize));
      setInitialLoadComplete(true);
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
  }, [isAuthenticated, token, groupId, currentPage, debouncedSearchTerm, authLoading]);

  // Load data when dependencies change
  useEffect(() => {
    loadPageData();
  }, [loadPageData]);

  const handleAddToGroup = useCallback(async (fieldId: number) => {
    if (!token) return;
    
    try {
      setActionLoading(prev => ({ ...prev, [`add_${fieldId}`]: true }));
      
      await apiService.addMetadataToGroup(groupId!, {
        metadata_config_id: fieldId,
        display_order: 0
      }, token);
      
      toast({
        title: "Success",
        description: "Metadata field added to group"
      });
      
      // Update local state
      setMetadataFields(prevFields => 
        prevFields.map(field => 
          field.id === fieldId ? { ...field, is_in_group: true } : field
        )
      );
      
      if (group) {
        setGroup(prev => prev ? { ...prev, metadata_count: prev.metadata_count + 1 } : null);
      }

    } catch (error) {
      console.error('Error adding metadata to group:', error);
      toast({
        title: "Error",
        description: "Failed to add metadata field to group",
        variant: "destructive"
      });
    } finally {
      setActionLoading(prev => ({ ...prev, [`add_${fieldId}`]: false }));
    }
  }, [token, groupId, group]);

  const handleRemoveFromGroup = useCallback(async (fieldId: number) => {
    if (!token) return;
    
    try {
      setActionLoading(prev => ({ ...prev, [`remove_${fieldId}`]: true }));
      
      await apiService.removeMetadataFromGroup(groupId!, fieldId, token);
      
      toast({
        title: "Success",
        description: "Metadata field removed from group"
      });
      
      // Update local state
      setMetadataFields(prevFields => 
        prevFields.map(field => 
          field.id === fieldId ? { ...field, is_in_group: false } : field
        )
      );
      
      if (group) {
        setGroup(prev => prev ? { ...prev, metadata_count: Math.max(0, prev.metadata_count - 1) } : null);
      }

    } catch (error) {
      console.error('Error removing metadata from group:', error);
      toast({
        title: "Error",
        description: "Failed to remove metadata field from group",
        variant: "destructive"
      });
    } finally {
      setActionLoading(prev => ({ ...prev, [`remove_${fieldId}`]: false }));
    }
  }, [token, groupId, group]);

  const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchTerm(e.target.value);
  }, []);

  // Show loading spinner during auth check
  if (authLoading || !groupId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  // Don't render anything if not authenticated (redirect will happen)
  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="max-w-7xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => router.push('/operations/metadata-groups')}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Groups
          </Button>
          <div>
            <h1 className="text-3xl font-bold">Manage Metadata Fields</h1>
            {group && (
              <p className="text-gray-600 mt-1">
                {group.name} - {group.metadata_count} fields assigned
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search metadata fields by name or description..."
              value={searchTerm}
              onChange={handleSearchChange}
              className="pl-10"
            />
          </div>
        </CardContent>
      </Card>

      {/* Metadata Fields List */}
      {loading && !initialLoadComplete ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : metadataFields.length === 0 ? (
        <Card>
          <CardContent className="p-12 text-center">
            <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">
              {debouncedSearchTerm ? 'No metadata fields found matching your search.' : 'No metadata fields available.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid gap-4">
            {metadataFields.map((field) => (
              <Card key={field.id} className={field.is_in_group ? 'border-green-200 bg-green-50' : ''}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <h3 className="font-semibold">{field.metadata_name}</h3>
                        <Badge variant="secondary">{field.data_type}</Badge>
                        {field.is_in_group && (
                          <Badge variant="default" className="bg-green-600">
                            <Check className="h-3 w-3 mr-1" />
                            Added
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-600 mb-2">{field.description}</p>
                      <p className="text-xs text-gray-500 italic">
                        Prompt: {field.extraction_prompt.substring(0, 100)}
                        {field.extraction_prompt.length > 100 && '...'}
                      </p>
                    </div>
                    <div className="ml-4">
                      {field.is_in_group ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleRemoveFromGroup(field.id)}
                          disabled={actionLoading[`remove_${field.id}`]}
                          className="flex items-center gap-2 text-red-600 hover:text-red-700"
                        >
                          {actionLoading[`remove_${field.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Minus className="h-4 w-4" />
                          )}
                          Remove
                        </Button>
                      ) : (
                        <Button
                          variant="default"
                          size="sm"
                          onClick={() => handleAddToGroup(field.id)}
                          disabled={actionLoading[`add_${field.id}`]}
                          className="flex items-center gap-2"
                        >
                          {actionLoading[`add_${field.id}`] ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Plus className="h-4 w-4" />
                          )}
                          Add
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-4 mt-6">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1 || loading}
              >
                Previous
              </Button>
              <span className="text-sm text-gray-600">
                Page {currentPage} of {totalPages} ({totalFields} total fields)
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(Math.min(totalPages, currentPage + 1))}
                disabled={currentPage === totalPages || loading}
              >
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}