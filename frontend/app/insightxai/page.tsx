// Minor update
"use client"

import React, { useState, useRef, useEffect, memo, useCallback } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Search, Bot, User, Sparkles, Clock, Loader2, ArrowUp, Database, Brain, Star, StarOff, TrendingUp } from "lucide-react";
import { apiService, type ChatMessage } from "@/services/api";
import { ChatHistorySidebar } from "@/components/ChatHistorySidebar";
import { useAuth } from "@/hooks/useAuth";
import { useChatHistory } from "@/hooks/useChatHistory";
import type { ChatHistoryItem, FavoriteItem } from "@/hooks/useChatHistory";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ChatModalProfessional } from "@/components/dashboard/ChatModalProfessional";
import { ChevronDown } from "lucide-react";

interface SearchResult {
  source_file_id: number;
  file_name: string;
  file_url: string;
  entity_name: string;
  us_ma_date?: string;
  relevance_score: number;
  relevance_comments: string;
  grade_weight: number;
  search_type?: string;
}

interface Collection {
  id: number;
  name: string;
  description?: string;
  document_count?: number;
}

// Favorites List Component - NOT memoized to ensure proper re-renders
const FavoritesList = ({ 
  favorites, 
  refreshKey, 
  onSelectFavorite 
}: { 
  favorites: FavoriteItem[], 
  refreshKey: number,
  onSelectFavorite: (item: FavoriteItem) => void 
}) => {
  
  // Use the refreshKey to force React to treat this as a new component instance
  return (
    <div className="w-1/2">
      <Card className="shadow-lg border-0 h-[400px] flex flex-col">
        <CardHeader className="bg-gradient-to-r from-green-600 to-green-700 text-white px-6 py-4 flex-shrink-0">
          <CardTitle className="flex items-center gap-2 text-lg">
            <Star className="h-5 w-5" />
            Favorites
          </CardTitle>
        </CardHeader>
        <CardContent className="bg-gray-50 p-6 flex-grow overflow-auto">
          <div className="space-y-3">
            {favorites.length > 0 ? (
              favorites.slice(0, 3).map((item, index) => {
                return (
                  <div 
                    key={`favorite-${item.id}-${refreshKey}`} 
                    className="flex items-center gap-3 p-3 bg-white rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer group"
                    onClick={() => onSelectFavorite(item)}
                  >
                    <div className="flex items-center justify-center h-8 w-8 rounded-full bg-green-600 text-white font-semibold text-sm">
                      {index + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 truncate">
                        {item.query.length > 50 ? `${item.query.substring(0, 50)}...` : item.query}
                      </div>
                      <div className="text-xs text-gray-500">Saved favorite</div>
                    </div>
                    <Star className="h-4 w-4 text-green-600 fill-green-600 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                );
              })
            ) : (
              <div className="text-center py-8">
                <Star className="h-8 w-8 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-600 font-medium">No favorites yet</p>
                <p className="text-sm text-gray-500 mt-1">Star conversations to save them here</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

type CollectionType = 'FDA' | 'EMA' | 'HTA' | 'Other';
type HTACountry = 'Sweden' | 'France' | 'Germany';

const COLLECTION_IDS = {
  FDA: parseInt(process.env.NEXT_PUBLIC_COLLECTION_ID_FDA || '1'),
  EMA: parseInt(process.env.NEXT_PUBLIC_COLLECTION_ID_EMA || '2'),
  HTA_SWEDEN: parseInt(process.env.NEXT_PUBLIC_COLLECTION_ID_HTA_SWEDEN || '3'),
  HTA_FRANCE: parseInt(process.env.NEXT_PUBLIC_COLLECTION_ID_HTA_FRANCE || '4'),
  HTA_GERMANY: parseInt(process.env.NEXT_PUBLIC_COLLECTION_ID_HTA_GERMANY || '5'),
};

export default function InsightXAIPage() {
  const { user } = useAuth();
  const { toggleFavorite, history, favorites, loadFavorites, refreshKey } = useChatHistory(false);
  
  // Force component updates when favorites change
  const [favoritesVersion, setFavoritesVersion] = useState(0);
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [lastResponseUsedSearch, setLastResponseUsedSearch] = useState<boolean>(false);
  const [selectedCollection, setSelectedCollection] = useState<Collection | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollectionType, setSelectedCollectionType] = useState<CollectionType>('FDA');
  const [selectedHTACountry, setSelectedHTACountry] = useState<HTACountry>('Sweden');
  const [otherCollections, setOtherCollections] = useState<Collection[]>([]);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [lastSourceInfo, setLastSourceInfo] = useState<{
    type: string;
    source: string;
    model?: string;
    documents_used?: number;
    description: string;
  } | null>(null);
  const [showSidebar, setShowSidebar] = useState(false);
  const [currentChatId, setCurrentChatId] = useState<number | null>(null);
  const [favoriteStates, setFavoriteStates] = useState<{ [key: string]: boolean }>({});
  const [favoriteLoading, setFavoriteLoading] = useState<{ [key: string]: boolean }>({});
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const [isChatModalOpen, setChatModalOpen] = useState(false);
  const [chatModalProps, setChatModalProps] = useState<any>(null);

  useEffect(() => {
    const fetchCollections = async () => {
      try {
        const response = await apiService.getCollections();
        const allCollections = response.collections || [];
        setCollections(allCollections);
        
        // Filter out predefined collections for 'Other' dropdown
        const predefinedIds = Object.values(COLLECTION_IDS);
        console.log('Predefined IDs to exclude:', predefinedIds);
        console.log('All collections:', allCollections.map(c => ({ id: c.id, name: c.name })));
        
        const otherColls = allCollections.filter(col => !predefinedIds.includes(col.id));
        console.log('Other collections after filtering:', otherColls.map(c => ({ id: c.id, name: c.name })));
        
        setOtherCollections(otherColls);
        
        // Set initial collection based on default selection (FDA) - only on first load
        if (isInitialLoad) {
          const fdaCollection = allCollections.find(col => col.id === COLLECTION_IDS.FDA);
          if (fdaCollection) {
            setSelectedCollection(fdaCollection);
            console.log('FDA collection selected on load:', fdaCollection);
          } else {
            console.warn('FDA collection not found with ID:', COLLECTION_IDS.FDA);
          }
          setIsInitialLoad(false);
        }
      } catch (error) {
        console.error("Failed to fetch collections:", error);
      }
    };
    fetchCollections();
  }, []);
  
  // Update selected collection when type or country changes
  useEffect(() => {
    let targetCollectionId: number;
    
    switch (selectedCollectionType) {
      case 'FDA':
        targetCollectionId = COLLECTION_IDS.FDA;
        break;
      case 'EMA':
        targetCollectionId = COLLECTION_IDS.EMA;
        break;
      case 'HTA':
        targetCollectionId = COLLECTION_IDS[`HTA_${selectedHTACountry.toUpperCase() as 'SWEDEN' | 'FRANCE' | 'GERMANY'}`];
        break;
      case 'Other':
        // For 'Other', collection is set via dropdown
        return;
      default:
        targetCollectionId = COLLECTION_IDS.FDA;
    }
    
    const targetCollection = collections.find(col => col.id === targetCollectionId);
    if (targetCollection) {
      setSelectedCollection(targetCollection);
    }
  }, [selectedCollectionType, selectedHTACountry, collections]);

  // Generate or retrieve session ID
  const generateSessionId = () => {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  };

  // Initialize session on component mount
  useEffect(() => {
    let storedSessionId = localStorage.getItem('insightxai_session_id');
    if (!storedSessionId) {
      storedSessionId = generateSessionId();
      localStorage.setItem('insightxai_session_id', storedSessionId);
    }
    setSessionId(storedSessionId);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Debug: Log favorites changes
  useEffect(() => {
    // Force re-render when favorites change
    setFavoritesVersion(prev => prev + 1);
  }, [favorites]);

  const handleSearch = async () => {
    if (!query.trim() || !selectedCollection) return;
  
    setLoading(true);
    try {
      const collectionDetails = await apiService.getCollectionDetails(selectedCollection.id);
      // Don't pass sourceFileIds - let the backend handle collection-based queries
      const entityNames = collectionDetails.documents.map((doc: any) => doc.entity_name || doc.file_name);
      
      // Create entity documents grouped by entity name
      const entitieDocMap = new Map();
      collectionDetails.documents.forEach((doc: any) => {
        const entityName = doc.entity_name || doc.file_name;
        if (!entitieDocMap.has(entityName)) {
          entitieDocMap.set(entityName, {
            entityName,
            documents: []
          });
        }
        entitieDocMap.get(entityName).documents.push({
          id: doc.id,
          fileName: doc.file_name
        });
      });
      
      const entitieDocuments = Array.from(entitieDocMap.values())
        .sort((a, b) => a.entityName.localeCompare(b.entityName));
  
      setChatModalProps({
        isOpen: true,
        onClose: () => setChatModalOpen(false),
        sourceFileIds: [],  // Pass empty array for collection-based queries
        entityNames,
        entitieDocuments,  // Pass the grouped entity documents
        initialMessage: query,
        collectionName: selectedCollection.name,
        collectionId: selectedCollection.id,
        isDocXChat: false,
        isCollectionChat: true,
        isDashboardCollectionChat: false,
        globalSearch: true, // Add global_search parameter
      });
      setChatModalOpen(true);
    } catch (error) {
      console.error("Failed to open chat modal:", error);
      setError("Failed to load collection details for chat.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleNewChat = () => {
    setMessages([]);
    setSearchResults([]);
    setError(null);
    setShowChat(false);
    setQuery("");
    setLastResponseUsedSearch(false);
    setLastSourceInfo(null);
    setShowSidebar(false);
    setCurrentChatId(null);
    setFavoriteStates({});
    setFavoriteLoading({});
    
    // Generate new session ID for new chat
    const newSessionId = generateSessionId();
    localStorage.setItem('insightxai_session_id', newSessionId);
    setSessionId(newSessionId);
  };

  const handleSelectHistory = (historyItem: ChatHistoryItem) => {
    // This function might need to be adapted to work with the modal
    // For now, it will open the old chat UI
    const userMessage: ChatMessage = {
      id: `${historyItem.id}-user`,
      content: historyItem.query,
      role: "user",
      timestamp: new Date(historyItem.created_at),
    };

    const assistantMessage: ChatMessage = {
      id: `${historyItem.id}-assistant`,
      content: historyItem.response || "Response not available",
      role: "assistant", 
      timestamp: new Date(historyItem.created_at),
    };

    setMessages([userMessage, assistantMessage]);
    setQuery("");
    setSearchResults([]);
    setError(null);
    setShowChat(true);
    setLastResponseUsedSearch(false);
    setLastSourceInfo(null);
    
    setCurrentChatId(historyItem.id);
    
    setFavoriteStates(prev => ({
      ...prev,
      [historyItem.id]: historyItem.is_favorite
    }));
  };

  const handleSelectFavorite = useCallback((favoriteItem: FavoriteItem) => {
    const historyItem: ChatHistoryItem = {
      id: favoriteItem.id,
      session_id: favoriteItem.session_id,
      query: favoriteItem.query,
      response: "Loading response...",
      created_at: new Date().toISOString(),
      is_favorite: true
    };
    handleSelectHistory(historyItem);
  }, [handleSelectHistory]);

  const handleLoadQuery = (queryText: string) => {
    setQuery(queryText);
    setTimeout(() => {
      inputRef.current?.focus();
    }, 100);
  };

  // This function is no longer used with the modal, but we'll keep it for now
  const handleToggleFavorite = async (messageId: string, currentQuery: string) => {
    if (!user?.id || !currentChatId) return;
    
    setFavoriteLoading(prev => ({ ...prev, [messageId]: true }));
    try {
      const currentFavoriteState = favoriteStates[currentChatId] || false;
      const newFavoriteState = !currentFavoriteState;
      
      setFavoriteStates(prev => ({ ...prev, [currentChatId]: newFavoriteState }));
      
      const success = await toggleFavorite(currentChatId, newFavoriteState, currentQuery);
      
      if (success) {
        setFavoritesVersion(prev => prev + 1);
      } else {
        setFavoriteStates(prev => ({ ...prev, [currentChatId]: currentFavoriteState }));
      }
    } catch (error) {
      console.error("Failed to toggle favorite:", error);
    } finally {
      setFavoriteLoading(prev => ({ ...prev, [messageId]: false }));
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="container mx-auto px-4 py-8 transition-all duration-500 ease-in-out">
      <h1 className="text-5xl font-bold text-center page-title mb-2">InsightXAI</h1>
      <h2 className="text-xl font-semibold text-center text-muted-foreground mb-8">
        Conversational AI for Pharmaceutical Insights
      </h2>
      <div className="card-tech p-8 mb-8">
        <h3 className="text-2xl font-bold text-center mb-4 text-foreground">Start a Conversation</h3>
        <p className="text-center text-muted-foreground mb-6 max-w-3xl mx-auto">
          Select your preferred regulatory database (FDA, EMA, HTA, or other collections) and ask questions to receive AI-powered insights from official pharmaceutical documents. Our system searches across comprehensive entity labels, clinical data, and regulatory information to provide accurate, context-aware answers.
        </p>
        
        {/* Collection Selection Section */}
        <div className="mb-8">
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {/* Collection Pills */}
            <div className="flex items-center gap-2">              
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedCollectionType('FDA')}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    selectedCollectionType === 'FDA'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  FDA
                </button>
                <button
                  onClick={() => setSelectedCollectionType('EMA')}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    selectedCollectionType === 'EMA'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  EMA
                </button>
                <button
                  onClick={() => setSelectedCollectionType('HTA')}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    selectedCollectionType === 'HTA'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  HTA
                </button>
                <button
                  onClick={() => setSelectedCollectionType('Other')}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                    selectedCollectionType === 'Other'
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-300'
                  }`}
                >
                  Other
                </button>
              </div>
            </div>
            
            {/* Conditional Dropdowns with document count */}
            <div className="flex items-center gap-3 min-w-[300px]">
              {selectedCollectionType === 'HTA' && (
                <>
                  <div className="flex items-center gap-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    <ChevronDown className="h-4 w-4 text-gray-500" />
                    <Select value={selectedHTACountry} onValueChange={(value) => setSelectedHTACountry(value as HTACountry)}>
                      <SelectTrigger className="w-40 bg-white">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="Sweden">Sweden</SelectItem>
                        <SelectItem value="France">France</SelectItem>
                        <SelectItem value="Germany">Germany</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  {selectedCollection && (
                    <div className="text-sm text-gray-600 font-medium">
                      {selectedCollection.document_count !== undefined 
                        ? `(${selectedCollection.document_count} docs)`
                        : ''}
                    </div>
                  )}
                </>
              )}
              
              {selectedCollectionType === 'Other' && (
                <>
                  <div className="flex items-center gap-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    <ChevronDown className="h-4 w-4 text-gray-500" />
                    <Select 
                      value={selectedCollection?.id.toString()} 
                      onValueChange={(value) => {
                        const collection = otherCollections.find(col => col.id === parseInt(value));
                        if (collection) {
                          setSelectedCollection(collection);
                        }
                      }}
                    >
                      <SelectTrigger className="w-48 bg-white">
                        <SelectValue placeholder="Select a collection" />
                      </SelectTrigger>
                      <SelectContent>
                        {otherCollections.map((collection) => (
                          <SelectItem key={collection.id} value={collection.id.toString()}>
                            {collection.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {selectedCollection && (
                    <div className="text-sm text-gray-600 font-medium">
                      {selectedCollection.document_count !== undefined 
                        ? `(${selectedCollection.document_count} docs)`
                        : ''}
                    </div>
                  )}
                </>
              )}
              
              {/* Show document count for FDA/EMA when no dropdown is visible */}
              {(selectedCollectionType === 'FDA' || selectedCollectionType === 'EMA') && selectedCollection && (
                <div className="text-sm text-gray-600 font-medium">
                  {selectedCollection.document_count !== undefined 
                    ? `${selectedCollection.document_count} document${selectedCollection.document_count !== 1 ? 's' : ''}`
                    : 'Loading...'}
                </div>
              )}
            </div>
          </div>
        </div>
        
        {/* Search Input Section */}
        <div className="flex flex-col items-center">
          <div className="flex gap-4 justify-center max-w-3xl w-full">
            <div className="flex-1 relative">
              <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
              <Input
                ref={inputRef}
                type="text"
                placeholder={`Ask about ${selectedCollection?.name || 'pharmaceutical'} documents...`}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                className="pl-12 pr-4 py-3.5 text-base rounded-xl border-2 border-gray-200 bg-white focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all duration-200 shadow-sm hover:shadow-md"
              />
            </div>
            <Button 
              onClick={handleSearch}
              disabled={!query.trim() || !selectedCollection || loading}
              className="px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-medium transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed shadow-md hover:shadow-lg"
            >
              {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <><Search className="inline h-5 w-5 mr-2" />Start Chat</>}
            </Button>
          </div>
          {selectedCollection && (
            <p className="text-sm text-gray-500 mt-3">
              Searching in: <span className="font-medium text-gray-700">{selectedCollection.name}</span>
              {selectedCollection.document_count !== undefined && (
                <span className="ml-1">• {selectedCollection.document_count} document{selectedCollection.document_count !== 1 ? 's' : ''}</span>
              )}
            </p>
          )}
        </div>
      </div>
      
      {/* Recent History and Favorites */}
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
              </CardTitle>
            </CardHeader>
            <CardContent className="bg-gray-50 p-6 flex-grow overflow-auto">
              {history.length === 0 ? (
                <div className="text-center py-8">
                  <Clock className="h-8 w-8 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-600 font-medium">No recent history</p>
                  <p className="text-sm text-gray-500 mt-1">Start a conversation to see your history here</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {history.slice(0, 4).map((item) => (
                    <div 
                      key={`history-${item.id}`} 
                      className="flex items-center gap-3 p-3 bg-white rounded-lg hover:shadow-md transition-all duration-200 cursor-pointer group"
                      onClick={() => handleSelectHistory(item)}
                    >
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

        {/* Favorites - key forces re-mount when favorites change */}
        <FavoritesList 
          key={`favorites-list-${refreshKey}-${favorites.length}-${favoritesVersion}`}
          favorites={favorites} 
          refreshKey={refreshKey} 
          onSelectFavorite={handleSelectFavorite} 
        />
      </div>
      </div>
      {isChatModalOpen && chatModalProps && (
        <ChatModalProfessional {...chatModalProps} />
      )}
    </div>
  );
} 