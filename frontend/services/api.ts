import { API_BASE_URL } from '@/config/api'

export interface Entity {
  id: string;
  name: string;
  type?: string;
  description?: string;
  relevance_score?: number;
  last_updated?: string;
  // Add other entity properties as needed
}

export interface SourceDocument {
  id: string
  source: string
  file_name: string
  chunk_id?: string
  page_content_preview: string
  relevance_score?: number
  metadata?: Record<string, any>
}

export interface EnhancedSourceDocument {
  id: string
  filename: string
  snippet: string
  citation_number: number
  relevance_score: number
  page_number?: number
  entity_name?: string
  metadata?: {
    original_content?: string
    file_url?: string
    [key: string]: any
  }
}

export interface QueryResponse {
  user_query: string
  response: string
  query_type: "collection" | "documents"
  collection_id?: number
  collection_name?: string
  source_documents?: SourceDocument[]
  content_type?: "html" | "markdown"
  chat_id?: number
}

export interface EnhancedQueryResponse extends QueryResponse {
  cited_response?: string
  source_documents?: EnhancedSourceDocument[]
  intent?: string
  conversation_summary?: string
  enhanced_query?: string
  confidence_scores?: {
    retrieval_confidence: number
    citation_coverage: number
    intent_confidence: number
  }
}

export interface Entity {
  id: string
  source_file_id?: number
  name: string
  brand?: string
  source?: string
  therapeuticArea?: string
  category?: string
  description: string
  timeline: TimelineEvent[]
  sections: EntitySection[]
  isBookmarked?: boolean
}

export interface EntitySection {
  id?: string
  type: string
  title: string
  content: string
}

export interface TimelineEvent {
  date: string
  event: string
  phase: string
}

export interface ChatMessage {
  id: string
  content: string
  role: "user" | "assistant"
  timestamp: Date
  entityId?: string
  entityIds?: string[]
  contentType?: "markdown" | "html"
  sourceInfo?: {
    type: "document_based" | "llm_based" | "error"
    source: string
    model?: string
    documents_used?: number
    description?: string
  }
  source_documents?: SourceDocument[] | EnhancedSourceDocument[]
  // Enhanced fields
  cited_content?: string
  intent?: string
  conversation_summary?: string
  enhanced_query?: string
  confidence_scores?: {
    retrieval_confidence: number
    citation_coverage: number
    intent_confidence: number
  }
  searchResults?: Array<{
    source_file_id: number
    file_name: string
    file_url: string
    entity_name: string
    us_ma_date?: string
    relevance_score: number
    relevance_comments: string
    grade_weight: number
    search_type?: string
  }>
  usedDocuments?: boolean
}

export interface SearchResult {
  entities: Entity[]
  total: number
}

// Enhanced interfaces for entity details
export interface EntityDetailsSection {
  id: number
  type: string
  title: string
  content: string
  order: number
}

export interface EntityDetails {
  basic_info: {
    id: number
    entity_name: string
    therapeutic_area?: string
    approval_status: string
    country: string
    applicant: string
    active_substance: any
    regulatory: string
  }
  timeline: {
    submission_date?: string
    pdufa_date?: string
    approval_date?: string
  }
  sections: EntityDetailsSection[]
  page_info?: {
    total_pages: number
    page_numbers: number[]
    total_chunks: number
    total_tokens: number
  }
  file_url?: string
  metadata?: any
}

export interface DualSearchRequest {
  brand_name?: string
  therapeutic_area?: string
  collection_id?: number
  filters?: Record<string, any>
}

export interface DualSearchResult {
  results: Array<{
    id: number
    source_file_id: number
    entity_name: string
    therapeutic_area: string
    manufacturer: string
    approval_status: string
    approval_date: string
    country: string
    active_ingredients: any
    regulatory_info: string
    document_type: string
    relevance_score: number
  }>
  total_count: number
  execution_time_ms: number
  search_criteria: {
    brand_name?: string
    therapeutic_area?: string
    filters?: Record<string, any>
  }
}

// Source Files interfaces
export interface SourceFileResponse {
  id: number
  file_name: string
  file_url: string
  entity_name?: string
  status: string
  comments?: string
  us_ma_date?: string
  created_by?: number
  created_at: string
  updated_at: string
  file_size?: string
  file_type?: string
  processing_progress?: number
  error_message?: string
  extraction_count?: number
  creator_username?: string
}

export interface SourceFileCreate {
  file_name: string
  file_url: string
  entity_name?: string
  comments?: string
  us_ma_date?: string
  status?: string
  collection_id?: number
}

export interface SourceFileUpdate {
  file_name?: string
  file_url?: string
  entity_name?: string
  status?: string
  comments?: string
  us_ma_date?: string
}

export interface SourceFilesListResponse {
  source_files: SourceFileResponse[]
  total_count: number
  limit: number
  offset: number
}

class ApiService {
  private getAuthHeaders(): Record<string, string> {
    // Get JWT token from localStorage
    const token = localStorage.getItem('access_token')
    
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    return headers
  }

