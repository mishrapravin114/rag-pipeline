// Minor update
"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  Search, 
  Edit, 
  Trash2,
  Users,
  FileText,
  Settings,
  ChevronRight,
  Loader2,
  Info,
  Save,
  AlertCircle
} from 'lucide-react';
import { apiService } from '../../../services/api';
import { toast } from '@/components/ui/use-toast';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { GroupCard } from '@/components/metadata-groups';

interface MetadataGroupItem {
  id: number;
  metadata_config_id: number;
  metadata_name: string;
  extraction_prompt: string;
  display_order: number;
}

interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  created_by: number;
  configuration_count: number;
  items: MetadataGroupItem[];
  is_default?: boolean;
  color?: string;
  tags?: string[];
}

interface MetadataConfig {
  id: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  is_active: boolean;
}

const MetadataGroupsPage = () => {
  const [groups, setGroups] = useState<MetadataGroup[]>([]);
  const [filteredGroups, setFilteredGroups] = useState<MetadataGroup[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState<MetadataGroup | null>(null);
  
  const [newGroup, setNewGroup] = useState({
    name: '',
    description: '',
    color: 'gray',
    tags: ''
  });

  const [editingGroup, setEditingGroup] = useState({
    name: '',
    description: '',
    color: 'gray',
    tags: ''
  });

  const { user, token } = useAuth();

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    const filtered = groups.filter(group =>
      group.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      group.description?.toLowerCase().includes(searchTerm.toLowerCase())
    );
    setFilteredGroups(filtered);
  }, [searchTerm, groups]);

  const loadGroups = async () => {
    try {
      setLoading(true);
      const response = await apiService.getMetadataGroups(1, 1000, '', token);
      const groupsArray = Array.isArray(response) ? response : (response?.groups || []);
      setGroups(groupsArray);
      setFilteredGroups(groupsArray);
    } catch (error) {
      console.error('Error loading metadata groups:', error);
      toast({
        title: "Error",
        description: "Failed to load metadata groups",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGroup = async () => {
    if (!newGroup.name.trim()) {
      toast({
        title: "Validation Error",
        description: "Group name is required",
        variant: "destructive"
      });
      return;
    }

    try {
      await apiService.createMetadataGroup({
        name: newGroup.name,
        description: newGroup.description,
        color: newGroup.color,
        tags: newGroup.tags ? newGroup.tags.split(',').map(t => t.trim()).filter(t => t) : []
      }, token);

      toast({
        title: "Success",
        description: "Metadata group created successfully"
      });

      setIsCreateModalOpen(false);
      setNewGroup({ name: '', description: '', color: 'gray', tags: '' });
      loadGroups();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to create metadata group",
        variant: "destructive"
      });
    }
  };

  const handleUpdateGroup = async () => {
    if (!selectedGroup || !editingGroup.name.trim()) return;

    try {
      await apiService.updateMetadataGroup(selectedGroup.id, {
        name: editingGroup.name,
        description: editingGroup.description,
        color: editingGroup.color,
        tags: editingGroup.tags ? editingGroup.tags.split(',').map(t => t.trim()).filter(t => t) : []
      }, token);

      toast({
        title: "Success",
        description: "Metadata group updated successfully"
      });

      setIsEditModalOpen(false);
      setSelectedGroup(null);
      loadGroups();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to update metadata group",
        variant: "destructive"
      });
    }
  };

  const handleDeleteGroup = async () => {
    if (!selectedGroup) return;

    try {
      await apiService.deleteMetadataGroup(selectedGroup.id, token);

      toast({
        title: "Success",
        description: "Metadata group deleted successfully"
      });

      setIsDeleteModalOpen(false);
      setSelectedGroup(null);
      loadGroups();
    } catch (error: any) {
      toast({
        title: "Error",
        description: error.response?.data?.detail || "Failed to delete metadata group",
        variant: "destructive"
      });
    }
  };

  const openEditModal = (group: MetadataGroup) => {
    setSelectedGroup(group);
    setEditingGroup({
      name: group.name,
      description: group.description || '',
      color: group.color || 'gray',
      tags: group.tags?.join(', ') || ''
    });
    setIsEditModalOpen(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-purple-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="page-title">Metadata Groups</h1>
            <p className="text-purple-700 mt-1">
              Define and manage metadata extraction fields for your documents
            </p>
          </div>
          <Button 
            onClick={() => setIsCreateModalOpen(true)}
            className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white btn-professional"
          >
            <Plus className="h-4 w-4" />
            Create Group
          </Button>
        </div>

        {/* Search Bar */}
        <Card className="mb-6 shadow-tech border-0">
          <CardContent className="p-6">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
              <Input
                placeholder="Search groups by name, description, or tags..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10 border-gray-200 focus:border-purple-400 transition-colors"
              />
            </div>
          </CardContent>
        </Card>

        {/* Groups Grid */}
        {filteredGroups.length === 0 ? (
          <Card className="shadow-tech border-0">
            <CardContent className="text-center p-12">
              <Users className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">
                {searchTerm ? 'No groups found' : 'No metadata groups yet'}
              </h3>
              <p className="text-gray-600 mb-6">
                {searchTerm 
                  ? 'Try adjusting your search terms'
                  : 'Create your first metadata group to define extraction fields'
                }
              </p>
              {!searchTerm && (
                <Button 
                  onClick={() => setIsCreateModalOpen(true)}
                  className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white btn-professional"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Create Group
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 auto-rows-fr">
            {filteredGroups.map((group) => (
              <GroupCard
                key={group.id}
                group={group}
                onEdit={openEditModal}
                onDelete={(g) => {
                  setSelectedGroup(g);
                  setIsDeleteModalOpen(true);
                }}
                className="shadow-tech hover:shadow-tech-lg transition-all duration-300 h-full"
              />
            ))}
          </div>
        )}

        {/* Create Metadata Group Modal */}
        <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="text-xl font-semibold">Create Metadata Group</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="name" className="text-sm font-medium text-gray-700">Group Name *</Label>
              <Input
                id="name"
                placeholder="e.g., Safety Information, Clinical Data"
                className="mt-1.5"
                value={newGroup.name}
                onChange={(e) => setNewGroup({ ...newGroup, name: e.target.value })}
              />
            </div>
              <div>
                <Label htmlFor="description" className="text-sm font-medium text-gray-700">Description</Label>
              <Textarea
                id="description"
                placeholder="Describe the purpose of this metadata group..."
                className="mt-1.5 resize-none"
                value={newGroup.description}
                onChange={(e) => setNewGroup({ ...newGroup, description: e.target.value })}
                rows={3}
              />
            </div>
              <div>
                <Label htmlFor="color" className="text-sm font-medium text-gray-700">Color Theme</Label>
              <Select
                value={newGroup.color}
                onValueChange={(value) => setNewGroup({ ...newGroup, color: value })}
              >
                <SelectTrigger id="color" className="mt-1.5">
                  <SelectValue placeholder="Select a color" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="blue">Blue</SelectItem>
                  <SelectItem value="green">Green</SelectItem>
                  <SelectItem value="purple">Purple</SelectItem>
                  <SelectItem value="yellow">Yellow</SelectItem>
                  <SelectItem value="red">Red</SelectItem>
                  <SelectItem value="gray">Gray</SelectItem>
                </SelectContent>
              </Select>
            </div>
              <div>
                <Label htmlFor="tags" className="text-sm font-medium text-gray-700">Tags (comma-separated)</Label>
              <Input
                id="tags"
                placeholder="e.g., clinical, safety, regulatory"
                className="mt-1.5"
                value={newGroup.tags}
                onChange={(e) => setNewGroup({ ...newGroup, tags: e.target.value })}
              />
              <p className="text-xs text-gray-500 mt-1.5">Add tags to help categorize this group</p>
            </div>
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <Info className="h-5 w-5 text-purple-600 mt-0.5" />
                <div className="text-sm text-purple-800">
                  <p className="font-medium mb-1">What are metadata groups?</p>
                  <p>Metadata groups define sets of fields to extract from your documents using AI, enabling structured data analysis.</p>
                </div>
              </div>
            </div>
          </div>
          <DialogFooter className="gap-3">
            <Button 
              variant="outline" 
              onClick={() => setIsCreateModalOpen(false)}
              className="btn-professional-subtle"
            >
              Cancel
            </Button>
            <Button 
              onClick={handleCreateGroup}
              disabled={!newGroup.name.trim()}
              className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white btn-professional"
            >
              <Plus className="h-4 w-4 mr-2" />
              Create Group
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

        {/* Edit Metadata Group Modal */}
        <Dialog open={isEditModalOpen} onOpenChange={setIsEditModalOpen}>
          <DialogContent className="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle className="text-xl font-semibold">Edit Metadata Group</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label htmlFor="edit-name" className="text-sm font-medium text-gray-700">Group Name *</Label>
              <Input
                id="edit-name"
                className="mt-1.5"
                value={editingGroup.name}
                onChange={(e) => setEditingGroup({ ...editingGroup, name: e.target.value })}
              />
            </div>
              <div>
                <Label htmlFor="edit-description" className="text-sm font-medium text-gray-700">Description</Label>
                <Textarea
                  id="edit-description"
                  className="mt-1.5 resize-none"
                  value={editingGroup.description}
                onChange={(e) => setEditingGroup({ ...editingGroup, description: e.target.value })}
                rows={3}
              />
            </div>
              <div>
                <Label htmlFor="edit-color" className="text-sm font-medium text-gray-700">Color Theme</Label>
                <Select
                value={editingGroup.color}
                onValueChange={(value) => setEditingGroup({ ...editingGroup, color: value })}
              >
                  <SelectTrigger id="edit-color" className="mt-1.5">
                  <SelectValue placeholder="Select a color" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="blue">Blue</SelectItem>
                  <SelectItem value="green">Green</SelectItem>
                  <SelectItem value="purple">Purple</SelectItem>
                  <SelectItem value="yellow">Yellow</SelectItem>
                  <SelectItem value="red">Red</SelectItem>
                  <SelectItem value="gray">Gray</SelectItem>
                </SelectContent>
              </Select>
            </div>
              <div>
                <Label htmlFor="edit-tags" className="text-sm font-medium text-gray-700">Tags (comma-separated)</Label>
                <Input
                id="edit-tags"
                placeholder="e.g., clinical, safety, regulatory"
                className="mt-1.5"
                value={editingGroup.tags}
                onChange={(e) => setEditingGroup({ ...editingGroup, tags: e.target.value })}
              />
                <p className="text-xs text-gray-500 mt-1.5">Add tags to help categorize this group</p>
              </div>
            </div>
            <DialogFooter className="gap-3">
              <Button 
                variant="outline" 
                onClick={() => setIsEditModalOpen(false)}
                className="btn-professional-subtle"
              >
                Cancel
              </Button>
              <Button 
                onClick={handleUpdateGroup}
                disabled={!editingGroup.name.trim()}
                className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white btn-professional"
              >
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

        {/* Delete Metadata Group Modal */}
        <AlertDialog open={isDeleteModalOpen} onOpenChange={setIsDeleteModalOpen}>
          <AlertDialogContent className="sm:max-w-[500px]">
            <AlertDialogHeader>
              <AlertDialogTitle className="text-xl font-semibold">Delete Metadata Group</AlertDialogTitle>
              <AlertDialogDescription asChild>
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mt-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                    <div>
                      <p className="text-red-800 font-medium mb-1">
                        Are you sure you want to delete "{selectedGroup?.name}"?
                      </p>
                      <p className="text-sm text-red-700">
                        This action cannot be undone. Existing extracted metadata will not be affected.
                      </p>
                    </div>
                  </div>
                </div>
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter className="gap-3">
              <AlertDialogCancel className="btn-professional-subtle">Cancel</AlertDialogCancel>
              <AlertDialogAction 
                onClick={handleDeleteGroup}
                className="bg-red-600 hover:bg-red-700 text-white btn-professional"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete Group
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    </div>
  );
};

export default MetadataGroupsPage;