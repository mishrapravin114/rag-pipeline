'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { cn } from '@/lib/utils';
import { 
  FileSpreadsheet, 
  Upload, 
  X, 
  CheckCircle2, 
  XCircle, 
  AlertCircle, 
  FileUp,
  Download,
  Eye,
  Loader2,
  Info,
  RefreshCw,
  FileX,
  FileCheck
} from 'lucide-react';
import { apiService } from '@/services/api';

interface ImportPreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: (result: ImportResult) => void;
}

interface PreviewData {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  configurations: ConfigurationPreview[];
  validation_summary: ValidationSummary;
}

interface ConfigurationPreview {
  row: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: string;
  validation_rules?: string;
  is_active: boolean;
  validation_status: 'valid' | 'invalid' | 'duplicate';
  errors?: string[];
  warnings?: string[];
  exists?: boolean;
}

interface ValidationSummary {
  total_errors: number;
  total_warnings: number;
  missing_required: number;
  invalid_data_types: number;
  duplicate_names: number;
}

interface ImportOptions {
  import_mode: 'skip' | 'update' | 'replace';
  validate_only: boolean;
  include_inactive: boolean;
}

interface ImportResult {
  success: boolean;
  total_processed: number;
  successful_imports: number;
  failed_imports: number;
  skipped_imports: number;
  import_details: {
    successful: Array<{
      row: number;
      metadata_name: string;
      action: string;
      id: number;
    }>;
    failed: Array<{
      row: number;
      metadata_name: string;
      error: string;
    }>;
    skipped: Array<{
      row: number;
      metadata_name: string;
      reason: string;
    }>;
  };
}