  private getAuthHeadersWithoutContentType(): Record<string, string> {
    // Get JWT token from localStorage (for file uploads)
    const token = localStorage.getItem('access_token')
    
    const headers: Record<string, string> = {}
    
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    
    return headers
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    let response = await fetch(`${API_BASE_URL}${endpoint}`, {
      headers: {
        ...this.getAuthHeaders(),
        ...options?.headers,
      },
      ...options,
    })
    
    // Debug logging for authentication issues
    if (response.status === 401) {
      console.log('🔒 Authentication error on endpoint:', endpoint);
      console.log('🔒 Token present:', !!localStorage.getItem('access_token'));
      console.log('🔒 Refresh token present:', !!localStorage.getItem('refresh_token'));
    }

    // If we get a 401 (Unauthorized), try to refresh the token
    if (response.status === 401) {
      const refreshToken = localStorage.getItem('refresh_token')
      
      if (refreshToken) {
        try {
          console.log('🔄 API request got 401, attempting token refresh...')
          
          // Attempt to refresh the access token
          const refreshResponse = await fetch(`${API_BASE_URL}/api/auth/refresh-token`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams({ refresh_token: refreshToken }),
          })

          if (refreshResponse.ok) {
            const tokenData = await refreshResponse.json()
            console.log('✅ Token refresh successful')
            
            // Update stored tokens
            localStorage.setItem('access_token', tokenData.access_token)
            if (tokenData.refresh_token) {
              localStorage.setItem('refresh_token', tokenData.refresh_token)
            }

            console.log('🔄 Retrying original request with new token...')
            // Retry the original request with the new token
            response = await fetch(`${API_BASE_URL}${endpoint}`, {
              headers: {
                ...this.getAuthHeaders(), // This will now use the new token
                ...options?.headers,
              },
              ...options,
            })
            
            if (response.ok) {
              console.log('✅ Original request succeeded after token refresh')
            }
          } else {
            console.log('❌ Token refresh failed, redirecting to login')
            // Refresh failed, clear tokens and redirect to login
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            localStorage.removeItem('user_data')
            
            // Trigger a custom event that the auth hook can listen to
            window.dispatchEvent(new CustomEvent('auth:logout', { 
              detail: { reason: 'Token refresh failed' } 
            }))
            
            // Redirect to login page
            if (typeof window !== 'undefined') {
              window.location.href = '/auth/login?reason=session_expired'
            }
            throw new Error('Session expired. Please log in again.')
          }
        } catch (refreshError) {
          console.log('❌ Token refresh error:', refreshError)
          // Refresh failed, clear tokens and redirect to login
          localStorage.removeItem('access_token')
          localStorage.removeItem('refresh_token')
          localStorage.removeItem('user_data')
          
          // Trigger a custom event that the auth hook can listen to
          window.dispatchEvent(new CustomEvent('auth:logout', { 
            detail: { reason: 'Token refresh error' } 
          }))
          
          // Redirect to login page
          if (typeof window !== 'undefined') {
            window.location.href = '/auth/login?reason=session_expired'
          }
          throw new Error('Session expired. Please log in again.')
        }
      } else {
        console.log('❌ No refresh token available, redirecting to login')
        // No refresh token available, redirect to login
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('user_data')
        
        // Trigger a custom event that the auth hook can listen to
        window.dispatchEvent(new CustomEvent('auth:logout', { 
          detail: { reason: 'No refresh token' } 
        }))
        
        if (typeof window !== 'undefined') {
          window.location.href = '/auth/login?reason=auth_required'
        }
        throw new Error('Authentication required. Please log in.')
      }
    }

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication failed. Please log in again.')
      }
      
      // Try to parse error message from response body
      let errorMessage = `API Error: ${response.status} ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : JSON.stringify(errorData.detail);
        } else if (errorData.message) {
          errorMessage = errorData.message;
        } else if (errorData.error) {
          errorMessage = errorData.error;
        }
      } catch (e) {
        // If parsing fails, use the default error message
        console.error('Failed to parse error response:', e);
      }
      
      const error = new Error(errorMessage);
      (error as any).status = response.status;
      (error as any).response = { status: response.status };
      throw error;
    }

    return response.json()
  }

  // Enhanced search with dual search functionality
  async dualSearch(request: DualSearchRequest): Promise<DualSearchResult> {
    return this.request<DualSearchResult>("/api/v1/search/dual", {
      method: "POST",
      body: JSON.stringify(request),
    })
  }

  // Get comprehensive entity details
  async getEntityDetails(entityId: string): Promise<EntityDetails> {
    return this.request<EntityDetails>(`/api/entities/${entityId}/details`)
  }

  // Download entity PDF document
  async downloadEntityPDF(entityId: string): Promise<Blob> {
    const response = await fetch(`${API_BASE_URL}/api/documents/download/${entityId}`, {
      headers: this.getAuthHeaders(),
    })
    
    if (!response.ok) {
      throw new Error(`Download Error: ${response.statusText}`)
    }
    
    return response.blob()
  }

  // Get search suggestions for autocomplete
  async getSearchSuggestions(query: string, searchType: 'brand' | 'therapeutic'): Promise<string[]> {
    const params = new URLSearchParams({ query, type: searchType })
    const result = await this.request<{ suggestions: string[] }>(`/api/search/suggestions?${params}`)
    return result.suggestions
  }

  // Get advanced filter options
  async getAdvancedFilters(): Promise<Record<string, any>> {
    return this.request<Record<string, any>>("/api/search/filters")
  }

  // Search entities (legacy method for backward compatibility)
  async searchEntities(query: string, filters?: { therapeuticArea?: string }): Promise<SearchResult> {
    // Convert to dual search format
    const searchRequest: DualSearchRequest = {
      brand_name: query,
      therapeutic_area: filters?.therapeuticArea,
      filters: filters
    }
    
    const result = await this.dualSearch(searchRequest)
    
    // Convert to legacy format
    return {
      entities: result.results.map(item => ({
        id: item.id.toString(),
        source_file_id: item.source_file_id,
        name: item.entity_name,
        brand: item.entity_name,
        therapeuticArea: item.therapeutic_area,
        description: item.therapeutic_area,
        timeline: [],
        sections: [],
        isBookmarked: false
      })),
      total: result.total_count
    }
  }

  // Get entity details (legacy method)
  async getEntity(id: string): Promise<Entity> {
    const details = await this.getEntityDetails(id)
    
    return {
      id: details.basic_info.id.toString(),
      name: details.basic_info.entity_name,
      brand: details.basic_info.entity_name,
      therapeuticArea: details.basic_info.therapeutic_area || '',
      description: details.basic_info.therapeutic_area || '',
      timeline: [],
      sections: details.sections.map(section => ({
        id: section.id.toString(),
        title: section.title,
        content: section.content,
        type: section.type as any
      })),
      isBookmarked: false
    }
  }

  // Analytics and history
  async getUserSearchHistory(limit: number = 10): Promise<any[]> {
    try {
      const params = new URLSearchParams({ limit: limit.toString() })
      const result = await this.request<{ history: any[] }>(`/api/analytics/history?${params}`)
      return result.history
    } catch (error) {
      console.warn('getUserSearchHistory endpoint not available:', error)
      return [] // Return empty array as fallback
    }
  }

  async getTrendingSearches(period: 'daily' | 'weekly' | 'monthly' = 'weekly', limit: number = 10): Promise<any[]> {
    try {
      const params = new URLSearchParams({ period, limit: limit.toString() })
      const result = await this.request<{ trending: any[] }>(`/api/analytics/trending?${params}`)
      return result.trending
    } catch (error) {
      console.warn('getTrendingSearches endpoint not available:', error)
      return [] // Return empty array as fallback
    }
  }

  async getDashboardData(): Promise<{
    total_entities: number;
    total_manufacturers: number;
    recent_approvals: number;
    total_searches: number;
    additional_stats?: {
      total_source_files: number;
      processed_files: number;
      total_metadata_entries: number;
      recent_searches_7d: number;
      trending_entities: Array<{ entity_name: string; search_count: number }>;
      top_entities: Array<{ name: string; count: number }>;
      top_manufacturers: Array<{ name: string; count: number }>;
      recent_activity?: Array<{
        id: string;
        type: string;
        timestamp: string;
        query?: string;
        entityName?: string;
      }>;
    };
    last_updated: string;
  }> {
    try {
      // Use the new dashboard stats endpoint
      const response = await this.request<any>("/api/dashboard/stats")
      console.log('📊 Dashboard stats response:', response);
      
      // Map the response to expected format
      return {
        total_entities: response.total_entities || 0,
        total_manufacturers: response.total_manufacturers || response.manufacturers_count || 0,
        recent_approvals: response.recent_approvals || 0,
        total_searches: response.total_searches || 0,
        additional_stats: {
          total_source_files: response.total_source_files || response.total_entities || 0,
          processed_files: response.processed_files || 0,
          total_metadata_entries: response.total_metadata_entries || response.total_sections || 0,
          recent_searches_7d: response.recent_searches_7d || response.recent_activity?.searches_last_7_days || 0,
          trending_entities: response.additional_stats?.trending_entities || response.trending_entities || [],
          top_entities: response.top_entities || [],
          top_manufacturers: response.top_manufacturers || [],
          recent_activity: response.additional_stats?.recent_activity || response.recent_activities || []
        },
        last_updated: response.last_updated || response.recent_activity?.last_updated || new Date().toISOString()
      }
    } catch (error) {
      console.warn('Dashboard stats endpoint error:', error)
      // Return default values if endpoint fails
      return {
        total_entities: 0,
        total_manufacturers: 0,
        recent_approvals: 0,
        total_searches: 0,
        last_updated: new Date().toISOString()
      }
    }
  }

  async getSearchStatistics(): Promise<any> {
    return this.request<any>("/api/search/stats")
  }

  // Get trending entities
  async getTrendingEntities(): Promise<Entity[]> {
    return this.request<Entity[]>("/entities/trending");
  }

  // Keep the old method for backward compatibility
  async getTrendingEntities(): Promise<Entity[]> {
    return this.getTrendingEntities() as unknown as Promise<Entity[]>;
  }

  // Chat with AI
  async sendUnifiedChatMessage(requestPayload: { 
    message: string; 
    session_id?: string; 
    user_id?: number;
    agency?: 'FDA' | 'EMA' | 'HTA';
    country?: 'Sweden' | 'France' | 'Germany';
  }): Promise<{
    id: string;
    content: string;
    role: string;
    timestamp: string;
    chat_id: number;
    content_type?: string;
    search_results?: Array<{
      source_file_id: number;
      file_name: string;
      file_url: string;
      entity_name: string;
      us_ma_date?: string;
      relevance_score: number;
      relevance_comments: string;
      grade_weight: number;
      search_type?: string;
    }>;
    used_documents: boolean;
    source_info?: {
      type: string;
      source: string;
      model?: string;
      documents_used?: number;
      description: string;
    };
  }> {
    console.log('apiService.sendUnifiedChatMessage called with:', requestPayload);
    
    const url = `${API_BASE_URL}/api/chat/unified`;
    console.log('Full URL:', url);
    
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(requestPayload)
      });

      if (!response.ok) {
        let errorText = '';
        try {
          errorText = await response.text();
        } catch (e) {
          errorText = 'Unable to parse error response';
        }
        
        console.error('API Error Response:', 
          `Status: ${response.status}`,
          `URL: ${url}`,
          `Error: ${errorText || response.statusText}`
        );
        
        throw new Error(`HTTP error! status: ${response.status} - ${errorText || response.statusText}`);
      }

      const data = await response.json();
      console.log('Unified Chat API Response:', data);
      return data;
      
    } catch (error) {
      console.error('Fetch error:', error);
      throw error;
    }
  }

  async sendChatMessage(requestPayload: { 
    message: string; 
    entityId?: number; 
    entityIds?: number[]; 
    source_file_id?: number; 
    source_file_ids?: number[]; 
    collection_id?: number;
    docXChat?: boolean;  // Dashboard document chat flag
    collectionChat?: boolean;  // Collection page chat flag
    isDashboardCollectionChat?: boolean;  // Dashboard collection chat flag
  }): Promise<ChatMessage> {
    console.log('apiService.sendChatMessage called with:', requestPayload);
    
    // Determine endpoint based on query type
    let endpoint: string;
    let payload: any;
    
    // Ensure we have a valid session ID
    const sessionId = localStorage.getItem('session_id') || this.generateSessionId();
    
    // Get user data from localStorage
    const userData = localStorage.getItem('user_data');
    let userId = 1; // Default fallback
    if (userData) {
      try {
        const user = JSON.parse(userData);
        userId = user.id || 1;
      } catch (e) {
        console.warn('Failed to parse user data:', e);
      }
    }
    

    // Route based on source flags
    if (requestPayload.isDashboardCollectionChat) {
      // Dashboard collection chat - use old endpoint
      endpoint = '/api/chat/query-multiple';
      payload = { 
        query: requestPayload.message,
        collection_id: requestPayload.collection_id,
        session_id: sessionId,
        user_id: userId,
        docXChat: requestPayload.docXChat || false
      };
      // Include source file IDs if provided (for collection with specific documents)
      if (requestPayload.source_file_ids && requestPayload.source_file_ids.length > 0) {
        payload.source_file_ids = requestPayload.source_file_ids;
      }
      // Include global_search flag if provided
      if (requestPayload.global_search) {
        payload.global_search = requestPayload.global_search;
      }
    } else if (requestPayload.docXChat) {
      // Dashboard document chat - use v2 endpoint
      console.log('Dashboard document chat (docXChat): Using v2 endpoint');
      endpoint = '/api/chat/query-multiple';
      payload = { 
        query: requestPayload.message,
        session_id: sessionId,
        user_id: userId,
        docXChat: true  // Send docXChat flag
      };
      // Include source file IDs
      if (requestPayload.source_file_ids && requestPayload.source_file_ids.length > 0) {
        payload.source_file_ids = requestPayload.source_file_ids;
      }
      // Always include collection_id for context
      if (requestPayload.collection_id !== undefined && requestPayload.collection_id !== null) {
        payload.collection_id = requestPayload.collection_id;
      }
      // Include global_search flag if provided
      if (requestPayload.global_search) {
        payload.global_search = requestPayload.global_search;
      }
    } else if (requestPayload.collectionChat) {
      // Collection page chat - use old endpoint
      console.log('Collection chat: Using old query-multiple endpoint');
      endpoint = '/api/chat/query-multiple';
      payload = { 
        query: requestPayload.message,
        collection_id: requestPayload.collection_id,
        session_id: sessionId,
        user_id: userId
      };
      // Include source file IDs if provided
      if (requestPayload.source_file_ids && requestPayload.source_file_ids.length > 0) {
        payload.source_file_ids = requestPayload.source_file_ids;
      }
      // Include global_search flag if provided
      if (requestPayload.global_search) {
        payload.global_search = requestPayload.global_search;
      }
    }
    
    console.log('Using endpoint:', endpoint);
    console.log('Sending payload:', payload);
    
    const url = `${API_BASE_URL}${endpoint}`;
    console.log('Full URL:', url);
    
    let response;
    try {
      response = await fetch(url, {
        method: 'POST',
        headers: this.getAuthHeaders(),
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        let errorText = '';
        try {
          errorText = await response.text();
        } catch (e) {
          errorText = 'Unable to parse error response';
        }
        
        console.error('API Error Response:', 
          `Status: ${response.status}`,
          `URL: ${url}`,
          `Error: ${errorText || response.statusText}`
        );
        
        throw new Error(`HTTP error! status: ${response.status} - ${errorText || response.statusText}`);
      }
    } catch (error) {
      console.error('Fetch error:', error);
      throw error;
    }

    let data;
    try {
      data = await response.json();
      console.log('Chat API Response:', data);
    } catch (error) {
      console.error('Failed to parse JSON response:', error);
      throw new Error('Invalid response format from server');
    }
    
    // Transform query endpoint responses to match ChatMessage interface
    if (requestPayload.source_file_id || requestPayload.source_file_ids || (requestPayload.collection_id !== undefined && requestPayload.collection_id !== null)) {
      // Check if we have the expected response structure
      if (!data.response) {
        console.error('Unexpected response structure:', data);
        throw new Error('Invalid response structure from chat API');
      }
      
      return {
        id: data.chat_id?.toString() || Date.now().toString(),
        content: data.response,
        role: 'assistant',
        timestamp: new Date(),
        entityId: data.source_file_id?.toString(),
        entityIds: data.source_file_ids?.map((id: number) => id.toString()),
        contentType: data.content_type || "markdown",
        source_documents: data.source_documents || [],
        // Enhanced fields with fallbacks
        intent: data.intent,
        conversation_summary: data.conversation_summary,
        enhanced_query: data.enhanced_query,
        confidence_scores: data.confidence_scores
      };
    }
    
    return data;
  }

  private generateSessionId(): string {
    const sessionId = crypto.randomUUID();
    localStorage.setItem('session_id', sessionId);
    return sessionId;
  }

  // Advanced search
  async advancedSearch(params: {
    query: string;
    session_id?: string;
    user_id?: number;
  }): Promise<any> {
    return this.request<any>(`/api/chat/search/advanced`, {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  // Get chat history
  async getChatHistory(entityId?: string): Promise<ChatMessage[]> {
    const params = entityId ? `?entityId=${entityId}` : ""
    return this.request<ChatMessage[]>(`/api/chat/history${params}`)
  }

  // Bookmark management
  async toggleBookmark(entityId: string): Promise<{ bookmarked: boolean }> {
    return this.request<{ bookmarked: boolean }>(`/bookmarks/${entityId}`, {
      method: "POST",
    })
  }

  async getBookmarks(): Promise<Entity[]> {
    return this.request<Entity[]>("/bookmarks")
  }

  // Search history
  async getSearchHistory(): Promise<string[]> {
    return this.request<string[]>("/api/analytics/history")
  }

  // Get all source files with filtering and pagination
  async getSourceFiles(params?: {
    status?: string
    search?: string
    limit?: number
    offset?: number
    exclude_collection?: number
  }): Promise<SourceFilesListResponse> {
    const queryParams = new URLSearchParams()
    
    if (params?.status) queryParams.append('status', params.status)
    if (params?.search) queryParams.append('search', params.search)
    if (params?.limit) queryParams.append('limit', params.limit.toString())
    if (params?.offset) queryParams.append('offset', params.offset.toString())
    if (params?.exclude_collection !== undefined) queryParams.append('exclude_collection', params.exclude_collection.toString())
    
    const endpoint = `/api/source-files${queryParams.toString() ? `?${queryParams.toString()}` : ''}`
    return this.request<SourceFilesListResponse>(endpoint)
  }

  // Create a new source file
  async createSourceFile(sourceFileData: SourceFileCreate): Promise<SourceFileResponse> {
    return this.request<SourceFileResponse>("/api/source-files", {
      method: "POST",
      body: JSON.stringify(sourceFileData),
    })
  }

  // Get a specific source file by ID
  async getSourceFile(fileId: number): Promise<SourceFileResponse> {
    return this.request<SourceFileResponse>(`/api/source-files/${fileId}`)
  }

  // Update a source file
  async updateSourceFile(fileId: number, sourceFileData: SourceFileUpdate): Promise<SourceFileResponse> {
    return this.request<SourceFileResponse>(`/api/source-files/${fileId}`, {
      method: "PUT",
      body: JSON.stringify(sourceFileData),
    })
  }

  // Delete a source file
  async deleteSourceFile(fileId: number): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(`/api/source-files/${fileId}`, {
      method: "DELETE",
    })
  }

  // Process a single source file
  async processSourceFile(fileId: number): Promise<{ success: boolean; message: string; file_id: number; status: string }> {
    return this.request<{ success: boolean; message: string; file_id: number; status: string }>(`/api/source-files/${fileId}/process`, {
      method: "POST",
    })
  }

  // Index a processed source file to vector database
  async indexSourceFile(fileId: number): Promise<{ success: boolean; message: string; file_id: number; status: string }> {
    return this.request<{ success: boolean; message: string; file_id: number; status: string }>(`/api/source-files/${fileId}/index`, {
      method: "POST",
    })
  }

  // Reprocess a source file by clearing data and restarting processing
  async reprocessSourceFile(fileId: number): Promise<{ success: boolean; message: string; file_id: number; status: string }> {
    return this.request<{ success: boolean; message: string; file_id: number; status: string }>(`/api/source-files/${fileId}/reprocess`, {
      method: "POST",
    })
  }

  // Delete vector database documents for a source file
  async deleteSourceFileVectorDB(fileId: number): Promise<{ 
    success: boolean; 
    message: string; 
    deleted_count: number;
    source_file_name: string;
    file_id: number;
    new_status: string;
  }> {
    return this.request<{ 
      success: boolean; 
      message: string; 
      deleted_count: number;
      source_file_name: string;
      file_id: number;
      new_status: string;
    }>(`/api/source-files/${fileId}/vectordb`, {
      method: "DELETE",
    })
  }

  // Get vector database document count for a source file
  async getSourceFileVectorDBCount(fileId: number): Promise<{
    success: boolean;
    source_file_name: string;
    file_id: number;
    document_count: number;
  }> {
    return this.request<{
      success: boolean;
      source_file_name: string;
      file_id: number;
      document_count: number;
    }>(`/api/source-files/${fileId}/vectordb/count`)
  }

  // Bulk process multiple source files
  async bulkProcessSourceFiles(fileIds: number[]): Promise<{ 
    success: boolean; 
    message: string; 
    processed_files: string[];
    total_requested: number;
    total_processed: number;
  }> {
    return this.request<{ 
      success: boolean; 
      message: string; 
      processed_files: string[];
      total_requested: number;
      total_processed: number;
    }>("/api/source-files/bulk-process", {
      method: "POST",
      body: JSON.stringify({ file_ids: fileIds }),
    })
  }

  // Process multiple source files sequentially
  async processSourceFilesSequential(fileIds: number[]): Promise<{ 
    success: boolean; 
    message: string; 
    processing_files: Array<{
      id: number;
      file_name: string;
      entity_name?: string;
    }>;
    total_requested: number;
    total_queued: number;
  }> {
    return this.request<{ 
      success: boolean; 
      message: string; 
      processing_files: Array<{
        id: number;
        file_name: string;
        entity_name?: string;
      }>;
      total_requested: number;
      total_queued: number;
    }>("/api/source-files/process-sequential", {
      method: "POST",
      body: JSON.stringify({ file_ids: fileIds }),
    })
  }

  // Get source files statistics
  async getSourceFilesStats(): Promise<{
    total_files: number
    recent_files: number
    status_distribution: Record<string, number>
    user_file_counts: number
    stats_generated_at: string
  }> {
    return this.request<{
      total_files: number
      recent_files: number
      status_distribution: Record<string, number>
      user_file_counts: number
      stats_generated_at: string
    }>("/api/source-files/stats")
  }

  // ============================
  // Search Operations
  // ============================

  // Search documents
  async searchDocuments(
    query: string, 
    entityName?: string, 
    collectionId?: number, 
    sourceFileId?: number,
    page: number = 1,
    pageSize: number = 20
  ): Promise<{
    success: boolean;
    results: Array<{
      source_file_id: number;
      file_name: string;
      file_url: string;
      entity_name: string;
      us_ma_date?: string;
      relevance_score: number;
      relevance_comments: string;
      grade_weight: number;
      search_type?: string;
    }>;
    search_type: string;
    total_results: number;
    pagination?: {
      page: number;
      page_size: number;
      total_pages: number;
      has_next: boolean;
      has_previous: boolean;
    };
  }> {
    return this.request<any>("/api/chat/search", {
      method: "POST",
      body: JSON.stringify({ 
        query, 
        entity_name: entityName, 
        collection_id: collectionId,
        source_file_id: sourceFileId,
        page,
        page_size: pageSize
      }),
    });
  }

  // Get unique entity names for filter
  async getUniqueEntityNames(collectionId?: number): Promise<{
    success: boolean;
    entity_names: string[];
  }> {
    const params = collectionId ? `?collection_id=${collectionId}` : '';
    return this.request<any>(`/api/chat/entity-names${params}`);
  }

  // ============================
  // File Upload Operations
  // ============================

  // Upload a file (existing method, but enhanced)
  async uploadFile(file: File, metadata?: { brand_name?: string; description?: string }): Promise<{
    success: boolean
    file_id: string
    processing_status: string
    message: string
  }> {
    const formData = new FormData()
    formData.append('file', file)
    
    if (metadata?.brand_name) {
      formData.append('brand_name', metadata.brand_name)
    }
    if (metadata?.description) {
      formData.append('description', metadata.description)
    }

    const response = await fetch(`${API_BASE_URL}/api/files/upload`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeadersWithoutContentType(),
        // Don't set Content-Type for FormData, let browser set it
      },
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`Upload Error: ${response.statusText}`)
    }

    return response.json()
  }

  // Get file upload status
  async getFileStatus(fileId: string): Promise<{
    file_id: string
    status: string
    progress?: number
    error?: string
    extraction_id?: number
  }> {
    return this.request<{
      file_id: string
      status: string
      progress?: number
      error?: string
      extraction_id?: number
    }>(`/api/files/${fileId}/status`)
  }

  // Get source file documents with metadata
  async getSourceFileDocuments(fileId: number): Promise<{
    source_file: {
      id: number
      file_name: string
      file_url: string
      entity_name?: string
      status: string
    }
    documents: Array<{
      id: number
      doc_content: string
      metadata: any
      created_at: string
      updated_at: string
    }>
    total_documents: number
  }> {
    return this.request<{
      source_file: {
        id: number
        file_name: string
        file_url: string
        entity_name?: string
        status: string
      }
      documents: Array<{
        id: number
        doc_content: string
        metadata: any
        created_at: string
        updated_at: string
      }>
      total_documents: number
    }>(`/api/source-files/${fileId}/documents`)
  }

  // Bulk upload source files
  async bulkUploadSourceFiles(items: Array<{
    file_name: string
    file_url: string
    entity_name?: string
    comments?: string
    us_ma_date?: string
  }>): Promise<{
    success: boolean
    total_items: number
    successful_items: number
    failed_items: number
    success_details: Array<{
      row: number
      id: number
      file_name: string
      entity_name?: string
    }>
    failure_details: Array<{
      row: number
      item: any
      error: string
    }>
  }> {
    return this.request<{
      success: boolean
      total_items: number
      successful_items: number
      failed_items: number
      success_details: Array<{
        row: number
        id: number
        file_name: string
        entity_name?: string
      }>
      failure_details: Array<{
        row: number
        item: any
        error: string
      }>
    }>("/api/source-files/bulk-upload", {
      method: "POST",
      body: JSON.stringify({ items }),
    })
  }

  // Upload a single source file
  async uploadSourceFile(formData: FormData): Promise<{
    id: number
    file_name: string
    entity_name?: string
    status: string
    message: string
  }> {
    const response = await fetch(`${API_BASE_URL}/api/source-files/upload`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeadersWithoutContentType(),
        // Don't set Content-Type for FormData, let browser set it
      },
      body: formData,
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Upload Error: ${response.statusText} - ${errorText}`)
    }

    return response.json()
  }

  // Get bulk upload template as XLSX file
  async getBulkUploadTemplate(): Promise<Blob> {
    // Use direct fetch for template download to avoid auth issues
    const response = await fetch(`${API_BASE_URL}/api/templates/bulk-upload`, {
      method: 'GET',
    })
    
    if (!response.ok) {
      throw new Error(`Failed to fetch template: ${response.statusText}`)
    }
    
    return response.blob()
  }

  // Bulk upload source files to a specific collection
  async bulkUploadToCollection(collectionId: number, items: Array<{
    file_name: string
    file_url: string
    entity_name?: string
    comments?: string
    us_ma_date?: string
  }>): Promise<{
    success: boolean
    total_items: number
    successful_items: number
    failed_items: number
    success_details: Array<{
      row: number
      id: number
      file_name: string
      entity_name?: string
    }>
    failure_details: Array<{
      row: number
      item: any
      error: string
    }>
  }> {
    return this.request<any>(`/api/collections/${collectionId}/bulk-upload`, {
      method: "POST",
      body: JSON.stringify({ items }),
    })
  }

  // ============================
  // Collections Operations
  // ============================

  async getCollections(): Promise<any> {
    const response = await this.request<any[]>('/api/collections/');
    // Wrap the array response in an object with collections property
    return { collections: response };
  }

  async createCollection(data: { name: string; description?: string }): Promise<any> {
    return this.request<any>('/api/collections/', {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }

  async updateCollection(collectionId: number, data: { name: string; description?: string }): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    });
  }

  async deleteCollection(collectionId: number, deleteSourceFiles: boolean = false): Promise<any> {
    const params = new URLSearchParams();
    if (deleteSourceFiles) {
      params.append('delete_source_files', 'true');
    }
    
    const url = `/api/collections/${collectionId}${params.toString() ? `?${params}` : ''}`;
    return this.request<any>(url, {
      method: 'DELETE'
    });
  }

  async getCollectionEntityNames(collectionId: number, options: {
    search?: string;
    limit?: number;
    offset?: number;
    include_counts?: boolean;
  } = {}): Promise<{
    collection_id: number;
    collection_name: string;
    entity_names: any[];
    total_count: number;
    limit: number;
    offset: number;
    has_more: boolean;
    search_term?: string;
  }> {
    const params = new URLSearchParams();
    if (options.search && options.search.trim() !== '') {
      params.append('search', options.search.trim());
    }
    if (options.limit !== undefined) params.append('limit', options.limit.toString());
    if (options.offset !== undefined) params.append('offset', options.offset.toString());
    if (options.include_counts !== undefined) params.append('include_counts', options.include_counts.toString());
    
    const url = `/api/collections/${collectionId}/entity-names${params.toString() ? `?${params}` : ''}`;
    return this.request<any>(url);
  }

  async getCollectionDetails(
    collectionId: number,
    page: number = 1,
    pageSize: number = 50,
    searchTerm?: string,
    statusFilter?: string
  ): Promise<any> {
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());
    if (searchTerm) params.append('search', searchTerm);
    if (statusFilter && statusFilter !== 'ALL') params.append('status', statusFilter);
    
    const response = await this.request<any>(`/api/collections/${collectionId}?${params.toString()}`);
    
    // The API returns the collection data directly, but the frontend expects it wrapped
    return {
      collection: response,
      documents: response.documents || [],
      total_documents: response.total_documents || 0,
      total_pages: response.total_pages || 1
    };
  }

  async addDocumentsToCollection(collectionId: number, documentIds: number[]): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}/documents`, {
      method: 'POST',
      body: JSON.stringify({ document_ids: documentIds })
    });
  }

  async removeDocumentFromCollection(collectionId: number, documentId: number): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}/documents/${documentId}`, {
      method: 'DELETE'
    });
  }

  async indexCollectionDocuments(collectionId: number, documentIds: number[]): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}/index`, {
      method: 'POST',
      body: JSON.stringify({ 
        document_ids: documentIds.length > 0 ? documentIds : undefined 
      })
    });
  }

  async getCollectionIndexingStatus(collectionId: number, jobId: string): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}/indexing-status/${jobId}`);
  }

  async reindexDocuments(collectionId: number, documentIds: number[]): Promise<any> {
    return this.request<any>(`/api/collections/${collectionId}/reindex`, {
      method: 'POST',
      body: JSON.stringify({ document_ids: documentIds })
    });
  }

  async getCollectionVectorDetails(collectionId: number, page: number = 1, pageSize: number = 20): Promise<any> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString()
    });
    return this.request<any>(`/api/collections/${collectionId}/vector-details?${params}`);
  }

  // ============================
  // User Management Operations
  // ============================

  // Get all users
  async getUsers(): Promise<any[]> {
    return this.request<any[]>('/api/auth/users')
  }

  // Get user analytics
  async getUserAnalytics(): Promise<any> {
    return this.request<any>('/api/auth/analytics/users')
  }

  // Create a new user
  async createUser(userData: any): Promise<any> {
    return this.request<any>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    })
  }

  // Update user
  async updateUser(userId: number, userData: any): Promise<any> {
    return this.request<any>(`/api/auth/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(userData),
    })
  }

  // Delete user
  async deleteUser(userId: number): Promise<any> {
    return this.request<any>(`/api/auth/users/${userId}`, {
      method: 'DELETE',
    })
  }

  // Reset user password
  async resetUserPassword(userId: number): Promise<{ temporary_password: string }> {
    return this.request<{ temporary_password: string }>(`/api/auth/users/${userId}/reset-password`, {
      method: 'POST',
    })
  }

  // Set user password
  async setUserPassword(userId: number, password: string): Promise<any> {
    return this.request<any>(`/api/auth/users/${userId}/set-password`, {
      method: 'POST',
      body: JSON.stringify({ password }),
    })
  }

  // ============================
  // Metadata Configuration Operations
  // ============================

  // Export metadata configurations as XLSX file
  async exportMetadataConfigs(ids?: number[]): Promise<Blob> {
    let url = `${API_BASE_URL}/api/metadata-configs/export`;
    
    // If specific IDs are provided, add them as query params
    if (ids && ids.length > 0) {
      const params = new URLSearchParams();
      ids.forEach(id => params.append('ids', id.toString()));
      url = `${url}?${params.toString()}`;
    }
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        ...this.getAuthHeadersWithoutContentType(),
      },
    })
    
    if (!response.ok) {
      throw new Error(`Failed to export metadata configs: ${response.statusText}`)
    }
    
    return response.blob()
  }

  // Preview metadata configurations import from XLSX file
  async previewMetadataConfigImport(file: File): Promise<{
    total_rows: number
    valid_rows: number
    invalid_rows: number
    duplicate_rows: number
    configurations: Array<{
      row: number
      metadata_name: string
      description: string
      extraction_prompt: string
      data_type: string
      validation_rules?: string
      is_active: boolean
      validation_status: 'valid' | 'invalid' | 'duplicate'
      errors?: string[]
      warnings?: string[]
      exists?: boolean
    }>
    validation_summary: {
      total_errors: number
      total_warnings: number
      missing_required: number
      invalid_data_types: number
      duplicate_names: number
    }
  }> {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/import/preview`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeadersWithoutContentType(),
      },
      body: formData,
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Preview Error: ${response.statusText} - ${errorText}`)
    }

    return response.json()
  }

  // Import metadata configurations from XLSX file
  async importMetadataConfigs(file: File, options?: {
    import_mode?: 'skip' | 'update' | 'replace'
    validate_only?: boolean
    include_inactive?: boolean
  }): Promise<{
    success: boolean
    total_processed: number
    successful_imports: number
    failed_imports: number
    skipped_imports?: number
    import_details: {
      successful: Array<{
        row: number
        metadata_name: string
        action: string
        id: number
      }>
      failed: Array<{
        row: number
        metadata_name: string
        error: string
      }>
      skipped?: Array<{
        row: number
        metadata_name: string
        reason: string
      }>
    }
    import_metadata: {
      imported_by: string
      import_timestamp: string
      filename: string
    }
  }> {
    // Debug logging
    console.log('Importing file:', file);
    console.log('File size:', file.size);
    console.log('File type:', file.type);
    console.log('File name:', file.name);
    
    if (!file) {
      throw new Error('No file provided for import');
    }

    const formData = new FormData()
    formData.append('file', file)
    
    // Append options to FormData if provided
    if (options) {
      if (options.import_mode) formData.append('import_mode', options.import_mode)
      if (options.validate_only !== undefined) formData.append('validate_only', options.validate_only.toString())
      if (options.include_inactive !== undefined) formData.append('include_inactive', options.include_inactive.toString())
    }

    // Debug FormData
    for (const [key, value] of formData.entries()) {
      console.log('FormData entry:', key, value);
    }

    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/import`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeadersWithoutContentType(),
        // Don't set Content-Type for FormData, let browser set it
      },
      body: formData,
    })

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Import Error: ${response.statusText} - ${errorText}`)
    }

    return response.json()
  }

  // Metadata Configuration endpoints
  async getAllMetadataConfigs(): Promise<any[]> {
    const response = await this.request<any>("/api/metadata-configs", {
      method: 'GET'
    });
    // Handle both old array format and new paginated format
    if (Array.isArray(response)) {
      return response;
    }
    // If it's the new format with fields and total
    if (response && response.fields) {
      return response.fields;
    }
    return [];
  }

  async createMetadataConfig(configData: any): Promise<any> {
    console.log('🆕 Creating metadata config:', configData);
    console.log('🔐 Auth token present:', !!localStorage.getItem('access_token'));
    console.log('🔐 Auth headers:', this.getAuthHeaders());
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs`, {
      method: 'POST',
      headers: {
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(configData),
    });

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Create Error: ${response.statusText} - ${errorText}`)
    }

    return response.json();
  }

  async updateMetadataConfig(configId: number, configData: any): Promise<any> {
    console.log('🔄 Updating metadata config:', configId, configData);
    console.log('🔐 Auth token present:', !!localStorage.getItem('access_token'));
    console.log('🔐 Auth headers:', this.getAuthHeaders());
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/${configId}`, {
      method: 'PUT',
      headers: {
        ...this.getAuthHeaders(),
      },
      body: JSON.stringify(configData),
    });

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Update Error: ${response.statusText} - ${errorText}`)
    }

    return response.json();
  }

  async deleteMetadataConfig(configId: number): Promise<any> {
    console.log('🗑️ Deleting metadata config:', configId);
    console.log('🔐 Auth token present:', !!localStorage.getItem('access_token'));
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/${configId}`, {
      method: 'DELETE',
      headers: {
        ...this.getAuthHeaders(),
      },
    });

    if (!response.ok) {
      const errorText = await response.text()
      throw new Error(`Delete Error: ${response.statusText} - ${errorText}`)
    }

    return response.json();
  }

  // ============================
  // Metadata Configuration Operations
  // ============================

  async getAllMetadataFields(
    page: number = 1, 
    pageSize: number = 20, 
    search: string = '', 
    token?: string
  ): Promise<{ fields: any[], total: number }> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const params = new URLSearchParams({
      skip: Math.max(0, (page - 1) * pageSize).toString(),
      limit: pageSize.toString()
    });
    if (search) {
      params.append('search', search);
    }
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs?${params.toString()}`, {
      method: 'GET',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get metadata fields: ${response.statusText}`);
    }
    
    // Handle both old format (array) and new format ({fields: [], total: number})
    const data = await response.json();
    if (Array.isArray(data)) {
      return { fields: data, total: data.length };
    }
    return data;
  }

  // ============================
  // Metadata Groups Operations
  // ============================

  async getMetadataGroups(
    page: number = 1, 
    pageSize: number = 10, 
    search: string = '', 
    token?: string
  ): Promise<{ groups: any[], total: number }> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const params = new URLSearchParams({
      skip: Math.max(0, (page - 1) * pageSize).toString(),
      limit: pageSize.toString()
    });
    if (search) {
      params.append('search', search);
    }
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups?${params.toString()}`, {
      method: 'GET',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get metadata groups: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log('Metadata groups API response:', data);
    return data;
  }

  async getMetadataGroup(groupId: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}`, {
      method: 'GET',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get metadata group: ${response.statusText}`);
    }
    
    return response.json();
  }

  async getMetadataGroupItems(groupId: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/items`, {
      method: 'GET',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get metadata group items: ${response.statusText}`);
    }
    
    return response.json();
  }

  async createMetadataGroup(groupData: { name: string; description?: string; color?: string; tags?: string[] }, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups`, {
      method: 'POST',
      headers,
      body: JSON.stringify(groupData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Create Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async updateMetadataGroup(groupId: number, groupData: { name?: string; description?: string; color?: string; tags?: string[] }, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(groupData),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Update Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async deleteMetadataGroup(groupId: number, token?: string): Promise<void> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}`, {
      method: 'DELETE',
      headers
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Delete Error: ${response.statusText} - ${errorText}`);
    }
  }

  async addMetadataToGroup(groupId: number, data: { metadata_config_id: number; display_order?: number }, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/items`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Add Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async removeMetadataFromGroup(groupId: number, configId: number, token?: string): Promise<void> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/items/${configId}`, {
      method: 'DELETE',
      headers
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Remove Error: ${response.statusText} - ${errorText}`);
    }
  }

  async bulkAssignConfigurationsToGroup(groupId: number, configIds: number[], token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/bulk-assign`, {
      method: 'POST',
      headers,
      body: JSON.stringify(configIds),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Bulk Assign Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async reorderMetadataConfiguration(configId: number, newOrder: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configurations/${configId}/reorder?new_order=${newOrder}`, {
      method: 'POST',
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Reorder Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async reorderMetadataConfigurationInGroup(groupId: number, configId: number, newOrder: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/configurations/${configId}/reorder?new_order=${newOrder}`, {
      method: 'POST',
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Reorder Error: ${response.statusText} - ${errorText}`);
    }

    return response.json();
  }

  async getMetadataConfigurations(token?: string): Promise<any[]> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs`, {
      method: 'GET',
      headers
    });
    
    if (!response.ok) {
      throw new Error(`Failed to get metadata configurations: ${response.statusText}`);
    }
    
    return response.json();
  }

  async createMetadataField(
    data: {
      metadata_name: string;
      description: string;
      extraction_prompt: string;
      data_type: string;
      is_active?: boolean;
      validation_rules?: any;
    },
    token?: string
  ): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to create metadata field: ${errorText}`);
    }

    return response.json();
  }

  async updateMetadataField(
    id: number,
    data: {
      metadata_name?: string;
      description?: string;
      extraction_prompt?: string;
      data_type?: string;
      is_active?: boolean;
      validation_rules?: any;
    },
    token?: string
  ): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/${id}`, {
      method: 'PUT',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to update metadata field: ${errorText}`);
    }

    return response.json();
  }

  async deleteMetadataField(id: number, token?: string): Promise<void> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configs/${id}`, {
      method: 'DELETE',
      headers,
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to delete metadata field: ${errorText}`);
    }
  }

  async getDocumentsByMetadataGroup(groupId: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/collections/metadata-group/${groupId}/documents`, {
        method: 'GET',
        headers
    });

    if (!response.ok) {
        throw new Error(`Failed to get documents for metadata group: ${response.statusText}`);
    }

    return response.json();
  }

  async getMetadataByGroup(groupId: number, token?: string): Promise<any> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-groups/${groupId}/metadata`, {
        method: 'GET',
        headers
    });

    if (!response.ok) {
        throw new Error(`Failed to get metadata for group: ${response.statusText}`);
    }

    return response.json();
  }

  // Metadata Import/Export
  async downloadMetadataTemplate(token?: string): Promise<Blob> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const response = await fetch(`${API_BASE_URL}/api/metadata-configurations/template/download`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to download template: ${response.statusText}`);
    }

    return response.blob();
  }

  async importMetadataConfigurations(file: File, token?: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);

    const headers = token ? { 'Authorization': `Bearer ${token}` } : {};
    
    const response = await fetch(`${API_BASE_URL}/api/metadata-configurations/import`, {
      method: 'POST',
      headers,
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorDetail = 'Failed to import configurations';
      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorDetail;
      } catch {
        errorDetail = errorText || errorDetail;
      }
      throw new Error(errorDetail);
    }

    return response.json();
  }

  async exportMetadataConfigurations(groupIds?: number[], activeOnly: boolean = true, token?: string): Promise<Blob> {
    const headers = token ? { ...this.getAuthHeaders(), 'Authorization': `Bearer ${token}` } : this.getAuthHeaders();
    const params = new URLSearchParams();
    
    if (groupIds && groupIds.length > 0) {
      params.append('group_ids', groupIds.join(','));
    }
    if (activeOnly) {
      params.append('active_only', 'true');
    }

    const response = await fetch(`${API_BASE_URL}/api/metadata-configurations/export?${params}`, {
      method: 'GET',
      headers
    });

    if (!response.ok) {
      throw new Error(`Failed to export configurations: ${response.statusText}`);
    }

    return response.blob();
  }

  // Collection Metadata Extraction
  async extractMetadataForCollection(
    collectionId: number, 
    groupId: number, 
    documentIds?: number[]
  ): Promise<{ job_id: string; message: string }> {
    const response = await fetch(`${API_BASE_URL}/api/collections/${collectionId}/extract-metadata`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
      body: JSON.stringify({
        group_id: groupId,
        document_ids: documentIds
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to start metadata extraction: ${errorText}`);
    }

    return response.json();
  }

  async getExtractionJobStatus(jobId: string): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/extraction-jobs/${jobId}/status`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to get extraction job status: ${response.statusText}`);
    }

    return response.json();
  }

  async stopExtractionJob(jobId: number): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/extraction-jobs/${jobId}/stop`, {
      method: 'POST',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to stop extraction job: ${response.statusText}`);
    }

    return response.json();
  }

  async getCollectionMetadata(
    collectionId: number,
    groupId?: number
  ): Promise<any> {
    const params = new URLSearchParams();
    if (groupId) params.append('group_id', groupId.toString());
    
    const response = await fetch(`${API_BASE_URL}/api/collections/${collectionId}/metadata${params.toString() ? `?${params}` : ''}`, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to get collection metadata: ${response.statusText}`);
    }

    return response.json();
  }

  async exportCollectionMetadata(
    collectionId: number,
    format: 'excel' | 'csv' = 'excel',
    groupId?: number
  ): Promise<Blob> {
    const params = new URLSearchParams();
    params.append('format', format);
    if (groupId) params.append('group_id', groupId.toString());
    
    const response = await fetch(`${API_BASE_URL}/api/collections/${collectionId}/export-metadata?${params}`, {
      method: 'POST',
      headers: this.getAuthHeadersWithoutContentType(),
    });

    if (!response.ok) {
      throw new Error(`Failed to export metadata: ${response.statusText}`);
    }

    return response.blob();
  }

  async getExtractedMetadataGroups(collectionId: number): Promise<any> {
    const response = await fetch(`${API_BASE_URL}/api/collections/${collectionId}/extracted-groups`, {
      headers: this.getAuthHeaders(),
    });
    if (!response.ok) {
      throw new Error(`Failed to get extracted metadata groups: ${response.statusText}`);
    }
    return response.json();
  }

  // Get extraction jobs for a collection
  async getCollectionExtractionJobs(
    collectionId: number, 
    userJobsOnly = false,
    statusFilter?: string,
    page = 1,
    pageSize = 10
  ) {
    const params = new URLSearchParams();
    if (userJobsOnly) {
      params.append('user_jobs_only', 'true');
    }
    if (statusFilter && statusFilter !== 'all') {
      params.append('status_filter', statusFilter);
    }
    params.append('page', page.toString());
    params.append('page_size', pageSize.toString());
    
    const url = `${API_BASE_URL}/api/extraction-jobs/collection/${collectionId}?${params}`;
    console.log('Fetching extraction jobs from:', url);
    
    const response = await fetch(url, {
      method: 'GET',
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      console.error('Failed to fetch extraction jobs:', response.status, response.statusText);
      throw new Error('Failed to fetch extraction jobs');
    }

    return await response.json();
  }

  // ============================
  // Metadata Extraction Operations
  // ============================

  // Get source files for metadata extraction view
  async getSourceFilesForMetadata(params?: {
    limit?: number
    offset?: number
    status?: string
    search?: string
  }): Promise<{
    source_files: any[]
    total_count: number
    limit: number
    offset: number
  }> {
    const queryParams = new URLSearchParams()
    
    if (params?.limit) queryParams.append('limit', params.limit.toString())
    if (params?.offset) queryParams.append('offset', params.offset.toString())
    if (params?.status) queryParams.append('status', params.status)
    if (params?.search) queryParams.append('search', params.search)
    
    const endpoint = `/api/metadata-extraction/source-files${queryParams.toString() ? `?${queryParams.toString()}` : ''}`
    return this.request<{
      source_files: any[]
      total_count: number
      limit: number
      offset: number
    }>(endpoint)
  }

  // Get metadata extraction statistics
  async getMetadataExtractionStats(): Promise<{
    total: number
    readyForExtraction: number
    metadataExtracted: number
    totalMetadataFields: number
  }> {
    return this.request<{
      total: number
      readyForExtraction: number
      metadataExtracted: number
      totalMetadataFields: number
    }>("/api/metadata-extraction/stats")
  }

  // Extract metadata for a source file
  async extractMetadata(sourceFileId: number): Promise<any> {
    return this.request<any>("/api/metadata-extraction/extract", {
      method: "POST",
      body: JSON.stringify({ source_file_id: sourceFileId }),
    });
  }

  // View extracted metadata for a source file
  async viewExtractedMetadata(sourceFileId: number): Promise<any> {
    return this.request<any>(`/api/metadata-extraction/view/${sourceFileId}`);
  }

  // Delete extracted metadata for a source file
  async deleteExtractedMetadata(sourceFileId: number): Promise<any> {
    return this.request<any>(`/api/metadata-extraction/delete/${sourceFileId}`, {
      method: "DELETE",
    });
  }

  // Re-extract metadata for a source file (deletes existing and extracts again)
  async reExtractMetadata(sourceFileId: number): Promise<any> {
    return this.request<any>("/api/metadata-extraction/re-extract", {
      method: "POST",
      body: JSON.stringify({ source_file_id: sourceFileId }),
    });
  }

  // Extract metadata for multiple source files sequentially
  async extractMetadataSequential(sourceFileIds: number[]): Promise<{
    success: boolean;
    message: string;
    extraction_files: Array<{
      id: number;
      file_name: string;
      entity_name?: string;
    }>;
    total_requested: number;
    total_queued: number;
  }> {
    return this.request<any>("/api/metadata-extraction/extract-sequential", {
      method: "POST",
      body: JSON.stringify({ source_file_ids: sourceFileIds }),
    });
  }

  // Get all metadata for export (JSON and Excel)
  async getMetadataExportData(): Promise<{
    success: boolean;
    grouped_data: { [entityName: string]: { [usMADate: string]: any } };
    flat_data: Array<{
      'File URL': string;
      'Entity Name': string;
      'US MA Date': string;
      'Metadata Name': string;
      'Extracted Value': string;
      'Confidence Score': string;
      'Extraction Date': string;
    }>;
    total_records: number;
    total_entities: number;
  }> {
    return this.request<any>("/api/metadata-extraction/export-data");
  }

  // Get entity metadata for a specific source file
  async getEntityMetadata(sourceFileId: number): Promise<{
    source_file: {
      id: number;
      file_name: string;
      file_url: string;
      entity_name: string;
      status: string;
    };
    metadata: Array<{
      id: number;
      metadata_name: string;
      value: string;
      entityname: string;
      source_file_id: number;
      file_url: string;
      created_at: string;
      metadata_details?: string;
    }>;
    total_count: number;
  }> {
    return this.request<any>(`/api/entities/${sourceFileId}/metadata`);
  }

  // Get entity metadata for a specific source file
  async getEntityMetadata(sourceFileId: number): Promise<{
    source_file: {
      id: number;
      file_name: string;
      file_url: string;
      entity_name: string;
      status: string;
    };
    metadata: Array<{
      id: number;
      attribute_name: string;
      value: string;
      entity_name: string;
      source_file_id: number;
      file_url: string;
      created_at: string;
      metadata_details?: string;
    }>;
    total_count: number;
  }> {
    return this.request<any>(`/api/entities/${sourceFileId}/metadata`);
  }

  // ============================
  // Chat Operations
  // ============================

  // Get chat suggestions based on context
  async getChatSuggestions(params: {
    chat_history?: Array<{ role: string; content: string }>;
    selected_entities?: string[];
    last_response?: string;
  }): Promise<{
    suggestions: string[];
    type: 'contextual' | 'rule-based';
  }> {
    return this.request<any>("/api/chat/suggestions", {
      method: "POST",
      body: JSON.stringify(params),
    });
  }

  // Get user chat suggestions
  async getUserChatSuggestions(userId: number): Promise<{
    suggestions: string[];
  }> {
    return this.request<any>(`/api/chat/suggestions/${userId}`);
  }

  // Get user chat history
  async getUserChatHistory(userId: number, docxChatFilter?: boolean): Promise<{
    history: Array<{
      id: number;
      session_id: string;
      query: string;
      response: string;
      source_file_id?: number;
      source_file_ids?: number[];
      created_at: string;
      is_favorite: boolean;
      is_docx_chat?: boolean;
      source_info?: {
        type: string;
        source: string;
        model?: string;
        documents_used?: number;
      };
      used_documents?: boolean;
      search_results?: Array<{
        source_file_id: number;
        file_name: string;
        entity_name: string;
        relevance_score: number;
      }>;
    }>;
  }> {
    const params = docxChatFilter !== undefined ? `?docx_chat_filter=${docxChatFilter}` : '';
    return this.request<any>(`/api/chat/history/${userId}${params}`);
  }
  
  // Get user chat sessions (grouped by session)
  async getUserChatSessions(userId: number, docxChatFilter?: boolean): Promise<{
    sessions: Array<{
      id: number;
      session_id: string;
      query: string;
      created_at: string;
      last_activity: string;
      message_count: number;
      is_favorite: boolean;
      is_docx_chat?: boolean;
      timestamp: string;
    }>;
  }> {
    const params = docxChatFilter !== undefined ? `?docx_chat_filter=${docxChatFilter}` : '';
    return this.request<any>(`/api/chat/sessions/${userId}${params}`);
  }

  // Get chat session details
  async getChatSession(sessionId: string): Promise<{
    session_id: string;
    chats: Array<{
      id: number;
      query: string;
      response: string;
      source_file_id?: number;
      source_file_ids?: number[];
      created_at: string;
      is_favorite: boolean;
      source_documents?: any[];
      source_info?: any;
    }>;
  }> {
    const userId = this.getCurrentUserId();
    return this.request<any>(`/api/chat/session/${sessionId}?user_id=${userId}`);
  }

  // Create new chat session
  async createChatSession(): Promise<{
    session_id: string;
  }> {
    return this.request<any>("/api/chat/new-session");
  }

  // Toggle chat favorite
  async toggleChatFavorite(chatId: number, isFavorite: boolean): Promise<{
    success: boolean;
    message?: string;
  }> {
    // Get current user info from stored user data
    const userData = localStorage.getItem('user_data');
    if (!userData) {
      console.error('❌ toggleChatFavorite: Authentication required');
      throw new Error('Authentication required');
    }
    
    // Parse user data to get user ID
    let userId = 1; // Default fallback
    try {
      const user = JSON.parse(userData);
      userId = user.id || 1;
    } catch (e) {
      console.warn('Could not parse user data, using default user ID');
    }

    const endpoint = "/api/chat/favorite";
    const method = isFavorite ? "POST" : "DELETE";
    const body = { chat_id: chatId, user_id: userId };
    
    console.log(`🔄 API: ${method} ${endpoint}`, body);
    
    try {
      const result = await this.request<any>(endpoint, {
        method,
        body: JSON.stringify(body),
      });
      console.log('✅ API response:', result);
      return result;
    } catch (error) {
      console.error('❌ API error:', error);
      throw error;
    }
  }

  // Get current user ID from localStorage
  private getCurrentUserId(): number | null {
    const userData = localStorage.getItem('user_data');
    if (userData) {
      try {
        const user = JSON.parse(userData);
        return user.id || null;
      } catch (e) {
        return null;
      }
    }
    return null;
  }

  // Get favorite chats for a user
  async getFavoriteChats(userId: number, docxChatFilter?: boolean): Promise<{
    favorites: Array<{
      id: number;
      session_id: string;
      query: string;
      response: string;
      created_at: string;
      is_favorite: boolean;
      source_file_id?: number;
      source_file_ids?: number[];
    }>;
  }> {
    const params = docxChatFilter !== undefined ? `?docx_chat_filter=${docxChatFilter}` : '';
    return this.request<any>(`/api/chat/favorites/${userId}${params}`);
  }

  // Delete a chat
  async deleteChat(chatId: number): Promise<{
    success: boolean;
  }> {
    const userId = this.getCurrentUserId();
    if (!userId) {
      throw new Error('User not authenticated');
    }
    return this.request<any>(`/api/chat/chat/${chatId}?user_id=${userId}`, {
      method: 'DELETE',
    });
  }

  // Create a share link for a chat session
  async createShareLink(params: {
    session_id: string;
    messages: any[];
    title: string;
    expiration_hours: number;
    password?: string;
  }): Promise<{
    share_url: string;
    share_id: string;
    expires_at: string;
  }> {
    return this.request<any>('/api/chat/share', {
      method: 'POST',
      body: JSON.stringify(params),
    });
  }

  // Get shared chat by share ID
  async getSharedChat(shareId: string, password?: string): Promise<{
    id: string;
    title: string;
    messages: any[];
    created_at: string;
    view_count: number;
    expires_at: string;
  }> {
    const params = new URLSearchParams();
    if (password) {
      params.append('password', password);
    }
    
    // Use fetch directly to avoid JWT token refresh logic for shared links
    const response = await fetch(`${API_BASE_URL}/api/chat/share/${shareId}${params.toString() ? `?${params}` : ''}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        // This is a password-required response, not an authentication issue
        const error = new Error('Password required');
        (error as any).status = 401;
        (error as any).response = { status: 401 };
        throw error;
      }
      
      if (response.status === 404) {
        const error = new Error('Share link not found or expired');
        (error as any).status = 404;
        (error as any).response = { status: 404 };
        throw error;
      }
      
      // Try to parse error message from response body
      let errorMessage = `API Error: ${response.status} ${response.statusText}`;
      try {
        const errorData = await response.json();
        if (errorData.detail) {
          errorMessage = typeof errorData.detail === 'string' 
            ? errorData.detail 
            : JSON.stringify(errorData.detail);
        }
      } catch (e) {
        // If parsing fails, use the default error message
      }
      
      const error = new Error(errorMessage);
      (error as any).status = response.status;
      (error as any).response = { status: response.status };
      throw error;
    }

    return response.json();
  }
}

export const apiService = new ApiService()
