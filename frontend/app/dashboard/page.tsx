"use client";

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useActivityTracker } from '@/hooks/useActivityTracker';
import { useChatHistory } from '@/hooks/useChatHistory';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Search, 
  TrendingUp, 
  MessageSquare, 
  FileText, 
  BarChart3,
  Pill,
  Building,
  Calendar,
  Clock,
  Filter,
  ChevronRight,
  Bot,
  BookOpen,
  Star,
  Download,
  ExternalLink,
  ChevronDown,
  X,
  Target,
  Zap,
  RefreshCw,
  FolderOpen,
  Loader2,
  Info
} from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Checkbox } from "@/components/ui/checkbox";
import { MetadataModal } from "@/components/dashboard/MetadataModal";
import { ChatModal } from "@/components/dashboard/ChatModal";
import { ChatModalProfessional } from "@/components/dashboard/ChatModalProfessional";

interface SearchResult {
  source_file_id: number;
  file_name: string;
  file_url: string;
  drug_name: string | null;
  us_ma_date?: string;
  relevance_score: number;
  relevance_comments: string;
  grade_weight: number;
  search_type?: string;
}

interface Drug {
  id: string;
  name: string;
  manufacturer: string;
  therapeuticArea: string;
  approvalDate: string;
  status: string;
  indication: string;
}

interface Collection {
  id: number;
  name: string;
  description?: string;
  document_count?: number;
}

interface DashboardStats {
  totalDrugs: number;
  totalManufacturers: number;
  recentApprovals: number;
  totalSearches: number;
  additionalStats?: {
    totalSourceFiles: number;
    processedFiles: number;
    totalMetadataEntries: number;
    recentSearches7d: number;
    trendingDrugs: Array<{ drug_name: string; search_count: number }>;
    topDrugs: Array<{ name: string; count: number }>;
    topManufacturers: Array<{ name: string; count: number }>;
  };
  lastUpdated?: string;
}