export const ImportPreviewModal: React.FC<ImportPreviewModalProps> = ({
  isOpen,
  onClose,
  onImportComplete
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [previewData, setPreviewData] = useState<PreviewData | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [importOptions, setImportOptions] = useState<ImportOptions>({
    import_mode: 'skip',
    validate_only: false,
    include_inactive: true
  });
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<'upload' | 'preview' | 'importing' | 'complete'>('upload');

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && isValidExcelFile(droppedFile)) {
      setFile(droppedFile);
      validateFile(droppedFile);
    } else {
      setError('Please upload a valid Excel file (.xlsx or .xls)');
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile && isValidExcelFile(selectedFile)) {
      setFile(selectedFile);
      validateFile(selectedFile);
    } else {
      setError('Please upload a valid Excel file (.xlsx or .xls)');
    }
  };

  const isValidExcelFile = (file: File): boolean => {
    return file.name.endsWith('.xlsx') || file.name.endsWith('.xls');
  };

  const validateFile = async (file: File) => {
    setIsValidating(true);
    setError(null);
    
    try {
      // Call preview/validation endpoint
      const preview = await apiService.previewMetadataConfigImport(file);
      setPreviewData(preview);
      setCurrentStep('preview');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to validate file');
      setCurrentStep('upload');
    } finally {
      setIsValidating(false);
    }
  };

  const handleImport = async () => {
    if (!file || !previewData) return;

    setIsImporting(true);
    setError(null);
    setCurrentStep('importing');

    try {
      const result = await apiService.importMetadataConfigs(file, importOptions);
      setCurrentStep('complete');
      onImportComplete(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
      setCurrentStep('preview');
    } finally {
      setIsImporting(false);
    }
  };

  const resetModal = () => {
    setFile(null);
    setPreviewData(null);
    setError(null);
    setCurrentStep('upload');
    setImportOptions({
      import_mode: 'skip',
      validate_only: false,
      include_inactive: true
    });
  };

  const handleClose = () => {
    resetModal();
    onClose();
  };

  const getStatusBadge = (status: 'valid' | 'invalid' | 'duplicate') => {
    const variants = {
      valid: { color: 'bg-green-100 text-green-800', icon: CheckCircle2 },
      invalid: { color: 'bg-red-100 text-red-800', icon: XCircle },
      duplicate: { color: 'bg-yellow-100 text-yellow-800', icon: AlertCircle }
    };

    const variant = variants[status];
    const Icon = variant.icon;

    return (
      <Badge className={cn(variant.color, 'flex items-center gap-1')}>
        <Icon className="h-3 w-3" />
        {status}
      </Badge>
    );
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="max-w-6xl max-h-[90vh] p-0 overflow-hidden">
        <DialogHeader className="p-6 pb-0">
          <DialogTitle className="flex items-center gap-2 text-xl">
            <FileSpreadsheet className="h-5 w-5" />
            Import Metadata Configurations
          </DialogTitle>
        </DialogHeader>

        <div className="p-6 overflow-y-auto">
          {/* Progress Steps */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              {['upload', 'preview', 'importing', 'complete'].map((step, idx) => (
                <div key={step} className="flex-1 flex items-center">
                  <div className={cn(
                    "w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors",
                    currentStep === step || ['preview', 'importing', 'complete'].indexOf(currentStep) > idx
                      ? "bg-blue-600 text-white"
                      : "bg-gray-200 text-gray-500"
                  )}>
                    {idx + 1}
                  </div>
                  {idx < 3 && (
                    <div className={cn(
                      "flex-1 h-0.5 mx-2 transition-colors",
                      ['preview', 'importing', 'complete'].indexOf(currentStep) > idx
                        ? "bg-blue-600"
                        : "bg-gray-200"
                    )} />
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-2">
              <span className="text-xs">Upload File</span>
              <span className="text-xs">Preview & Validate</span>
              <span className="text-xs">Importing</span>
              <span className="text-xs">Complete</span>
            </div>
          </div>

          {/* Error Display */}
          {error && (
            <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
              <div className="flex-1">
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
          )}

          {/* Upload Step */}
          {currentStep === 'upload' && (
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Upload Excel File</CardTitle>
                </CardHeader>
                <CardContent>
                  <div
                    onDrop={handleDrop}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    className={cn(
                      "relative border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                      dragActive 
                        ? "border-blue-500 bg-blue-50" 
                        : "border-gray-300 hover:border-gray-400"
                    )}
                  >
                    <input
                      type="file"
                      accept=".xlsx,.xls"
                      onChange={handleFileSelect}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                      disabled={isValidating}
                    />
                    
                    <div className="space-y-4">
                      <div className="mx-auto w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center">
                        <FileUp className="h-8 w-8 text-gray-400" />
                      </div>
                      
                      <div>
                        <p className="text-lg font-medium text-gray-900">
                          Drop your Excel file here
                        </p>
                        <p className="text-sm text-gray-500 mt-1">
                          or click to browse
                        </p>
                      </div>
                      
                      {file && (
                        <div className="flex items-center justify-center gap-2 mt-4">
                          <FileCheck className="h-5 w-5 text-green-600" />
                          <span className="text-sm text-gray-700">{file.name}</span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              setFile(null);
                            }}
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                      
                      {isValidating && (
                        <div className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" />
                          <span className="text-sm text-gray-600">Validating file...</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-4 space-y-2">
                    <div className="flex items-start gap-2">
                      <Info className="h-4 w-4 text-blue-600 mt-0.5" />
                      <div className="text-sm text-gray-600">
                        <p>Required columns: metadata_name, description, extraction_prompt</p>
                        <p>Optional columns: data_type, validation_rules, is_active</p>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Import Options</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <Label className="text-sm font-medium mb-2 block">
                      How to handle existing configurations?
                    </Label>
                    <RadioGroup
                      value={importOptions.import_mode}
                      onValueChange={(value: 'skip' | 'update' | 'replace') => 
                        setImportOptions({...importOptions, import_mode: value})
                      }
                    >
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="skip" id="skip" />
                        <Label htmlFor="skip" className="cursor-pointer">
                          Skip duplicates (keep existing configurations unchanged)
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="update" id="update" />
                        <Label htmlFor="update" className="cursor-pointer">
                          Update existing configurations with new values
                        </Label>
                      </div>
                      <div className="flex items-center space-x-2">
                        <RadioGroupItem value="replace" id="replace" />
                        <Label htmlFor="replace" className="cursor-pointer">
                          Replace all existing configurations
                        </Label>
                      </div>
                    </RadioGroup>
                  </div>

                  <div className="flex items-center justify-between">
                    <Label htmlFor="include-inactive" className="cursor-pointer">
                      Include inactive configurations
                    </Label>
                    <Switch
                      id="include-inactive"
                      checked={importOptions.include_inactive}
                      onCheckedChange={(checked) => 
                        setImportOptions({...importOptions, include_inactive: checked})
                      }
                    />
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Preview Step */}
          {currentStep === 'preview' && previewData && (
            <div className="space-y-4">
              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-4">
                <Card className="bg-blue-50 border-blue-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-blue-600">Total Rows</p>
                        <p className="text-2xl font-bold text-blue-900">
                          {previewData.total_rows}
                        </p>
                      </div>
                      <FileSpreadsheet className="h-8 w-8 text-blue-400" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-green-50 border-green-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-green-600">Valid</p>
                        <p className="text-2xl font-bold text-green-900">
                          {previewData.valid_rows}
                        </p>
                      </div>
                      <CheckCircle2 className="h-8 w-8 text-green-400" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-yellow-50 border-yellow-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-yellow-600">Duplicates</p>
                        <p className="text-2xl font-bold text-yellow-900">
                          {previewData.duplicate_rows}
                        </p>
                      </div>
                      <AlertCircle className="h-8 w-8 text-yellow-400" />
                    </div>
                  </CardContent>
                </Card>

                <Card className="bg-red-50 border-red-200">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-red-600">Invalid</p>
                        <p className="text-2xl font-bold text-red-900">
                          {previewData.invalid_rows}
                        </p>
                      </div>
                      <XCircle className="h-8 w-8 text-red-400" />
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Validation Summary */}
              {previewData.validation_summary.total_errors > 0 && (
                <Card className="border-red-200">
                  <CardHeader className="bg-red-50 py-3">
                    <CardTitle className="text-sm flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 text-red-600" />
                      Validation Issues
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="p-4">
                    <ul className="space-y-1 text-sm">
                      {previewData.validation_summary.missing_required > 0 && (
                        <li className="text-red-700">
                          • {previewData.validation_summary.missing_required} rows missing required fields
                        </li>
                      )}
                      {previewData.validation_summary.invalid_data_types > 0 && (
                        <li className="text-red-700">
                          • {previewData.validation_summary.invalid_data_types} rows with invalid data types
                        </li>
                      )}
                      {previewData.validation_summary.duplicate_names > 0 && (
                        <li className="text-yellow-700">
                          • {previewData.validation_summary.duplicate_names} duplicate configurations
                        </li>
                      )}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {/* Configuration Preview Table */}
              <Card>
                <CardHeader>
                  <CardTitle>Configuration Preview</CardTitle>
                </CardHeader>
                <CardContent className="p-0">
                  <Tabs defaultValue="all" className="w-full">
                    <TabsList className="grid grid-cols-4 w-full">
                      <TabsTrigger value="all">
                        All ({previewData.configurations.length})
                      </TabsTrigger>
                      <TabsTrigger value="valid">
                        Valid ({previewData.valid_rows})
                      </TabsTrigger>
                      <TabsTrigger value="duplicates">
                        Duplicates ({previewData.duplicate_rows})
                      </TabsTrigger>
                      <TabsTrigger value="invalid">
                        Invalid ({previewData.invalid_rows})
                      </TabsTrigger>
                    </TabsList>

                    {['all', 'valid', 'duplicates', 'invalid'].map(tab => (
                      <TabsContent key={tab} value={tab} className="mt-0">
                        <ScrollArea className="h-[400px]">
                          <table className="w-full">
                            <thead className="bg-gray-50 sticky top-0">
                              <tr>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Row
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Name
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Type
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Status
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Issues
                                </th>
                                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                                  Action
                                </th>
                              </tr>
                            </thead>
                            <tbody className="bg-white divide-y divide-gray-200">
                              {previewData.configurations
                                .filter(config => {
                                  if (tab === 'all') return true;
                                  if (tab === 'valid') return config.validation_status === 'valid';
                                  if (tab === 'duplicates') return config.validation_status === 'duplicate';
                                  if (tab === 'invalid') return config.validation_status === 'invalid';
                                  return true;
                                })
                                .map((config) => (
                                  <tr key={config.row} className="hover:bg-gray-50">
                                    <td className="px-4 py-3 text-sm">
                                      {config.row}
                                    </td>
                                    <td className="px-4 py-3">
                                      <div className="text-sm font-medium text-gray-900">
                                        {config.metadata_name}
                                      </div>
                                      <div className="text-xs text-gray-500 mt-0.5">
                                        {config.description.slice(0, 50)}...
                                      </div>
                                    </td>
                                    <td className="px-4 py-3 text-sm">
                                      {config.data_type}
                                    </td>
                                    <td className="px-4 py-3">
                                      {getStatusBadge(config.validation_status)}
                                    </td>
                                    <td className="px-4 py-3 text-sm">
                                      {config.errors && config.errors.length > 0 && (
                                        <div className="space-y-1">
                                          {config.errors.map((error, idx) => (
                                            <p key={idx} className="text-red-600 text-xs">
                                              {error}
                                            </p>
                                          ))}
                                        </div>
                                      )}
                                      {config.warnings && config.warnings.length > 0 && (
                                        <div className="space-y-1">
                                          {config.warnings.map((warning, idx) => (
                                            <p key={idx} className="text-yellow-600 text-xs">
                                              {warning}
                                            </p>
                                          ))}
                                        </div>
                                      )}
                                    </td>
                                    <td className="px-4 py-3 text-sm">
                                      {config.exists ? (
                                        <span className="text-xs text-gray-500">
                                          {importOptions.import_mode === 'skip' 
                                            ? 'Will skip' 
                                            : importOptions.import_mode === 'update'
                                            ? 'Will update'
                                            : 'Will replace'}
                                        </span>
                                      ) : (
                                        <span className="text-xs text-green-600">
                                          Will create
                                        </span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                            </tbody>
                          </table>
                        </ScrollArea>
                      </TabsContent>
                    ))}
                  </Tabs>
                </CardContent>
              </Card>

              {/* Action Buttons */}
              <div className="flex justify-between items-center">
                <Button
                  variant="outline"
                  onClick={() => setCurrentStep('upload')}
                  disabled={isImporting}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  Change File
                </Button>
                
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={handleClose}
                    disabled={isImporting}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleImport}
                    disabled={isImporting || previewData.valid_rows === 0}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {isImporting ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Importing...
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4 mr-2" />
                        Import {previewData.valid_rows} Configuration{previewData.valid_rows !== 1 ? 's' : ''}
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          {/* Importing Step */}
          {currentStep === 'importing' && (
            <div className="space-y-4">
              <Card>
                <CardContent className="p-8">
                  <div className="text-center space-y-4">
                    <Loader2 className="h-12 w-12 animate-spin text-blue-600 mx-auto" />
                    <h3 className="text-lg font-medium">Importing Configurations...</h3>
                    <p className="text-sm text-gray-600">
                      Please wait while we import your metadata configurations.
                    </p>
                    <Progress value={33} className="w-full max-w-xs mx-auto" />
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {/* Complete Step */}
          {currentStep === 'complete' && (
            <div className="space-y-4">
              <Card>
                <CardContent className="p-8">
                  <div className="text-center space-y-4">
                    <CheckCircle2 className="h-12 w-12 text-green-600 mx-auto" />
                    <h3 className="text-lg font-medium">Import Complete!</h3>
                    <p className="text-sm text-gray-600">
                      Your metadata configurations have been successfully imported.
                    </p>
                    <Button
                      onClick={handleClose}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      Done
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};