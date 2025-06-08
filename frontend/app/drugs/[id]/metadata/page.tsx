// Minor update
"use client";

import { useState, useEffect } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft, 
  FileText, 
  Download, 
  ExternalLink,
  Database,
  Tag,
  FileCheck,
  Loader2,
  Search,
  Grid3X3,
  List,
  Info
} from 'lucide-react';
import { Input } from '@/components/ui/input';
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
  metadata_details?: string;
}

interface SourceFile {
  id: number;
  file_name: string;
  file_url: string;
  drug_name: string;
  status: string;
}

// Generate a consistent color based on string hash
const stringToColor = (str: string) => {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  const colors = [
    'bg-blue-50 text-blue-700 border-blue-200',
    'bg-purple-50 text-purple-700 border-purple-200',
    'bg-green-50 text-green-700 border-green-200',
    'bg-indigo-50 text-indigo-700 border-indigo-200',
    'bg-pink-50 text-pink-700 border-pink-200',
    'bg-cyan-50 text-cyan-700 border-cyan-200',
    'bg-emerald-50 text-emerald-700 border-emerald-200',
    'bg-violet-50 text-violet-700 border-violet-200',
    'bg-rose-50 text-rose-700 border-rose-200',
    'bg-teal-50 text-teal-700 border-teal-200',
  ];
  
  return colors[Math.abs(hash) % colors.length];
};

export default function DrugMetadataPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const sourceFileId = parseInt(params.id as string);
  
  // Get return navigation parameters
  const returnQuery = searchParams.get('returnQuery');
  const returnFilter = searchParams.get('returnFilter');
  const shouldReturnToSearch = searchParams.get('returnSearch') === 'true';
  
  const [loading, setLoading] = useState(true);
  const [metadata, setMetadata] = useState<DrugMetadata[]>([]);
  const [sourceFile, setSourceFile] = useState<SourceFile | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    if (sourceFileId) {
      loadMetadata();
    }
  }, [sourceFileId]);

  const loadMetadata = async () => {
    try {
      setLoading(true);
      
      // Get source file details
      const fileResponse = await apiService.getSourceFile(sourceFileId);
      setSourceFile(fileResponse);
      
      // Get metadata for this source file
      const metadataResponse = await apiService.getDrugMetadata(sourceFileId);
      
      if (metadataResponse && metadataResponse.metadata) {
        setMetadata(metadataResponse.metadata);
      }
    } catch (error) {
      console.error('Failed to load metadata:', error);
      toast.error('Failed to load metadata details');
    } finally {
      setLoading(false);
    }
  };

  // Filter metadata based on search term
  const filteredMetadata = metadata.filter(item => 
    searchTerm === '' || 
    item.metadata_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    item.value.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleDownloadPDF = async () => {
    if (sourceFile?.file_url) {
      window.open(sourceFile.file_url, '_blank');
    }
  };

  const handleExportMetadata = async () => {
    try {
      // Prepare data for Excel export
      const exportData = metadata.map(item => ({
        'File URL': item.file_url || sourceFile?.file_url || '',
        'Drug Name': item.drugname || sourceFile?.drug_name || '',
        'Metadata Name': item.metadata_name,
        'Metadata Value': item.value
      }));

      // Create a new workbook
      const wb = XLSX.utils.book_new();
      
      // Convert data to worksheet
      const ws = XLSX.utils.json_to_sheet(exportData);
      
      // Set column widths
      const colWidths = [
        { wch: 50 }, // File URL
        { wch: 30 }, // Drug Name
        { wch: 40 }, // Metadata Name
        { wch: 60 }  // Metadata Value
      ];
      ws['!cols'] = colWidths;
      
      // Add worksheet to workbook
      XLSX.utils.book_append_sheet(wb, ws, 'Metadata');
      
      // Generate Excel file
      const excelBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' });
      
      // Create blob and download
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

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading metadata...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-8">
          <Button
            variant="ghost"
            onClick={() => {
              if (shouldReturnToSearch) {
                // Build return URL with search parameters
                const params = new URLSearchParams();
                if (returnQuery) params.set('q', returnQuery);
                if (returnFilter) params.set('filter', returnFilter);
                params.set('search', 'true');
                router.push(`/dashboard?${params.toString()}`);
              } else {
                router.push('/dashboard');
              }
            }}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to {shouldReturnToSearch ? 'Search Results' : 'Dashboard'}
          </Button>
          
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-3xl font-bold text-gray-900 mb-2">
                  {sourceFile?.drug_name || 'Drug Metadata'}
                </h1>
                <p className="text-gray-600 flex items-center gap-2">
                  <FileText className="h-4 w-4" />
                  {sourceFile?.file_name}
                </p>
                <div className="flex items-center gap-4 mt-3">
                  <Badge variant="outline" className="bg-green-50">
                    <FileCheck className="h-3 w-3 mr-1" />
                    {sourceFile?.status}
                  </Badge>
                  <span className="text-sm text-gray-500">
                    {metadata.length} metadata entries
                  </span>
                </div>
              </div>
              
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={handleExportMetadata}
                  disabled={metadata.length === 0}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export
                </Button>
                <Button
                  onClick={handleDownloadPDF}
                  disabled={!sourceFile?.file_url}
                >
                  <ExternalLink className="h-4 w-4 mr-2" />
                  View PDF
                </Button>
              </div>
            </div>
          </div>
        </div>

        {/* Search and Filter Bar */}
        {metadata.length > 0 && (
          <Card className="shadow-lg border-0 mb-6">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Search metadata by name or value..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="pl-10"
                  />
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-600">
                  <Info className="h-4 w-4" />
                  <span>{filteredMetadata.length} of {metadata.length} entries</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Metadata Display */}
        {metadata.length === 0 ? (
          <Card className="shadow-lg border-0">
            <CardContent className="text-center py-12">
              <Database className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600">No metadata available for this document</p>
              <p className="text-sm text-gray-500 mt-2">Metadata extraction may be pending or not configured for this file type</p>
            </CardContent>
          </Card>
        ) : filteredMetadata.length === 0 ? (
          <Card className="shadow-lg border-0">
            <CardContent className="text-center py-12">
              <Search className="h-12 w-12 text-gray-300 mx-auto mb-4" />
              <p className="text-gray-600">No metadata matches your search</p>
              <Button
                variant="link"
                onClick={() => setSearchTerm('')}
                className="mt-2"
              >
                Clear search
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-4">
            <Card className="shadow-lg border-0">
              <CardHeader>
                <CardTitle className="text-xl flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Extracted Metadata
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                <div className="space-y-4">
                  {filteredMetadata.map((item, index) => {
                    const colorClass = stringToColor(item.metadata_name);
                    
                    return (
                      <div
                        key={`${item.id}-${index}`}
                        className={`border rounded-lg transition-all hover:shadow-lg ${colorClass}`}
                      >
                        <div className="p-4">
                          <div className="flex items-start gap-3">
                            <Tag className="h-5 w-5 mt-0.5 flex-shrink-0" />
                            <div className="flex-1 min-w-0">
                              <h4 className="font-semibold text-gray-900 mb-2 break-words">
                                {item.metadata_name}
                              </h4>
                              <div className="bg-white/50 rounded-md p-3">
                                <p className="text-gray-700 whitespace-pre-wrap break-words text-sm">
                                  {item.value}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}