// Minor update
'use client';

import React from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  FileText, 
  Edit, 
  Trash2, 
  Settings,
  Calendar,
  Tag,
  Lock
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetadataGroup {
  id: number;
  name: string;
  description: string;
  configuration_count: number;
  created_at: string;
  updated_at: string;
  is_default?: boolean;
  color?: string;
  tags?: string[];
}

interface GroupCardProps {
  group: MetadataGroup;
  onEdit: (group: MetadataGroup) => void;
  onDelete: (group: MetadataGroup) => void;
  className?: string;
}

const colorClasses: Record<string, string> = {
  blue: 'bg-gradient-to-br from-blue-50 to-indigo-50 border-blue-200 hover:border-blue-400 hover:shadow-tech-lg',
  green: 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200 hover:border-green-400 hover:shadow-tech-lg',
  purple: 'bg-gradient-to-br from-purple-50 to-violet-50 border-purple-200 hover:border-purple-400 hover:shadow-tech-purple',
  yellow: 'bg-gradient-to-br from-yellow-50 to-amber-50 border-yellow-200 hover:border-yellow-400 hover:shadow-tech-lg',
  red: 'bg-gradient-to-br from-red-50 to-pink-50 border-red-200 hover:border-red-400 hover:shadow-tech-lg',
  gray: 'bg-gradient-to-br from-gray-50 to-slate-50 border-gray-200 hover:border-gray-400 hover:shadow-tech-lg',
};

export const GroupCard: React.FC<GroupCardProps> = ({
  group,
  onEdit,
  onDelete,
  className
}) => {
  const colorClass = colorClasses[group.color || 'gray'] || colorClasses.gray;

  return (
    <Card 
      className={cn(
        "transition-all duration-300 border-2 backdrop-blur-sm flex flex-col h-full",
        colorClass,
        className
      )}
    >
      <CardHeader className="pb-4">
        <div className="flex justify-between items-start">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-lg font-semibold text-gray-900 truncate">{group.name}</h3>
              {group.is_default && (
                <Badge variant="secondary" className="text-xs flex-shrink-0">
                  <Lock className="h-3 w-3 mr-1" />
                  Default
                </Badge>
              )}
            </div>
            <p className="text-sm text-gray-600 line-clamp-2 min-h-[2.5rem]">
              {group.description || 'No description provided'}
            </p>
          </div>
          <Badge variant="outline" className="ml-2 bg-white/80 backdrop-blur-sm flex-shrink-0">
            <FileText className="h-3 w-3 mr-1" />
            {group.configuration_count} fields
          </Badge>
        </div>
      </CardHeader>
      
      <CardContent className="flex flex-col flex-1 space-y-4">
        {/* Tags - This section will grow to fill available space */}
        <div className="flex-1">
          {group.tags && group.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {group.tags.map((tag, index) => (
                <Badge key={index} variant="secondary" className="text-xs px-2 py-0.5">
                  <Tag className="h-3 w-3 mr-1" />
                  {tag}
                </Badge>
              ))}
            </div>
          )}
        </div>

        {/* Bottom section - Always at the bottom */}
        <div className="mt-auto space-y-4">
          {/* Stats */}
          <div className="flex items-center justify-between text-xs text-gray-500 pt-3 border-t border-gray-100">
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              Updated {new Date(group.updated_at).toLocaleDateString()}
            </span>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button 
              asChild 
              size="sm" 
              className="flex-1 bg-gradient-to-r from-purple-600 to-indigo-600 text-white hover:from-purple-700 hover:to-indigo-700 btn-professional"
            >
              <Link href={`/operations/metadata-groups/${group.id}/manage-fields-v2`}>
                <Settings className="h-4 w-4 mr-2" />
                Manage Fields
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onEdit(group)}
              disabled={group.is_default}
              className="btn-professional-subtle hover:border-purple-400"
            >
              <Edit className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDelete(group)}
              disabled={group.is_default}
              className="hover:bg-red-50 hover:text-red-600 hover:border-red-300 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};