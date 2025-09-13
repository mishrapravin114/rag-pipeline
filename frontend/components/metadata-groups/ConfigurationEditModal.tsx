// Minor update
'use client';

import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Loader2, 
  AlertCircle,
  FileText,
  Wand2,
  History
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetadataConfig {
  id?: number;
  metadata_name: string;
  description: string;
  extraction_prompt: string;
  data_type: string;
  is_active: boolean;
  validation_rules?: any;
  extraction_prompt_version?: number;
}

interface ConfigurationEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  configuration: MetadataConfig | null;
  onSave: (config: MetadataConfig) => Promise<void>;
  onTest?: (prompt: string, sampleText: string) => Promise<any>;
  loading?: boolean;
  mode?: 'create' | 'edit' | 'clone';
}

const dataTypes = [
  { value: 'text', label: 'Text', description: 'Free-form text content' },
  { value: 'number', label: 'Number', description: 'Numeric values (integers or decimals)' },
  { value: 'date', label: 'Date', description: 'Date values in ISO format' },
  { value: 'boolean', label: 'Boolean', description: 'True/False values' }
];

const promptTemplates = {
  text: "Extract the {field_name} from the document. Return as plain text.",
  number: "Extract the numeric value for {field_name}. Return only the number.",
  date: "Extract the {field_name} date. Return in ISO format (YYYY-MM-DD).",
  boolean: "Determine if {field_name} is present or true. Return 'true' or 'false'."
};

