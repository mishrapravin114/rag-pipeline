"use client";

import { useState, useEffect } from 'react';
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';
import { 
  X,
  FileText, 
  Download, 
  Database,
  Tag,
  Loader2,
  Search,
  Grid3X3,
  List,
  ExternalLink,
  Maximize2,
  Minimize2,
  ArrowUpDown,
  Info
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import * as XLSX from 'xlsx';

interface DrugMetadata {
  id: number;
  metadata_name: string;
  value: string;
  drugname: string;
  source_file_id: number;
  file_url: string;
  created_at: string;
}

interface SourceFile {
  id: number;
  file_name: string;
  file_url: string;
  drug_name: string;
  status: string;
}

interface MetadataModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceFileId: number;
  drugName?: string;
}

// Generate consistent color for metadata names
const getMetadataColor = (name: string) => {
  const colors = [
    'from-blue-600 to-blue-700',
    'from-indigo-600 to-indigo-700',
    'from-purple-600 to-purple-700',
    'from-pink-600 to-pink-700',
    'from-red-600 to-red-700',
    'from-orange-600 to-orange-700',
    'from-amber-600 to-amber-700',
    'from-yellow-600 to-yellow-700',
    'from-lime-600 to-lime-700',
    'from-green-600 to-green-700',
    'from-emerald-600 to-emerald-700',
    'from-teal-600 to-teal-700',
    'from-cyan-600 to-cyan-700',
  ];
  
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  return colors[Math.abs(hash) % colors.length];
};

// Convert to proper title case
const toTitleCase = (str: string) => {
  // Common abbreviations that should stay uppercase
  const upperCaseWords = ['FDA', 'USA', 'UK', 'EU', 'API', 'ID', 'URL', 'PDF', 'XML', 'JSON', 'CSV'];
  
  return str.split('_').map(word => {
    // Check if the word should stay uppercase
    if (upperCaseWords.includes(word.toUpperCase())) {
      return word.toUpperCase();
    }
    
    // Handle camelCase words
    const camelCaseProcessed = word.replace(/([a-z])([A-Z])/g, '$1 $2');
    
    // Convert to title case
    return camelCaseProcessed
      .split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  }).join(' ');
};

