'use client';

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { 
  Search, 
  Loader2, 
  Users,
  Check,
  X
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  metadata_count: number;
  color?: string;
  is_default?: boolean;
}

interface MetadataConfig {
  id: number;
  metadata_name: string;
  groups?: number[];
}

interface MultiGroupAssignmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  configurations: MetadataConfig[];
  groups: MetadataGroup[];
  onAssign: (configIds: number[], groupIds: number[]) => Promise<void>;
  loading?: boolean;
}

export const MultiGroupAssignmentModal: React.FC<MultiGroupAssignmentModalProps> = ({
  isOpen,
  onClose,
  configurations,
  groups,
  onAssign,
  loading = false
}) => {
  const [selectedGroups, setSelectedGroups] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [isAssigning, setIsAssigning] = useState(false);

  const filteredGroups = groups.filter(group =>
    group.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    group.description?.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Initialize selected groups based on common groups across all configurations
  useEffect(() => {
    if (!configurations.length || !groups.length) return;

    // Find groups that ALL selected configurations belong to
    const commonGroups = groups.filter(group => 
      configurations.every(config => 
        config.groups?.includes(group.id)
      )
    );

    setSelectedGroups(new Set(commonGroups.map(g => g.id)));
  }, [configurations, groups]);

  const handleGroupToggle = (groupId: number, checked: boolean) => {
    const newSelectedGroups = new Set(selectedGroups);
    if (checked) {
      newSelectedGroups.add(groupId);
    } else {
      newSelectedGroups.delete(groupId);
    }
    setSelectedGroups(newSelectedGroups);
  };

  const handleAssign = async () => {
    if (selectedGroups.size === 0) {
      // Ensure at least one group is selected
      const defaultGroup = groups.find(g => g.is_default);
      if (defaultGroup) {
        setSelectedGroups(new Set([defaultGroup.id]));
        return;
      }
    }

    setIsAssigning(true);
    try {
      await onAssign(
        configurations.map(c => c.id),
        Array.from(selectedGroups)
      );
      onClose();
    } finally {
      setIsAssigning(false);
    }
  };

  const getGroupStatus = (groupId: number) => {
    const belongingConfigs = configurations.filter(config => 
      config.groups?.includes(groupId)
    );
    
    if (belongingConfigs.length === 0) return 'none';
    if (belongingConfigs.length === configurations.length) return 'all';
    return 'partial';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Assign to Groups</DialogTitle>
          <p className="text-sm text-gray-600 mt-2">
            Assigning {configurations.length} configuration{configurations.length > 1 ? 's' : ''} to groups.
            Each configuration must belong to at least one group.
          </p>
        </DialogHeader>

        <div className="space-y-4">
          {/* Selected configurations preview */}
          <div className="bg-gray-50 p-3 rounded-lg">
            <p className="text-xs font-medium text-gray-700 mb-2">Selected Configurations:</p>
            <div className="flex flex-wrap gap-2">
              {configurations.slice(0, 5).map(config => (
                <Badge key={config.id} variant="secondary" className="text-xs">
                  {config.metadata_name}
                </Badge>
              ))}
              {configurations.length > 5 && (
                <Badge variant="outline" className="text-xs">
                  +{configurations.length - 5} more
                </Badge>
              )}
            </div>
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <Input
              placeholder="Search groups..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Groups list */}
          <ScrollArea className="h-[300px] border rounded-lg p-4">
            {loading ? (
              <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin" />
              </div>
            ) : filteredGroups.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-500">
                <Users className="h-12 w-12 mb-2" />
                <p>No groups found</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredGroups.map(group => {
                  const status = getGroupStatus(group.id);
                  const isSelected = selectedGroups.has(group.id);

                  return (
                    <div
                      key={group.id}
                      className={cn(
                        "flex items-start space-x-3 p-3 rounded-lg border transition-colors",
                        isSelected && "bg-blue-50 border-blue-200",
                        !isSelected && "hover:bg-gray-50"
                      )}
                    >
                      <Checkbox
                        id={`group-${group.id}`}
                        checked={isSelected}
                        onCheckedChange={(checked) => handleGroupToggle(group.id, checked as boolean)}
                        disabled={group.is_default && selectedGroups.size === 1 && isSelected}
                      />
                      <label 
                        htmlFor={`group-${group.id}`} 
                        className="flex-1 cursor-pointer space-y-1"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{group.name}</span>
                          {group.is_default && (
                            <Badge variant="outline" className="text-xs">
                              Default
                            </Badge>
                          )}
                          {status === 'all' && (
                            <Badge variant="secondary" className="text-xs bg-green-100 text-green-800">
                              <Check className="h-3 w-3 mr-1" />
                              All included
                            </Badge>
                          )}
                          {status === 'partial' && (
                            <Badge variant="secondary" className="text-xs bg-yellow-100 text-yellow-800">
                              Partially included
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-gray-600">{group.description}</p>
                        <p className="text-xs text-gray-500">{group.metadata_count} configurations</p>
                      </label>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>

          {/* Warning if no groups selected */}
          {selectedGroups.size === 0 && (
            <div className="flex items-center gap-2 p-3 bg-yellow-50 text-yellow-800 rounded-lg">
              <X className="h-4 w-4" />
              <p className="text-sm">
                At least one group must be selected. Configurations without groups will be assigned to the default group.
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isAssigning}>
            Cancel
          </Button>
          <Button onClick={handleAssign} disabled={isAssigning || loading}>
            {isAssigning ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Assigning...
              </>
            ) : (
              <>
                <Check className="h-4 w-4 mr-2" />
                Assign to {selectedGroups.size} Group{selectedGroups.size !== 1 ? 's' : ''}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};