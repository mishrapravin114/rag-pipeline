"use client";

import { useState, useEffect } from 'react';
import { useRouter, useParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowLeft,
  FileText,
  Search,
  Calendar,
  Loader2,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import { apiService } from '@/services/api';
import { useAuth } from '@/hooks/useAuth';
import { API_BASE_URL } from '@/config/api';

interface MetadataGroup {
  id: number;
  name: string;
  description?: string;
}

interface Document {
  id: number;
  file_name: string;
  file_url: string;
  entity_name?: string;
  status: string;
  created_at: string;
}

export default function MetadataGroupDocumentsPage() {
  const router = useRouter();
  const params = useParams();
  const groupId = parseInt(params.id as string);
  const { user } = useAuth();
  
  const [group, setGroup] = useState<MetadataGroup | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [filteredDocuments, setFilteredDocuments] = useState<Document[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (groupId) {
      loadGroupDetails();
    }
  }, [groupId]);

  const loadGroupDetails = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const groupData = await apiService.getMetadataGroup(groupId);
      setGroup(groupData);

      // Assuming the API service has a method to get documents by metadata group
      // This might need to be created if it doesn't exist.
      // For now, let's assume it's called `getDocumentsByMetadataGroup`
      const result = await apiService.getDocumentsByMetadataGroup(groupId);
      
      const documentsWithFullUrls = (result.documents || []).map((doc: Document) => ({
        ...doc,
        file_url: doc.file_url.startsWith('http') 
          ? doc.file_url 
          : `${API_BASE_URL}${doc.file_url}`
      }));
      
      setDocuments(documentsWithFullUrls);
      setFilteredDocuments(documentsWithFullUrls);
      
    } catch (error) {
      console.error('Error loading group details:', error);
      setError('Failed to load group details. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const filtered = documents.filter(doc =>
      doc.file_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (doc.entity_name && doc.entity_name.toLowerCase().includes(searchTerm.toLowerCase()))
    );
    setFilteredDocuments(filtered);
  }, [searchTerm, documents]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600 mr-3" />
        <span className="text-gray-600">Loading documents...</span>
      </div>
    );
  }

  if (!group) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Card className="w-full max-w-md">
          <CardContent className="text-center p-8">
            <AlertCircle className="h-12 w-12 text-red-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Metadata Group Not Found</h3>
            <p className="text-gray-600 mb-6">The group you're looking for doesn't exist.</p>
            <Button onClick={() => router.push('/operations/metadata-groups')}>
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to Groups
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto px-4 py-8">
        <div className="mb-8">
          <Button
            variant="ghost"
            onClick={() => router.push('/operations/metadata-groups')}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Metadata Groups
          </Button>
          
          <div>
            <h1 className="text-3xl font-bold">{group.name}</h1>
            {group.description && (
              <p className="text-gray-600 mt-1">{group.description}</p>
            )}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Documents in this Group</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-4">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
                <Input
                  placeholder="Search documents..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10"
                />
              </div>
            </div>

            {filteredDocuments.length === 0 ? (
              <div className="text-center py-12">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <p className="text-gray-500">No documents found in this group.</p>
              </div>
            ) : (
              <div className="divide-y">
                {filteredDocuments.map((doc) => (
                  <div key={doc.id} className="py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <Link 
                          href={doc.file_url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="group"
                        >
                          <h3 className="text-lg font-medium text-gray-900 mb-1 group-hover:text-blue-600 transition-colors flex items-center gap-2">
                            {doc.entity_name ? `${doc.entity_name} - ${doc.file_name}` : doc.file_name}
                            <ExternalLink className="h-4 w-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                          </h3>
                        </Link>
                        <div className="flex items-center gap-4 text-sm text-gray-600">
                          <Badge variant="outline">{doc.status}</Badge>
                          <span className="flex items-center gap-1">
                            <Calendar className="h-4 w-4" />
                            Added: {new Date(doc.created_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}