export function MetadataModal({ isOpen, onClose, sourceFileId, drugName }: MetadataModalProps) {
  const [loading, setLoading] = useState(true);
  const [metadata, setMetadata] = useState<DrugMetadata[]>([]);
  const [sourceFile, setSourceFile] = useState<SourceFile | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [sortBy, setSortBy] = useState<'name' | 'value'>('name');
  const [isMaximized, setIsMaximized] = useState(false);

  useEffect(() => {
    if (isOpen && sourceFileId) {
      loadMetadata();
    }
  }, [isOpen, sourceFileId]);

  const loadMetadata = async () => {
    setLoading(true);
    try {
      const response = await apiService.getDrugMetadata(sourceFileId);
      setMetadata(response.metadata || []);
      setSourceFile(response.source_file);
    } catch (error) {
      console.error('Failed to load metadata:', error);
      toast.error('Failed to load metadata');
    } finally {
      setLoading(false);
    }
  };

  const filteredMetadata = metadata.filter(item =>
    item.metadata_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.value.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const sortedMetadata = [...filteredMetadata].sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.metadata_name.localeCompare(b.metadata_name);
      case 'value':
        return a.value.localeCompare(b.value);
      default:
        return 0;
    }
  });

  const exportToExcel = () => {
    try {
      const data = metadata.map(item => ({
        'Metadata Name': toTitleCase(item.metadata_name),
        'Value': item.value,
        'Drug Name': item.drugname,
        'Created Date': new Date(item.created_at).toLocaleDateString()
      }));
      
      const ws = XLSX.utils.json_to_sheet(data);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, 'Metadata');
      
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${sourceFile?.drug_name || 'drug'}_metadata_${new Date().toISOString().split('T')[0]}.xlsx`;
      link.click();
      window.URL.revokeObjectURL(url);
      
      toast.success('Metadata exported to Excel successfully');
    } catch (error) {
      console.error('Export error:', error);
      toast.error('Failed to export metadata');
    }
  };

  const MetadataCard = ({ item }: { item: DrugMetadata }) => {
    const colorGradient = getMetadataColor(item.metadata_name);
    
    return (
      <div className="group bg-white rounded-xl border border-gray-200 hover:border-blue-300 hover:shadow-lg transition-all duration-300 p-5 cursor-pointer">
        <div className="space-y-3">
          <h4 className={`font-semibold text-transparent bg-clip-text bg-gradient-to-r ${colorGradient} text-lg`}>
            {toTitleCase(item.metadata_name)}
          </h4>
          <p className="text-gray-700 text-sm leading-relaxed break-words">
            {item.value}
          </p>
        </div>
      </div>
    );
  };

  const MetadataListItem = ({ item, index }: { item: DrugMetadata; index: number }) => {
    const colorGradient = getMetadataColor(item.metadata_name);
    const isEvenRow = index % 2 === 0;
    
    return (
      <div className={cn(
        "group flex items-center py-4 px-6 transition-all duration-200 border-b border-gray-100 last:border-0",
        isEvenRow ? "bg-gray-50/70" : "bg-white",
        "hover:bg-gradient-to-r hover:from-blue-50 hover:to-indigo-50"
      )}>
        <div className="flex-1 grid grid-cols-2 gap-6 items-center">
          <div>
            <p className={`font-medium text-transparent bg-clip-text bg-gradient-to-r ${colorGradient}`}>
              {toTitleCase(item.metadata_name)}
            </p>
          </div>
          <div>
            <p className="text-sm text-gray-700">{item.value}</p>
          </div>
        </div>
      </div>
    );
  };

  return (
    <DialogPrimitive.Root open={isOpen} onOpenChange={onClose}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className={cn(
          "fixed z-50 bg-white shadow-2xl duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          isMaximized 
            ? 'inset-0 w-full h-full rounded-none' 
            : 'left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] w-[95vw] max-w-6xl h-[90vh] rounded-xl',
          "flex flex-col overflow-hidden"
        )}>
          {/* Visually hidden title for accessibility */}
          <DialogPrimitive.Title className="sr-only">
            Drug Metadata Dashboard
          </DialogPrimitive.Title>
          {/* Header */}
          <div className="px-6 py-5 border-b bg-gradient-to-r from-blue-600 to-indigo-700 flex-shrink-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-2.5 bg-white/20 rounded-lg backdrop-blur-sm">
                  <Database className="h-6 w-6 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Drug Metadata Dashboard</h2>
                  <p className="text-blue-100 mt-1">
                    {sourceFile?.drug_name || drugName || 'Loading...'} 
                    {sourceFile?.file_name && (
                      <>
                        <span className="mx-2">•</span>
                        <span className="text-sm">{sourceFile.file_name}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={() => setIsMaximized(!isMaximized)}
                  variant="ghost"
                  size="sm"
                  className="h-9 w-9 p-0 text-white hover:bg-white/20 rounded-lg transition-colors"
                >
                  {isMaximized ? <Minimize2 className="h-5 w-5" /> : <Maximize2 className="h-5 w-5" />}
                </Button>
                <DialogPrimitive.Close asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-9 w-9 p-0 text-white hover:bg-white/20 rounded-lg transition-colors"
                  >
                    <X className="h-5 w-5" />
                  </Button>
                </DialogPrimitive.Close>
              </div>
            </div>
          </div>

          <div className="flex-1 flex flex-col bg-gray-50 min-h-0">
            {loading ? (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <Loader2 className="h-10 w-10 animate-spin text-blue-600 mx-auto mb-4" />
                  <p className="text-gray-600 font-medium">Loading metadata...</p>
                </div>
              </div>
            ) : (
              <>
                {/* Controls Bar */}
                <div className="bg-white border-b border-gray-200 px-6 py-4 flex-shrink-0">
                  <div className="flex flex-col lg:flex-row gap-4">
                    {/* Search */}
                    <div className="relative flex-1">
                      <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
                      <Input
                        placeholder="Search metadata..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-10 bg-gray-50 border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200"
                      />
                    </div>

                    <div className="flex items-center gap-3">
                      {/* Sort */}
                      <div className="flex items-center gap-2">
                        <ArrowUpDown className="h-4 w-4 text-gray-500" />
                        <select
                          value={sortBy}
                          onChange={(e) => setSortBy(e.target.value as any)}
                          className="px-3 py-2 bg-gray-50 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="name">Sort by Name</option>
                          <option value="value">Sort by Value</option>
                        </select>
                      </div>

                      {/* View Mode */}
                      <div className="flex items-center gap-1 border border-gray-300 rounded-lg p-1 bg-gray-50">
                        <Button
                          variant={viewMode === 'list' ? 'default' : 'ghost'}
                          size="sm"
                          onClick={() => setViewMode('list')}
                          className={`px-3 btn-professional-subtle ${viewMode === 'list' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'hover:bg-gray-100'}`}
                        >
                          <List className="h-4 w-4" />
                        </Button>
                        <Button
                          variant={viewMode === 'grid' ? 'default' : 'ghost'}
                          size="sm"
                          onClick={() => setViewMode('grid')}
                          className={`px-3 btn-professional-subtle ${viewMode === 'grid' ? 'bg-blue-600 hover:bg-blue-700 text-white' : 'hover:bg-gray-100'}`}
                        >
                          <Grid3X3 className="h-4 w-4" />
                        </Button>
                      </div>

                      {/* Actions */}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={exportToExcel}
                        className="bg-white hover:bg-gray-50 border-blue-300 text-blue-600 hover:text-blue-700 btn-professional-subtle"
                      >
                        <Download className="h-4 w-4 mr-2" />
                        Export
                      </Button>
                      {sourceFile?.file_url && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => window.open(sourceFile.file_url, '_blank')}
                          className="bg-white hover:bg-gray-50 border-blue-300 text-blue-600 hover:text-blue-700 btn-professional-subtle"
                        >
                          <ExternalLink className="h-4 w-4 mr-2" />
                          Source
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="flex items-center gap-6 mt-4">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-blue-100 rounded">
                        <Tag className="h-4 w-4 text-blue-600" />
                      </div>
                      <span className="text-sm font-medium text-gray-700">{metadata.length} Total Fields</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 bg-green-100 rounded">
                        <FileText className="h-4 w-4 text-green-600" />
                      </div>
                      <span className="text-sm font-medium text-gray-700">{filteredMetadata.length} Matching</span>
                    </div>
                    {searchTerm && (
                      <div className="flex items-center gap-2">
                        <Info className="h-4 w-4 text-gray-400" />
                        <span className="text-sm text-gray-500">Searching for "{searchTerm}"</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Metadata Content with ScrollArea */}
                <div className="flex-1 overflow-hidden min-h-0">
                  <ScrollArea className="h-full w-full" type="always">
                    <div className="p-6">
                      {viewMode === 'list' ? (
                        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
                          {sortedMetadata.length > 0 ? (
                            <div>
                              {sortedMetadata.map((item, index) => (
                                <MetadataListItem key={item.id} item={item} index={index} />
                              ))}
                            </div>
                          ) : (
                            <div className="text-center py-16">
                              <Database className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                              <p className="text-gray-500 font-medium">No metadata found</p>
                              {searchTerm && (
                                <p className="text-sm text-gray-400 mt-2">
                                  Try adjusting your search term
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                          {sortedMetadata.length > 0 ? (
                            sortedMetadata.map((item) => (
                              <MetadataCard key={item.id} item={item} />
                            ))
                          ) : (
                            <div className="col-span-full text-center py-16">
                              <Database className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                              <p className="text-gray-500 font-medium">No metadata found</p>
                              {searchTerm && (
                                <p className="text-sm text-gray-400 mt-2">
                                  Try adjusting your search term
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </ScrollArea>
                </div>
              </>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}