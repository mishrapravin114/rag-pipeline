"use client";

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { 
  Plus, 
  Trash2,
  X,
  Save,
  AlertTriangle,
  Loader2
} from 'lucide-react';

interface TestFile {
  id: number;
  file_name: string;
  file_url: string;
  drug_name?: string;
  description?: string;
}

export default function TestUploadAndDelete() {
  const [files, setFiles] = useState<TestFile[]>([
    { id: 1, file_name: "test-document.pdf", file_url: "https://example.com/test.pdf", drug_name: "Test Drug" }
  ]);
  
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [deleteFileData, setDeleteFileData] = useState<TestFile | null>(null);
  const [loading, setLoading] = useState(false);
  
  const [uploadForm, setUploadForm] = useState({
    file_name: '',
    file_url: '',
    drug_name: '',
    description: ''
  });

  // Handle upload
  const handleUpload = async () => {
    setLoading(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    const newFile: TestFile = {
      id: Date.now(),
      file_name: uploadForm.file_name,
      file_url: uploadForm.file_url,
      drug_name: uploadForm.drug_name,
      description: uploadForm.description
    };
    
    setFiles([...files, newFile]);
    setUploadForm({ file_name: '', file_url: '', drug_name: '', description: '' });
    setIsUploadModalOpen(false);
    setLoading(false);
  };

  // Handle delete - show modal instead of browser confirm
  const handleDelete = (file: TestFile) => {
    setDeleteFileData(file);
    setIsDeleteModalOpen(true);
  };

  // Confirm delete
  const confirmDelete = async () => {
    if (!deleteFileData) return;
    
    setLoading(true);
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 500));
    
    setFiles(files.filter(f => f.id !== deleteFileData.id));
    setIsDeleteModalOpen(false);
    setDeleteFileData(null);
    setLoading(false);
  };

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Test Upload & Delete Functionality</h1>
        <Button 
          onClick={() => setIsUploadModalOpen(true)}
          className="flex items-center gap-2 bg-gradient-to-r from-green-600 to-emerald-600"
        >
          <Plus className="h-4 w-4" />
          Add File
        </Button>
      </div>

      {/* Files List */}
      <Card>
        <CardHeader>
          <CardTitle>Files ({files.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {files.length === 0 ? (
            <p className="text-gray-500 text-center py-8">No files uploaded yet</p>
          ) : (
            <div className="space-y-4">
              {files.map((file) => (
                <div key={file.id} className="flex items-center justify-between p-4 border rounded-lg">
                  <div>
                    <h3 className="font-medium">{file.file_name}</h3>
                    <p className="text-sm text-gray-600">{file.file_url}</p>
                    {file.drug_name && (
                      <p className="text-sm text-blue-600">Drug: {file.drug_name}</p>
                    )}
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm"
                    onClick={() => handleDelete(file)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Upload Modal */}
      {isUploadModalOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>Add New File</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setIsUploadModalOpen(false)}
                  disabled={loading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  File Name *
                </label>
                <Input
                  value={uploadForm.file_name}
                  onChange={(e) => setUploadForm({...uploadForm, file_name: e.target.value})}
                  placeholder="e.g., document.pdf"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  File URL *
                </label>
                <Input
                  value={uploadForm.file_url}
                  onChange={(e) => setUploadForm({...uploadForm, file_url: e.target.value})}
                  placeholder="https://example.com/document.pdf"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Drug Name
                </label>
                <Input
                  value={uploadForm.drug_name}
                  onChange={(e) => setUploadForm({...uploadForm, drug_name: e.target.value})}
                  placeholder="e.g., Aspirin"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-700 mb-2 block">
                  Description
                </label>
                <Textarea
                  value={uploadForm.description}
                  onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                  placeholder="Brief description..."
                  rows={3}
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <Button
                  variant="outline"
                  onClick={() => setIsUploadModalOpen(false)}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpload}
                  disabled={!uploadForm.file_name || !uploadForm.file_url || loading}
                  className="flex items-center gap-2"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  Add File
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && deleteFileData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-8 w-8 bg-gradient-to-r from-red-600 to-rose-600 rounded-lg flex items-center justify-center">
                    <Trash2 className="h-4 w-4 text-white" />
                  </div>
                  <span>Confirm Delete</span>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setIsDeleteModalOpen(false);
                    setDeleteFileData(null);
                  }}
                  disabled={loading}
                >
                  <X className="h-4 w-4" />
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-red-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="font-medium text-red-900 mb-2">Are you sure?</h4>
                    <p className="text-sm text-red-800 mb-2">
                      You are about to delete: <strong>{deleteFileData.file_name}</strong>
                    </p>
                    <p className="text-sm text-red-800">
                      This action cannot be undone.
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => {
                    setIsDeleteModalOpen(false);
                    setDeleteFileData(null);
                  }}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button
                  onClick={confirmDelete}
                  disabled={loading}
                  className="flex items-center gap-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-700 hover:to-rose-700"
                >
                  {loading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Delete File
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
} 