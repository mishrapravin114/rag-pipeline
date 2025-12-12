// Minor update
// Minor update
'use client';

import React, { useState, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';
import { 
  ArrowLeft,
  Upload,
  Download,
  FileSpreadsheet,
  CheckCircle,
  AlertCircle,
  Info,
  X,
  Loader2
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from '@/components/ui/use-toast';

interface ImportResult {
  success: boolean;
  imported: number;
  skipped: number;
  errors: string[];
  created_groups: string[];
  details: Array<{
    row: number;
    name: string;
    status: string;
    action?: string;
    reason?: string;
  }>;
}

export default function ImportMetadataPage() {
  const router = useRouter();
  const params = useParams();
  const groupId = params?.id as string;
  const { token, authLoading } = useAuth();
  
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.xlsx') && !selectedFile.name.endsWith('.xls')) {
        toast({
          title: "Invalid file type",
          description: "Please select an Excel file (.xlsx or .xls)",
          variant: "destructive"
        });
        return;
      }
      setFile(selectedFile);
      setImportResult(null);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      if (!droppedFile.name.endsWith('.xlsx') && !droppedFile.name.endsWith('.xls')) {
        toast({
          title: "Invalid file type",
          description: "Please select an Excel file (.xlsx or .xls)",
          variant: "destructive"
        });
        return;
      }
      setFile(droppedFile);
      setImportResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !token) return;

    setUploading(true);
    try {
      const result = await apiService.importMetadataConfigurations(file, token);
      setImportResult(result);
      
      if (result.success) {
        toast({
          title: "Import successful",
          description: `Imported ${result.imported} configurations, skipped ${result.skipped}`
        });
        
        // If we're in a specific group context, assign imported configs to this group
        if (groupId && result.imported > 0) {
          // Get the IDs of imported configurations from the details
          const importedConfigIds = result.details
            .filter(d => d.status === 'success' && d.action === 'imported')
            .map(d => d.row); // Note: We'd need the actual config IDs here
          
          // TODO: Call API to assign imported configs to current group
        }
      }
    } catch (error: any) {
      toast({
        title: "Import failed",
        description: error.response?.data?.detail || "Failed to import configurations",
        variant: "destructive"
      });
    } finally {
      setUploading(false);
    }
  };

  const downloadTemplate = async () => {
    try {
      const blob = await apiService.downloadMetadataTemplate(token);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'metadata-import-template.xlsx';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      
      toast({
        title: "Template downloaded",
        description: "Check your downloads folder"
      });
    } catch (error) {
      toast({
        title: "Download failed",
        description: "Failed to download template",
        variant: "destructive"
      });
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="space-y-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.back()}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
        
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Import Metadata Fields</h1>
          <p className="text-lg text-gray-600 mt-2">
            Upload an Excel file to bulk import metadata configurations
          </p>
        </div>
      </div>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            How to Import
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
            <li>Download the Excel template using the button below</li>
            <li>Fill in the template with your metadata configurations</li>
            <li>Each row represents one metadata field</li>
            <li>Upload the completed Excel file</li>
            <li>Review the import results</li>
          </ol>
          
          <Button
            variant="outline"
            onClick={downloadTemplate}
            className="w-full"
          >
            <Download className="h-4 w-4 mr-2" />
            Download Excel Template
          </Button>
        </CardContent>
      </Card>

      {/* Upload Area */}
      <Card>
        <CardHeader>
          <CardTitle>Upload File</CardTitle>
          <CardDescription>
            Select or drag and drop your Excel file here
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`
              border-2 border-dashed rounded-lg p-12 text-center cursor-pointer
              transition-all duration-200
              ${isDragging 
                ? 'border-blue-500 bg-blue-50' 
                : 'border-gray-300 hover:border-gray-400 hover:bg-gray-50'
              }
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileSelect}
              className="hidden"
            />
            
            <FileSpreadsheet className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            
            {file ? (
              <div className="space-y-2">
                <p className="text-sm font-medium text-gray-900">{file.name}</p>
                <p className="text-xs text-gray-500">
                  {(file.size / 1024).toFixed(2)} KB
                </p>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                    setImportResult(null);
                  }}
                >
                  <X className="h-4 w-4 mr-1" />
                  Remove
                </Button>
              </div>
            ) : (
              <>
                <p className="text-sm text-gray-600">
                  Drop your Excel file here, or click to browse
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  Supports .xlsx and .xls files
                </p>
              </>
            )}
          </div>

          {file && !importResult && (
            <Button
              onClick={handleUpload}
              disabled={uploading}
              className="w-full mt-4 bg-blue-600 hover:bg-blue-700"
            >
              {uploading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Importing...
                </>
              ) : (
                <>
                  <Upload className="h-4 w-4 mr-2" />
                  Import File
                </>
              )}
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Import Results */}
      {importResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              {importResult.success ? (
                <>
                  <CheckCircle className="h-5 w-5 text-green-600" />
                  Import Complete
                </>
              ) : (
                <>
                  <AlertCircle className="h-5 w-5 text-red-600" />
                  Import Failed
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Summary */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1">
                <p className="text-sm text-gray-500">Imported</p>
                <p className="text-2xl font-bold text-green-600">{importResult.imported}</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm text-gray-500">Skipped</p>
                <p className="text-2xl font-bold text-yellow-600">{importResult.skipped}</p>
              </div>
            </div>

            {/* Created Groups */}
            {importResult.created_groups.length > 0 && (
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Created {importResult.created_groups.length} new groups: {importResult.created_groups.join(', ')}
                </AlertDescription>
              </Alert>
            )}

            {/* Errors */}
            {importResult.errors.length > 0 && (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>
                  <p className="font-semibold mb-2">Errors:</p>
                  <ul className="list-disc list-inside space-y-1">
                    {importResult.errors.map((error, idx) => (
                      <li key={idx} className="text-sm">{error}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            )}

            {/* Details */}
            {importResult.details.length > 0 && (
              <div>
                <h4 className="font-medium mb-2">Import Details</h4>
                <div className="max-h-64 overflow-y-auto border rounded-lg">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50 sticky top-0">
                      <tr>
                        <th className="text-left p-2">Row</th>
                        <th className="text-left p-2">Name</th>
                        <th className="text-left p-2">Status</th>
                        <th className="text-left p-2">Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {importResult.details.map((detail, idx) => (
                        <tr key={idx} className="border-t">
                          <td className="p-2">{detail.row}</td>
                          <td className="p-2 font-medium">{detail.name}</td>
                          <td className="p-2">
                            <span className={`
                              inline-flex items-center px-2 py-1 rounded-full text-xs font-medium
                              ${detail.status === 'success' 
                                ? 'bg-green-100 text-green-800'
                                : detail.status === 'skipped'
                                ? 'bg-yellow-100 text-yellow-800'
                                : 'bg-red-100 text-red-800'
                              }
                            `}>
                              {detail.status}
                            </span>
                          </td>
                          <td className="p-2 text-gray-600">
                            {detail.action || detail.reason || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex gap-2 pt-4">
              <Button
                variant="outline"
                onClick={() => {
                  setFile(null);
                  setImportResult(null);
                }}
              >
                Import Another File
              </Button>
              <Button
                onClick={() => router.back()}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Done
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}