export const ConfigurationEditModal: React.FC<ConfigurationEditModalProps> = ({
  isOpen,
  onClose,
  configuration,
  onSave,
  onTest,
  loading = false,
  mode = 'edit'
}) => {
  const [formData, setFormData] = useState<MetadataConfig>({
    metadata_name: '',
    description: '',
    extraction_prompt: '',
    data_type: 'text',
    is_active: true
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState('details');
  const [testSample, setTestSample] = useState('');
  const [testResult, setTestResult] = useState<any>(null);
  const [isTestingPrompt, setIsTestingPrompt] = useState(false);

  useEffect(() => {
    if (configuration) {
      setFormData({
        ...configuration,
        metadata_name: mode === 'clone' ? `${configuration.metadata_name} (Copy)` : configuration.metadata_name
      });
    } else {
      setFormData({
        metadata_name: '',
        description: '',
        extraction_prompt: '',
        data_type: 'text',
        is_active: true
      });
    }
    setErrors({});
    setTestResult(null);
  }, [configuration, mode]);

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.metadata_name.trim()) {
      newErrors.metadata_name = 'Name is required';
    }
    if (!formData.description.trim()) {
      newErrors.description = 'Description is required';
    }
    if (!formData.extraction_prompt.trim()) {
      newErrors.extraction_prompt = 'Extraction prompt is required';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    await onSave(formData);
  };

  const handleTestPrompt = async () => {
    if (!onTest || !testSample.trim() || !formData.extraction_prompt.trim()) return;

    setIsTestingPrompt(true);
    try {
      const result = await onTest(formData.extraction_prompt, testSample);
      setTestResult(result);
    } catch (error) {
      setTestResult({ error: 'Failed to test prompt' });
    } finally {
      setIsTestingPrompt(false);
    }
  };

  const applyPromptTemplate = () => {
    const template = promptTemplates[formData.data_type as keyof typeof promptTemplates];
    if (template) {
      setFormData({
        ...formData,
        extraction_prompt: template.replace('{field_name}', formData.metadata_name || 'field')
      });
    }
  };

  const title = mode === 'create' ? 'Create Configuration' : 
               mode === 'clone' ? 'Clone Configuration' : 
               'Edit Configuration';

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="details">Details</TabsTrigger>
            <TabsTrigger value="test">Test Extraction</TabsTrigger>
          </TabsList>

          <TabsContent value="details" className="space-y-4 mt-4">
            <div className="grid gap-4">
              {/* Name */}
              <div>
                <Label htmlFor="name">Configuration Name</Label>
                <Input
                  id="name"
                  value={formData.metadata_name}
                  onChange={(e) => setFormData({ ...formData, metadata_name: e.target.value })}
                  placeholder="e.g., Entity Name, Dosage Form"
                  className={cn(errors.metadata_name && "border-red-500")}
                />
                {errors.metadata_name && (
                  <p className="text-xs text-red-500 mt-1">{errors.metadata_name}</p>
                )}
              </div>

              {/* Description */}
              <div>
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe what this metadata field captures..."
                  rows={3}
                  className={cn(errors.description && "border-red-500")}
                />
                {errors.description && (
                  <p className="text-xs text-red-500 mt-1">{errors.description}</p>
                )}
              </div>

              {/* Data Type */}
              <div>
                <Label htmlFor="dataType">Data Type</Label>
                <Select
                  value={formData.data_type}
                  onValueChange={(value) => setFormData({ ...formData, data_type: value })}
                >
                  <SelectTrigger id="dataType">
                    <SelectValue placeholder="Select data type" />
                  </SelectTrigger>
                  <SelectContent>
                    {dataTypes.map(type => (
                      <SelectItem key={type.value} value={type.value} className="flex items-start">
                        <div className="flex flex-col">
                          <span className="font-medium">{type.label}</span>
                          <span className="text-xs text-gray-500">{type.description}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Extraction Prompt */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <Label htmlFor="prompt">Extraction Prompt</Label>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={applyPromptTemplate}
                    className="text-xs"
                  >
                    <Wand2 className="h-3 w-3 mr-1" />
                    Use Template
                  </Button>
                </div>
                <Textarea
                  id="prompt"
                  value={formData.extraction_prompt}
                  onChange={(e) => setFormData({ ...formData, extraction_prompt: e.target.value })}
                  placeholder="Enter the prompt that will be used to extract this metadata..."
                  rows={4}
                  className={cn("font-mono text-sm", errors.extraction_prompt && "border-red-500")}
                />
                {errors.extraction_prompt && (
                  <p className="text-xs text-red-500 mt-1">{errors.extraction_prompt}</p>
                )}
                {formData.extraction_prompt_version && (
                  <p className="text-xs text-gray-500 mt-1">
                    <History className="h-3 w-3 inline mr-1" />
                    Version {formData.extraction_prompt_version}
                  </p>
                )}
              </div>

              {/* Active Status */}
              <div className="flex items-center justify-between p-4 border rounded-lg">
                <div className="space-y-0.5">
                  <Label htmlFor="active">Active Status</Label>
                  <p className="text-sm text-gray-600">
                    Active configurations will be used for metadata extraction
                  </p>
                </div>
                <Switch
                  id="active"
                  checked={formData.is_active}
                  onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                />
              </div>
            </div>
          </TabsContent>

          <TabsContent value="test" className="space-y-4 mt-4">
            {onTest ? (
              <>
                <div>
                  <Label htmlFor="testSample">Sample Document Text</Label>
                  <Textarea
                    id="testSample"
                    value={testSample}
                    onChange={(e) => setTestSample(e.target.value)}
                    placeholder="Paste a sample section of a document to test the extraction prompt..."
                    rows={6}
                    className="font-mono text-sm"
                  />
                </div>

                <Button 
                  onClick={handleTestPrompt}
                  disabled={!testSample.trim() || !formData.extraction_prompt.trim() || isTestingPrompt}
                  className="w-full"
                >
                  {isTestingPrompt ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Testing Prompt...
                    </>
                  ) : (
                    <>
                      <FileText className="h-4 w-4 mr-2" />
                      Test Extraction
                    </>
                  )}
                </Button>

                {testResult && (
                  <Card>
                    <CardContent className="p-4">
                      <h4 className="font-medium mb-2">Extraction Result:</h4>
                      {testResult.error ? (
                        <div className="flex items-start gap-2 text-red-600">
                          <AlertCircle className="h-4 w-4 mt-0.5" />
                          <p className="text-sm">{testResult.error}</p>
                        </div>
                      ) : (
                        <div className="space-y-2">
                          <div className="p-3 bg-gray-50 rounded font-mono text-sm">
                            {testResult.value || 'No value extracted'}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant="outline">
                              Type: {testResult.type || formData.data_type}
                            </Badge>
                            {testResult.confidence && (
                              <Badge variant="outline">
                                Confidence: {Math.round(testResult.confidence * 100)}%
                              </Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </>
            ) : (
              <Card>
                <CardContent className="p-8 text-center text-gray-500">
                  <AlertCircle className="h-12 w-12 mx-auto mb-3" />
                  <p>Prompt testing is not available in this context.</p>
                  <p className="text-sm mt-1">Save the configuration first to test the extraction prompt.</p>
                </CardContent>
              </Card>
            )}
          </TabsContent>
        </Tabs>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              mode === 'create' ? 'Create Configuration' :
              mode === 'clone' ? 'Clone Configuration' :
              'Save Changes'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};