export default function DashboardPage() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  
  // State management
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [pagination, setPagination] = useState<{
    page: number;
    page_size: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
  } | null>(null);
  const [dashboardStats, setDashboardStats] = useState<DashboardStats>({
    totalDrugs: 0,
    totalManufacturers: 0,
    recentApprovals: 0,
    totalSearches: 0
  });
  const [trendingDrugs, setTrendingDrugs] = useState<Drug[]>([]);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [loadingStats, setLoadingStats] = useState(true);
  const [drugNames, setDrugNames] = useState<string[]>([]);
  const [selectedDrugFilter, setSelectedDrugFilter] = useState<string | null>(null);
  const [showDrugFilter, setShowDrugFilter] = useState(false);
  const [searchType, setSearchType] = useState<string>('');
  const [totalResults, setTotalResults] = useState(0);
  const [loadingDrugNames, setLoadingDrugNames] = useState(false);
  const [showRelevanceDialog, setShowRelevanceDialog] = useState(false);
  const [selectedResult, setSelectedResult] = useState<SearchResult | null>(null);
  const [selectedDocuments, setSelectedDocuments] = useState<Set<number>>(new Set());
  const [isSelectionMode, setIsSelectionMode] = useState(false);
  const [metadataModalOpen, setMetadataModalOpen] = useState(false);
  const [selectedMetadataFile, setSelectedMetadataFile] = useState<{ id: number; name: string } | null>(null);
  const [chatModalOpen, setChatModalOpen] = useState(false);
  const [selectedChatFiles, setSelectedChatFiles] = useState<{ 
    ids: number[]; 
    names: string[]; 
    drugDocuments?: Array<{
      drugName: string;
      documents: Array<{
        id: number;
        fileName: string;
      }>;
    }>;
    isCollectionChat?: boolean; 
    collectionId?: number; 
    isDashboardCollectionChat?: boolean 
  } | null>(null);
  const [loadingCollectionDocuments, setLoadingCollectionDocuments] = useState(false);
  
  // Collection filter state
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<number | null>(null);
  const [loadingCollections, setLoadingCollections] = useState(false);
  
  // Use the activity tracker hook
  const { activities: recentActivity, trackSearch, trackView, trackChat, refreshActivities } = useActivityTracker();
  
  // Use the chat history hook for recent history (with docXChat=true filter for dashboard)
  const { history: chatHistory, loadHistory } = useChatHistory(true);

  // Load dashboard data when component mounts
  useEffect(() => {
    console.log('🚀 Dashboard mounted, loading data...');
    loadDashboardData();
    loadDrugNames(); // Load all drug names initially
    loadCollections();
    refreshActivities(); // Load recent activities with docXChat=true filter
    loadHistory(); // Load chat history with docXChat filter
    
    // Check if we're returning from chat with search state
    const returnFromSearch = searchParams.get('search') === 'true';
    const returnQuery = searchParams.get('q');
    const returnFilter = searchParams.get('filter');
    
    if (returnFromSearch) {
      // Restore search state
      if (returnQuery) {
        setSearchQuery(returnQuery);
      }
      if (returnFilter) {
        setSelectedDrugFilter(returnFilter);
      }
      
      // Check for collection filter from URL
      const collectionId = searchParams.get('collection_id');
      if (collectionId) {
        setSelectedCollection(parseInt(collectionId));
      }
      
      // Trigger search after a short delay to ensure everything is loaded
      setTimeout(() => {
        if (returnQuery || returnFilter) {
          handleSearch(returnQuery || '', returnFilter || null);
        }
        // Clean up URL parameters after restoring search
        router.replace('/dashboard', { scroll: false });
      }, 100);
    }
    
    // Auto-refresh stats every 5 minutes
    const statsInterval = setInterval(() => {
      console.log('🔄 Auto-refreshing dashboard stats...');
      loadDashboardData();
    }, 5 * 60 * 1000); // 5 minutes
    
    return () => {
      clearInterval(statsInterval);
    };
  }, []);

  // Reload drug names when collection changes
  useEffect(() => {
    if (selectedCollection !== null) {
      // Clear existing drug filter when collection changes
      setSelectedDrugFilter(null);
      // Load drug names for the selected collection
      loadDrugNames(selectedCollection);
    } else {
      // Load all drug names when no collection is selected
      loadDrugNames();
    }
  }, [selectedCollection]);

  const loadDashboardData = async () => {
    setLoadingStats(true);
    try {
      const data = await apiService.getDashboardData();
      setDashboardStats({
        totalDrugs: data.total_drugs,
        totalManufacturers: data.total_manufacturers,
        recentApprovals: data.recent_approvals || 0,
        totalSearches: data.total_searches || (data.additional_stats?.recent_searches_7d || 0),
        additionalStats: data.additional_stats ? {
          totalSourceFiles: data.additional_stats.total_source_files,
          processedFiles: data.additional_stats.processed_files,
          totalMetadataEntries: data.additional_stats.total_metadata_entries,
          recentSearches7d: data.additional_stats.recent_searches_7d,
          trendingDrugs: data.additional_stats.trending_drugs,
          topDrugs: data.additional_stats.top_drugs,
          topManufacturers: data.additional_stats.top_manufacturers
        } : undefined,
        lastUpdated: data.last_updated
      });
      
      // Process trending drugs directly from the response data
      if (data.additional_stats?.trending_drugs && data.additional_stats.trending_drugs.length > 0) {
        console.log('Processing trending drugs from dashboard data:', data.additional_stats.trending_drugs);
        const trendingData = data.additional_stats.trending_drugs.map((drug: any, index: number) => ({
          id: `trending-${index}`,
          name: drug.drug_name.toUpperCase(), // Capitalize drug names
          manufacturer: 'View Details',
          therapeuticArea: 'Multiple',
          approvalDate: '',
          status: 'Trending',
          indication: `${drug.search_count} searches`
        }));
        setTrendingDrugs(trendingData.slice(0, 3));
      }
    } catch (error) {
      console.error('Failed to load dashboard stats:', error);
      // Set some fallback values
      setDashboardStats({
        totalDrugs: 0,
        totalManufacturers: 0,
        recentApprovals: 0,
        totalSearches: 0
      });
    } finally {
      setLoadingStats(false);
    }
  };

  // Remove loadTrendingDrugs as trending drugs are now loaded directly in loadDashboardData

  // No longer needed - using useActivityTracker hook
  
  // No longer needed - using useActivityTracker hook

  const loadDrugNames = async (collectionId?: number | null) => {
    try {
      setLoadingDrugNames(true);
      console.log('Loading drug names...', collectionId ? `for collection ${collectionId}` : 'for all collections');
      const response = await apiService.getUniqueDrugNames(collectionId || undefined);
      console.log('Drug names response:', response);
      if (response.success) {
        setDrugNames(response.drug_names);
        console.log('Drug names loaded:', response.drug_names.length);
      }
    } catch (error) {
      console.error('Failed to load drug names:', error);
      toast.error('Failed to load drug filter options');
    } finally {
      setLoadingDrugNames(false);
    }
  };
  
  const loadCollections = async () => {
    setLoadingCollections(true);
    try {
      const response = await apiService.getCollections();
      setCollections(response.collections || []);
    } catch (error) {
      console.error('Failed to load collections:', error);
    } finally {
      setLoadingCollections(false);
    }
  };

  const handleSearch = async (queryOverride?: string, filterOverride?: string | null, page: number = 1) => {
    const query = queryOverride !== undefined ? queryOverride : searchQuery;
    const filter = filterOverride !== undefined ? filterOverride : selectedDrugFilter;
    
    // Ensure query is a string
    const queryString = String(query || '');
    
    // Collection is now mandatory
    if (!selectedCollection) {
      toast.error('Please select a collection before searching');
      return;
    }
    
    // No additional validation needed - allow search with just collection selected
    
    setIsSearching(true);
    setShowSearchResults(true);
    setCurrentPage(page);
    
    let resultsCount = 0;
    
    try {
      // Use empty string if no query but drug filter is selected
      const searchQueryString = queryString.trim() || '';
      
      // If we have a search query and a drug filter, we need to get the source_file_id
      let sourceFileId: number | undefined;
      if (searchQueryString && filter && selectedCollection) {
        // Find the source_file_id for the selected drug in the collection
        try {
          const collectionDetails = await apiService.getCollectionDetails(selectedCollection);
          if (collectionDetails.documents) {
            const drugFile = collectionDetails.documents.find(
              (doc: any) => doc.drug_name === filter && doc.status === 'READY'
            );
            if (drugFile) {
              sourceFileId = drugFile.id;
            }
          }
        } catch (error) {
          console.error('Failed to get source file ID for drug:', error);
        }
      }
      
      const response = await apiService.searchDocuments(
        searchQueryString, 
        filter || undefined, 
        selectedCollection || undefined,
        sourceFileId,
        page,
        pageSize
      );
      
      if (response.success) {
        // Ensure each result has the search_type from the response
        const resultsWithSearchType = response.results.map(result => ({
          ...result,
          search_type: result.search_type || response.search_type
        }));
        setSearchResults(resultsWithSearchType);
        setSearchType(response.search_type);
        setTotalResults(response.total_results);
        resultsCount = response.results.length;
        
        // Store pagination info
        if (response.pagination) {
          setPagination(response.pagination);
        }
        
        if (response.results.length === 0) {
          toast.info('No results found. Try different search terms or filters.');
        }
      } else {
        throw new Error('Search failed');
      }
    } catch (error) {
      console.error('Search failed:', error);
      toast.error('Failed to search documents. Please try again.');
      setSearchResults([]);
    } finally {
      setIsSearching(false);
      
      // Track search activity
      trackSearch(
        searchQuery.trim() || 'all results',
        selectedDrugFilter || undefined,
        resultsCount
      );
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      setCurrentPage(1); // Reset to first page
      handleSearch(searchQuery, selectedDrugFilter, 1);
    }
  };

  const handleDrugFilterSelect = (drugName: string | null) => {
    setSelectedDrugFilter(drugName);
    setShowDrugFilter(false);
    setCurrentPage(1); // Reset to first page
    // Immediately trigger a search with the new filter
    handleSearch(searchQuery, drugName, 1);
  };

  const clearDrugFilter = () => {
    setSelectedDrugFilter(null);
  };

  const openFileUrl = (url: string) => {
    if (url) {
      window.open(url, '_blank');
    }
  };

  const handleShowRelevanceDetails = (result: SearchResult) => {
    setSelectedResult(result);
    setShowRelevanceDialog(true);
  };

  const toggleDocumentSelection = (sourceFileId: number) => {
    const newSelection = new Set(selectedDocuments);
    if (newSelection.has(sourceFileId)) {
      newSelection.delete(sourceFileId);
    } else {
      newSelection.add(sourceFileId);
    }
    setSelectedDocuments(newSelection);
  };

  const clearSelection = () => {
    setSelectedDocuments(new Set());
    setIsSelectionMode(false);
  };

  const startMultiChat = () => {
    if (selectedDocuments.size > 0) {
      const selectedResults = searchResults.filter(result => 
        selectedDocuments.has(result.source_file_id)
      );
      
      setSelectedChatFiles({
        ids: Array.from(selectedDocuments),
        names: selectedResults.map(r => r.drug_name || r.file_name.split('_')[0] || 'document'),
        isCollectionChat: false,
        collectionId: selectedCollection || -1  // Use -1 when no collection is selected
      });
      setChatModalOpen(true);
      
      // Clear selection after opening chat
      setSelectedDocuments(new Set());
      setIsSelectionMode(false);
    }
  };

  return (
    <TooltipProvider>
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8">
        
        {/* Welcome Section */}
        <div className="mb-8">
          <div className="mb-8">
            <div className="text-center mb-8">
              <h1 className="text-4xl lg:text-5xl font-bold page-title mb-2 leading-tight">DocXAI Intelligence Platform</h1>
              <h2 className="text-2xl font-semibold text-blue-500 mb-4">Advanced DocXAI Discovery & Analysis</h2>              
            </div>
          </div>
        </div>
        
        {/* Document Search Interface */}
        <div className="mb-8">
          <Card className="border-0 shadow-lg">
            <CardContent className="p-8">
              <h2 className="text-2xl font-bold text-gray-900 mb-6">Document Search</h2>
              
              <div className="space-y-4">
                {/* Search Query Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Search Query</label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
                    <Input
                      type="text"
                      placeholder="Enter keywords, topics, or questions (optional)"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={handleKeyPress}
                      className="pl-10 pr-4 py-3 text-base"
                    />
                  </div>
                  <p className="mt-1 text-sm text-gray-500">Leave empty to search by collection or drug only.</p>
                </div>
                
                {/* Filters Row */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Collection Filter */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Collection Filter</label>
                    <Select
                      value={selectedCollection?.toString() || 'all'}
                      onValueChange={(value) => setSelectedCollection(value === 'all' ? null : parseInt(value))}
                    >
                      <SelectTrigger className="w-full h-[46px]">
                        <SelectValue placeholder="All Collections">
                          <div className="flex items-center gap-2">
                            <FolderOpen className="h-4 w-4" />
                            {selectedCollection ? collections.find(c => c.id === selectedCollection)?.name || 'All Collections' : 'All Collections'}
                          </div>
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2">
                            <FolderOpen className="h-4 w-4" />
                            All Collections
                          </div>
                        </SelectItem>
                        {collections.map((collection) => (
                          <SelectItem key={collection.id} value={collection.id.toString()}>
                            <div className="flex items-center justify-between w-full">
                              <span>{collection.name}</span>
                              <span className="text-xs text-gray-500 ml-2">({collection.document_count || 0})</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {/* Drug Filter */}
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Drug Filter</label>
                    <Select
                      value={selectedDrugFilter || 'all'}
                      onValueChange={(value) => setSelectedDrugFilter(value === 'all' ? null : value)}
                    >
                      <SelectTrigger className="w-full h-[46px]">
                        <SelectValue placeholder="All Drugs">
                          <div className="flex items-center gap-2">
                            <Pill className="h-4 w-4" />
                            {selectedDrugFilter || 'All Drugs'}
                          </div>
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">
                          <div className="flex items-center gap-2">
                            <Pill className="h-4 w-4" />
                            All Drugs
                          </div>
                        </SelectItem>
                        {loadingDrugNames ? (
                          <div className="px-2 py-4 text-center text-sm text-gray-500">
                            <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2" />
                            Loading drugs...
                          </div>
                        ) : (
                          drugNames.map((drugName) => (
                            <SelectItem key={drugName} value={drugName}>
                              <div className="flex items-center gap-2">
                                <Pill className="h-3 w-3" />
                                {drugName}
                              </div>
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                
                {/* Search Button and Actions */}
                <div className="flex items-center justify-between pt-4">
                  <div className="text-sm text-gray-600">
                    {(selectedCollection || selectedDrugFilter || searchQuery) && (
                      <div className="flex items-center gap-2">
                        <span>Active filters:</span>
                        {searchQuery && (
                          <Badge variant="secondary" className="text-xs">
                            Query: "{searchQuery}"
                          </Badge>
                        )}
                        {selectedCollection && (
                          <Badge variant="secondary" className="text-xs">
                            Collection: {collections.find(c => c.id === selectedCollection)?.name}
                          </Badge>
                        )}
                        {selectedDrugFilter && (
                          <Badge variant="secondary" className="text-xs">
                            Drug: {selectedDrugFilter}
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setSearchQuery('');
                            setSelectedCollection(null);
                            setSelectedDrugFilter(null);
                            setCurrentPage(1);
                            setPagination(null);
                            setSearchResults([]);
                            setShowSearchResults(false);
                          }}
                          className="h-6 px-2 text-xs"
                        >
                          Clear all
                        </Button>
                      </div>
                    )}
                  </div>
                  
                  <Button 
                    className="px-8 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => {
                      setCurrentPage(1); // Reset to first page
                      handleSearch(searchQuery, selectedDrugFilter, 1);
                    }}
                    disabled={isSearching || !selectedCollection}
                    title={!selectedCollection ? "Please select a collection to search" : ""}
                  >
                    {isSearching ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <Search className="h-4 w-4 mr-2" />
                    )}
                    Search Documents
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Search Results */}
        {showSearchResults && (
          <div className="mb-8">
            <Card className="shadow-lg border-0">
              <CardHeader className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-t-lg">
                <div className="space-y-2">
                  <CardTitle className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Search className="h-5 w-5" />
                      {searchQuery.trim() ? (
                        <>
                          Search Results for "{searchQuery}"
                          {(selectedDrugFilter || selectedCollection) && (
                            <span className="text-sm font-normal">
                              (filtered by{' '}
                              {selectedDrugFilter && `drug: ${selectedDrugFilter}`}
                              {selectedDrugFilter && selectedCollection && ', '}
                              {selectedCollection && `collection: ${collections.find(c => c.id === selectedCollection)?.name}`}
                              )
                            </span>
                          )}
                        </>
                      ) : (
                        <>
                          All Results
                          {(selectedDrugFilter || selectedCollection) && (
                            <span className="text-sm font-normal">
                              {' '}for{' '}
                              {selectedDrugFilter && `${selectedDrugFilter}`}
                              {selectedDrugFilter && selectedCollection && ' in '}
                              {selectedCollection && `${collections.find(c => c.id === selectedCollection)?.name}`}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                    {totalResults > 0 && (
                      <div className="text-sm font-normal">
                        {totalResults} results • {searchType} search
                      </div>
                    )}
                  </CardTitle>
                  {searchResults.length > 0 && (
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-2">
                          <Checkbox 
                            className="h-4 w-4" 
                            checked={isSelectionMode}
                            onCheckedChange={(checked) => setIsSelectionMode(!!checked)}
                          />
                          <label 
                            htmlFor="selection-mode"
                            className="text-xs font-medium cursor-pointer"
                            onClick={() => setIsSelectionMode(!isSelectionMode)}
                          >
                            Select Multiple
                          </label>
                        </div>
                        {selectedDocuments.size > 0 && (
                          <>
                            <span className="text-xs">
                              {selectedDocuments.size} selected
                            </span>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={clearSelection}
                              className="text-xs"
                            >
                              Clear
                            </Button>
                            <Button
                              size="sm"
                              onClick={startMultiChat}
                              className="text-xs bg-white text-blue-600 hover:bg-gray-100"
                            >
                              <MessageSquare className="h-3 w-3 mr-1" />
                              Chat with Selected ({selectedDocuments.size})
                            </Button>
                          </>
                        )}
                      </div>
                      {selectedCollection && (
                        <Button
                          size="sm"
                          onClick={async () => {
                            // Load all documents in the collection like the collections page does
                            if (selectedCollection) {
                              setLoadingCollectionDocuments(true);
                              try {
                                const result = await apiService.getCollectionDetails(selectedCollection);
                                console.log('Collection details result:', result);
                                const collectionDocs = result.documents || [];
                                console.log('Collection documents:', collectionDocs);
                                
                                // Use collection_status instead of status
                                const readyDocs = collectionDocs.filter((doc: any) => 
                                  doc.collection_status === 'INDEXED' || doc.indexing_status === 'indexed'
                                );
                                console.log('Ready documents:', readyDocs);
                                console.log('Ready doc IDs:', readyDocs.map((doc: any) => doc.id));
                                
                                // Create drug documents grouped by drug name
                                const drugDocMap = new Map();
                                collectionDocs.forEach((doc: any) => {
                                  const drugName = doc.drug_name || doc.file_name;
                                  if (!drugDocMap.has(drugName)) {
                                    drugDocMap.set(drugName, {
                                      drugName,
                                      documents: []
                                    });
                                  }
                                  drugDocMap.get(drugName).documents.push({
                                    id: doc.id,
                                    fileName: doc.file_name
                                  });
                                });
                                
                                const drugDocuments = Array.from(drugDocMap.values())
                                  .sort((a, b) => a.drugName.localeCompare(b.drugName));
                                
                                // For collection chat, don't pass document IDs
                                setSelectedChatFiles({
                                  ids: [],  // Pass empty array for collection-wide chat
                                  names: collectionDocs.map((doc: any) => doc.drug_name || doc.file_name),
                                  drugDocuments,  // Pass the grouped drug documents
                                  isCollectionChat: true,
                                  collectionId: selectedCollection,
                                  isDashboardCollectionChat: true  // Flag to indicate this is from dashboard
                                });
                                setChatModalOpen(true);
                              } catch (error) {
                                console.error('Failed to load collection documents:', error);
                                toast.error('Failed to load collection documents');
                              } finally {
                                setLoadingCollectionDocuments(false);
                              }
                            }
                          }}
                          className="text-xs bg-white text-blue-600 hover:bg-gray-100"
                          disabled={loadingCollectionDocuments}
                        >
                          {loadingCollectionDocuments ? (
                            <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                          ) : (
                            <MessageSquare className="h-3 w-3 mr-1" />
                          )}
                          Chat with {collections.find(c => c.id === selectedCollection)?.name || 'Collection'}
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="p-6">
                {isSearching ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mr-3" />
                    <span>Searching FDA database...</span>
                  </div>
                ) : searchResults.length > 0 ? (
                  <div className="space-y-6">
                    {(() => {
                      // Group results by drug name
                      const groupedResults = searchResults.reduce((acc, result) => {
                        const drugName = result.drug_name;
                        if (!acc[drugName]) {
                          acc[drugName] = [];
                        }
                        acc[drugName].push(result);
                        return acc;
                      }, {} as Record<string, SearchResult[]>);

                      // Sort drug names alphabetically
                      const sortedDrugNames = Object.keys(groupedResults).sort();

                      return sortedDrugNames.map((drugName) => {
                        const drugResults = groupedResults[drugName];
                        const hasMultipleDates = drugResults.length > 1;

                        return (
                          <div key={drugName} className="space-y-4">
                            {/* Drug Name Header */}
                            <div className="flex items-center justify-between">
                              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                                <Pill className="h-5 w-5 text-blue-600" />
                                {drugName}
                                {hasMultipleDates && (
                                  <>
                                    <span className="text-sm font-normal text-gray-600">
                                      ({drugResults.length} documents)
                                    </span>
                                  </>
                                )}
                              </h3>
                              {hasMultipleDates && (
                                <div className="flex items-center gap-2">
                                  <div className="inline-flex items-center gap-1 px-3 py-1 bg-orange-50 text-orange-700 rounded-full text-xs font-medium">
                                    <Calendar className="h-3 w-3" />
                                    {drugResults.length} different dates
                                  </div>
                                </div>
                              )}
                            </div>

                            {/* Results for this drug */}
                            <div className={`${hasMultipleDates ? 'space-y-3 pl-6 border-l-2 border-gray-200' : ''}`}>
                              {drugResults.map((result) => (
                                <Card 
                                  key={result.source_file_id} 
                                  className={`hover:shadow-lg transition-all duration-200 border-gray-200 hover:border-blue-300 ${
                                    selectedDocuments.has(result.source_file_id) ? 'ring-2 ring-blue-500 border-blue-500' : ''
                                  } ${hasMultipleDates ? 'relative before:absolute before:w-3 before:h-3 before:bg-white before:border-2 before:border-gray-300 before:rounded-full before:-left-[1.56rem] before:top-8 hover:before:border-blue-500' : ''}`}
                                >
                                  <CardContent className="p-5">
                                    <div className="space-y-4">
                                      <div className="flex items-start justify-between">
                                        <div className="flex-1">
                                          {!hasMultipleDates && (
                                            <h3 className="font-semibold text-gray-900 text-lg">
                                              {result.drug_name}
                                            </h3>
                                          )}
                                          <p className="text-sm text-gray-600 mt-1">
                                            <FileText className="h-3.5 w-3.5 inline mr-1 text-gray-400" />
                                            {result.file_name}
                                          </p>
                                          {/* Show date from us_ma_date field */}
                                          {(() => {
                                            if (result.us_ma_date) {
                                              // Format the date if it's in ISO format
                                              let formattedDate = result.us_ma_date;
                                              try {
                                                const date = new Date(result.us_ma_date);
                                                if (!isNaN(date.getTime())) {
                                                  formattedDate = date.toLocaleDateString('en-US', {
                                                    year: 'numeric',
                                                    month: 'short',
                                                    day: 'numeric'
                                                  });
                                                }
                                              } catch (e) {
                                                // Keep original format if parsing fails
                                              }
                                              
                                              return (
                                                <div className="inline-flex items-center gap-1 px-3 py-1 mt-2 bg-blue-100 text-blue-800 rounded-full text-xs font-semibold">
                                                  <Calendar className="h-3 w-3" />
                                                  {formattedDate}
                                                </div>
                                              );
                                            }
                                            return (
                                              <div className="inline-flex items-center gap-1 px-3 py-1 mt-2 bg-gray-100 text-gray-600 rounded-full text-xs">
                                                <Calendar className="h-3 w-3" />
                                                No date available
                                              </div>
                                            );
                                          })()}
                                        </div>
                                        {isSelectionMode && (
                                          <Checkbox
                                            checked={selectedDocuments.has(result.source_file_id)}
                                            onCheckedChange={() => toggleDocumentSelection(result.source_file_id)}
                                            className="mt-1"
                                          />
                                        )}
                                      </div>
                                      
                                      {/* Relevance Score Card */}
                                      <div className="bg-gray-50 rounded-lg p-3 space-y-2">
                                        <div className="flex items-center justify-between">
                                          <div className="flex items-center gap-1.5">
                                            {result.search_type === 'SQL' ? (
                                              <Target className="h-3.5 w-3.5 text-gray-500" />
                                            ) : (
                                              <Zap className="h-3.5 w-3.5 text-gray-500" />
                                            )}
                                            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Relevance Score</span>
                                          </div>
                                          <div className={`text-lg font-bold ${
                                            result.relevance_score >= 90 ? 'text-green-600' :
                                            result.relevance_score >= 70 ? 'text-blue-600' :
                                            result.relevance_score >= 50 ? 'text-yellow-600' :
                                            'text-orange-600'
                                          }`}>
                                            {Math.round(result.relevance_score)}%
                                          </div>
                                        </div>
                                        
                                        {/* Progress Bar */}
                                        <div className="w-full bg-gray-200 rounded-full h-2.5">
                                          <div 
                                            className={`h-2.5 rounded-full transition-all duration-500 ${
                                              result.relevance_score >= 90 ? 'bg-gradient-to-r from-green-500 to-green-600' :
                                              result.relevance_score >= 70 ? 'bg-gradient-to-r from-blue-500 to-blue-600' :
                                              result.relevance_score >= 50 ? 'bg-gradient-to-r from-yellow-500 to-yellow-600' :
                                              'bg-gradient-to-r from-orange-500 to-orange-600'
                                            }`}
                                            style={{ width: `${Math.min(result.relevance_score, 100)}%` }}
                                          />
                                        </div>
                                        
                                        {/* Match Details */}
                                        <div className="space-y-1">
                                          <div className="flex items-center justify-between text-xs">
                                            <span className="text-gray-600">
                                              {result.search_type === 'SQL' ? 'Direct Match' : 'Similarity Match'}
                                            </span>
                                            {result.search_type !== 'SQL' && typeof result.grade_weight === 'number' && result.grade_weight > 0 && (
                                              <button
                                                onClick={() => handleShowRelevanceDetails(result)}
                                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 text-blue-700 font-medium hover:bg-blue-100 transition-colors cursor-pointer group"
                                                title="Click to view relevance details"
                                              >
                                                {result.grade_weight} relevant {result.grade_weight === 1 ? 'section' : 'sections'}
                                                <ChevronRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
                                              </button>
                                            )}
                                </div>
                                          <p className="text-xs text-gray-500 italic">
                                            {result.search_type === 'SQL' 
                                              ? 'Found by exact drug name match' 
                                              : `Found by content similarity${result.grade_weight > 0 ? ` in ${result.grade_weight} document section${result.grade_weight > 1 ? 's' : ''}` : ''}`}
                                          </p>
                                        </div>
                                      </div>
                                      
                                      <div className="pt-3 border-t flex items-center gap-2">
                                        <Button 
                                          variant="outline" 
                                          size="sm"
                                          className="flex-1 bg-gradient-to-r from-purple-50 to-indigo-50 hover:from-purple-100 hover:to-indigo-100 text-purple-700 border-purple-200 hover:border-purple-300 transition-all duration-200"
                                          onClick={() => {
                                            // Track metadata view activity
                                            trackView(result.drug_name, result.source_file_id);
                                            
                                            // Open metadata modal
                                            setSelectedMetadataFile({ 
                                              id: result.source_file_id, 
                                              name: result.drug_name 
                                            });
                                            setMetadataModalOpen(true);
                                          }}
                                        >
                                          <FileText className="h-4 w-4 mr-1.5 text-purple-600" />
                                          View Metadata
                                        </Button>
                                        <Button 
                                          size="sm"
                                          className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white shadow-sm hover:shadow-md transition-all duration-200"
                                          onClick={() => {
                                            // Track chat activity
                                            trackChat(result.drug_name || result.file_name.split('_')[0] || 'unknown', result.source_file_id);
                                            
                                            // Open chat modal
                                            setSelectedChatFiles({
                                              ids: [result.source_file_id],
                                              names: [result.drug_name || result.file_name.split('_')[0] || 'this document'],
                                              isCollectionChat: false,
                                              collectionId: selectedCollection || -1  // Use -1 when no collection is selected
                                            });
                                            setChatModalOpen(true);
                                          }}
                                        >
                                          <MessageSquare className="h-4 w-4 mr-1.5" />
                                          Chat
                                        </Button>
                                      </div>
                                    </div>
                                  </CardContent>
                                </Card>
                              ))}
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </div>
                ) : (
                  <div className="text-center py-12">
                    <div className="bg-gray-100 rounded-full h-20 w-20 flex items-center justify-center mx-auto mb-4">
                      <FileText className="h-10 w-10 text-gray-400" />
                    </div>
                    <h3 className="text-lg font-medium text-gray-900 mb-1">No results found</h3>
                    <p className="text-gray-600">
                      {searchQuery ? `No documents match "${searchQuery}"` : 'No documents found'}
                      {selectedDrugFilter && <span className="block text-sm mt-1">for drug: {selectedDrugFilter}</span>}
                    </p>
                    <p className="text-sm text-gray-500 mt-3">Try adjusting your search terms or filters</p>
                  </div>
                )}
                
                {/* Pagination Controls */}
                {pagination && searchResults.length > 0 && (
                  <div className="mt-6 flex items-center justify-between border-t pt-6">
                    <div className="text-sm text-gray-600">
                      Showing {((pagination.page - 1) * pagination.page_size) + 1} to {Math.min(pagination.page * pagination.page_size, totalResults)} of {totalResults} results
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSearch(searchQuery, selectedDrugFilter, currentPage - 1)}
                        disabled={!pagination.has_previous || isSearching}
                      >
                        Previous
                      </Button>
                      
                      <div className="flex items-center gap-1">
                        {/* Show page numbers */}
                        {Array.from({ length: Math.min(5, pagination.total_pages) }, (_, i) => {
                          const pageNumber = Math.max(1, Math.min(currentPage - 2 + i, pagination.total_pages - 4)) + i;
                          if (pageNumber > pagination.total_pages) return null;
                          
                          return (
                            <Button
                              key={pageNumber}
                              variant={pageNumber === currentPage ? "default" : "outline"}
                              size="sm"
                              onClick={() => handleSearch(searchQuery, selectedDrugFilter, pageNumber)}
                              disabled={isSearching}
                              className="min-w-[40px]"
                            >
                              {pageNumber}
                            </Button>
                          );
                        }).filter(Boolean)}
                      </div>
                      
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleSearch(searchQuery, selectedDrugFilter, currentPage + 1)}
                        disabled={!pagination.has_next || isSearching}
                      >
                        Next
                      </Button>
                    </div>
                    
                    <Select
                      value={pageSize.toString()}
                      onValueChange={(value) => {
                        setPageSize(parseInt(value));
                        setCurrentPage(1); // Reset to first page when changing page size
                        handleSearch(searchQuery, selectedDrugFilter, 1);
                      }}
                    >
                      <SelectTrigger className="w-[120px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="10">10 per page</SelectItem>
                        <SelectItem value="20">20 per page</SelectItem>
                        <SelectItem value="50">50 per page</SelectItem>
                        <SelectItem value="100">100 per page</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Recent History and Trending Drugs */}
        <div className="flex gap-8 mb-8">
          {/* Recent History */}
          <div className="w-1/2">
            <Card className="shadow-lg border-0 h-[400px] flex flex-col">
              <CardHeader className="bg-gradient-to-r from-purple-600 via-purple-700 to-pink-600 text-white px-6 py-4 flex-shrink-0">
                <CardTitle className="flex items-center justify-between text-lg">
                  <div className="flex items-center gap-2">
                    <Clock className="h-5 w-5" />
                    Recent History
                  </div>
                  <RefreshCw 
                    className="h-4 w-4 cursor-pointer hover:rotate-180 transition-transform duration-500" 
                    onClick={loadHistory}
                  />
                </CardTitle>
              </CardHeader>
              <CardContent className="bg-gray-50 p-6 flex-grow overflow-auto">
                {chatHistory.length === 0 ? (
                  <div className="text-center py-8">
                    <Clock className="h-8 w-8 text-gray-400 mx-auto mb-3" />
                    <p className="text-gray-600 font-medium">No recent history</p>
                    <p className="text-sm text-gray-500 mt-1">Start a conversation to see your history here</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {chatHistory.slice(0, 4).map((item) => (
                      <div key={`history-${item.id}`} className="flex items-center gap-3 p-3 bg-white rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer group">
                        <div className="h-8 w-8 bg-gray-100 rounded-lg flex items-center justify-center transition-transform duration-200 group-hover:scale-110">
                          <Clock className="h-4 w-4 text-gray-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium text-gray-900 truncate">
                            {item.query && item.query.length > 50 ? `${item.query.substring(0, 50)}...` : (item.query || 'No query')}
                          </div>
                          <div className="text-xs text-gray-500">
                            {new Date(item.created_at).toLocaleDateString()}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Trending Drugs */}
          <div className="w-1/2">
            <Card className="shadow-lg border-0 h-[400px] flex flex-col">
              <CardHeader className="bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-4 flex-shrink-0">
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="h-5 w-5" />
                  Trending Drugs Search
                </CardTitle>
              </CardHeader>
              <CardContent className="bg-gray-50 p-6 flex-grow overflow-auto">
                <div className="space-y-3">
                  {trendingDrugs.length > 0 && trendingDrugs[0].name !== 'No trending data' ? (
                    trendingDrugs.slice(0, 3).map((drug, index) => (
                      <div key={drug.id} className="flex items-center gap-3 p-3 bg-white rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer group">
                        <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-600 text-white font-semibold text-sm">
                          {index + 1}
                        </div>
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{drug.name}</div>
                          <div className="text-xs text-gray-500">{drug.indication}</div>
                        </div>
                        <TrendingUp className="h-4 w-4 text-green-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8">
                      <TrendingUp className="h-8 w-8 text-gray-400 mx-auto mb-3" />
                      <p className="text-gray-600 font-medium">No trending drugs</p>
                      <p className="text-sm text-gray-500 mt-1">Search activity will appear here</p>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
         
        {/* Chat Panel Modal */}
        {isChatOpen && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <Card className="w-full max-w-2xl max-h-[80vh] mx-4">
              <CardHeader className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-t-lg">
                <CardTitle className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Bot className="h-5 w-5" />
                    FDA AI Assistant
                  </div>
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={() => setIsChatOpen(false)}
                    className="text-white hover:bg-white/20"
                  >
                    ✕
                  </Button>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6 h-96">
                <div className="flex items-center justify-center h-full">
                  <div className="text-center">
                    <Bot className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-600">AI Chat functionality coming soon</p>
                    <p className="text-sm text-gray-500 mt-2">Ask questions about drugs, interactions, and FDA data</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Relevance Details Dialog */}
        <Dialog open={showRelevanceDialog} onOpenChange={setShowRelevanceDialog}>
          <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Relevance Details</DialogTitle>
              <DialogDescription>
                Detailed information about why this document was matched
              </DialogDescription>
            </DialogHeader>
            
            {selectedResult && (
              <div className="space-y-4 mt-4">
                {/* Document Info */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-semibold text-gray-900 mb-2">Document Information</h4>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Drug Name:</span>
                      <span className="font-medium">{selectedResult.drug_name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">File Name:</span>
                      <span className="font-medium text-xs">{selectedResult.file_name}</span>
                    </div>
                  </div>
                </div>

                {/* Relevance Score Breakdown */}
                <div className="bg-blue-50 rounded-lg p-4">
                  <h4 className="font-semibold text-gray-900 mb-3">Relevance Score Breakdown</h4>
                  
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-gray-700">Overall Relevance Score:</span>
                      <div className="flex items-center gap-2">
                        <div className="w-32 bg-gray-200 rounded-full h-3">
                          <div 
                            className={`h-3 rounded-full transition-all ${
                              selectedResult.relevance_score >= 90 ? 'bg-green-500' :
                              selectedResult.relevance_score >= 70 ? 'bg-blue-500' :
                              selectedResult.relevance_score >= 50 ? 'bg-yellow-500' :
                              'bg-orange-500'
                            }`}
                            style={{ width: `${Math.min(selectedResult.relevance_score, 100)}%` }}
                          />
                        </div>
                        <span className="font-bold text-gray-900">{Math.round(selectedResult.relevance_score)}%</span>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-blue-100">
                      <div className="flex items-start gap-2">
                        <div className="mt-0.5">
                          {selectedResult.search_type === 'SQL' ? (
                            <Target className="h-4 w-4 text-blue-600" />
                          ) : (
                            <Zap className="h-4 w-4 text-blue-600" />
                          )}
                        </div>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-900">
                            {selectedResult.search_type === 'SQL' ? 'Direct Match' : 'Similarity Match'}
                          </p>
                          <p className="text-sm text-gray-600 mt-1">
                            {selectedResult.relevance_comments}
                          </p>
                        </div>
                      </div>
                    </div>

                    {selectedResult.search_type !== 'SQL' && typeof selectedResult.grade_weight === 'number' && selectedResult.grade_weight > 0 && (
                      <div className="pt-2 border-t border-blue-100">
                        <p className="text-sm text-gray-700">
                          <span className="font-medium">Relevant Sections Found:</span> {selectedResult.grade_weight}
                        </p>
                        <p className="text-xs text-gray-600 mt-1">
                          The search query matched {selectedResult.grade_weight} {selectedResult.grade_weight === 1 ? 'section' : 'sections'} within this document. 
                          Each matched section contributes to the overall relevance score.
                        </p>
                      </div>
                    )}
                  </div>
                </div>

                {/* Search Context */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h4 className="font-semibold text-gray-900 mb-2">Search Context</h4>
                  <div className="space-y-2 text-sm">
                    <div>
                      <span className="text-gray-600">Search Query:</span>
                      <span className="ml-2 font-medium">{searchQuery || 'No query (filter only)'}</span>
                    </div>
                    {selectedDrugFilter && (
                      <div>
                        <span className="text-gray-600">Drug Filter:</span>
                        <span className="ml-2 font-medium">{selectedDrugFilter}</span>
                      </div>
                    )}
                    <div>
                      <span className="text-gray-600">Search Type:</span>
                      <span className="ml-2 font-medium">{searchType}</span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={() => openFileUrl(selectedResult.file_url)}
                  >
                    <ExternalLink className="h-4 w-4 mr-1" />
                    View Document
                  </Button>
                  <Button
                    onClick={() => {
                      setShowRelevanceDialog(false);
                      router.push(`/chat?file=${selectedResult.source_file_id}`);
                    }}
                  >
                    <MessageSquare className="h-4 w-4 mr-1" />
                    Chat with Document
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Metadata Modal */}
        {selectedMetadataFile && (
          <MetadataModal
            isOpen={metadataModalOpen}
            onClose={() => {
              setMetadataModalOpen(false);
              setSelectedMetadataFile(null);
            }}
            sourceFileId={selectedMetadataFile.id}
            drugName={selectedMetadataFile.name}
          />
        )}

        {/* Chat Modal */}
        {selectedChatFiles && (
          <ChatModalProfessional
            isOpen={chatModalOpen}
            onClose={() => {
              setChatModalOpen(false);
              setSelectedChatFiles(null);
            }}
            sourceFileIds={selectedChatFiles.ids}
            drugNames={selectedChatFiles.names}
            drugDocuments={selectedChatFiles.drugDocuments}
            collectionName={selectedChatFiles.isCollectionChat && selectedCollection ? collections.find(c => c.id === selectedCollection)?.name : undefined}
            collectionId={selectedChatFiles.isCollectionChat ? selectedCollection : selectedChatFiles.collectionId}
            isDocXChat={true}  // Only document chats use v2 endpoint
            isDashboardCollectionChat={selectedChatFiles.isDashboardCollectionChat}  // Pass the collection chat flag
          />
        )}

      </div>
    </div>
    </TooltipProvider>
  );
} 