"use client";

import React, { useState, useEffect, useRef, useCallback, Fragment, useMemo } from 'react';
import {
  Dialog,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';

import { 
  X,
  Send, 
  Bot, 
  User,
  Loader2,
  FileText,
  Copy,
  MessageSquare,
  Sparkles,
  RefreshCw,
  AlertCircle,
  ArrowRight,
  Lightbulb,
  MessageCircle,
  Maximize2,
  Minimize2,
  Download,
  Share2,
  Mic,
  Check,
  CheckCheck,
  FileDown,
  FolderOpen,
  PanelRightOpen,
  PanelRightClose,
  History,
  Search
} from 'lucide-react';
import { apiService, type ChatMessage } from '@/services/api';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { EnhancedSourceDocuments } from '@/components/chat/EnhancedSourceDocuments';
import { VirtualDrugListFixed as VirtualDrugList } from '@/components/chat/VirtualDrugListFixed';
import { CollectionViewer } from '@/components/dashboard/CollectionViewer';
import { ShareChatModal } from '@/components/dashboard/ShareChatModal';
import { ChatHistorySidebar } from '@/components/ChatHistorySidebar';
import { format } from 'date-fns';
import { getRelativeTime, getFullTimestamp, getDateSeparatorText, shouldShowDateSeparator } from '@/utils/timeFormat';
import { downloadPDF, downloadHTML } from '@/utils/pdfExport';
import { copyToClipboard } from '@/utils/clipboard';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  suggestions?: string[];
  attachments?: Array<{
    name: string;
    type: string;
    url: string;
  }>;
  status?: 'sending' | 'sent' | 'delivered' | 'read';
  isTyping?: boolean;
  replyTo?: ChatMessage;
  isEdited?: boolean;
  editedAt?: Date;
}



interface DrugDocument {
  drugName: string;
  documents: Array<{
    id: number;
    fileName: string;
  }>;
}

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceFileIds: number[];
  drugNames: string[];
  drugDocuments?: DrugDocument[]; // New prop for grouped drug information
  initialMessage?: string;
  collectionName?: string;
  collectionId?: number;
  isDocXChat?: boolean;  // True for dashboard chat, uses v2 endpoint
  isCollectionChat?: boolean;  // True for collection page chat, uses old endpoint
  isDashboardCollectionChat?: boolean;  // True for collection chat from dashboard
  globalSearch?: boolean;  // True to enable global search fallback
}

export function ChatModalProfessional({ isOpen, onClose, sourceFileIds, drugNames, drugDocuments, initialMessage, collectionName, collectionId, isDocXChat = false, isCollectionChat = false, isDashboardCollectionChat = false, globalSearch = false }: ChatModalProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [userId, setUserId] = useState<number | null>(null);
  const [isCollectionExpanded, setIsCollectionExpanded] = useState(false);
  const [assistantTyping, setAssistantTyping] = useState(false);
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const [rightPanelView, setRightPanelView] = useState<'suggestions' | 'collection' | 'history'>('suggestions');
  const [showRightPanel, setShowRightPanel] = useState(false);
  const [conversationHistory, setConversationHistory] = useState<any[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isMultipleFiles = sourceFileIds.length > 1;
  

  // Initialize user data
  useEffect(() => {
    const userData = localStorage.getItem('user_data');
    if (userData) {
      try {
        const user = JSON.parse(userData);
        setUserId(user.id || 1);
      } catch (e) {
        console.error('Failed to parse user data:', e);
        setUserId(1);
      }
    }
  }, []);

  // Create new session when modal opens
  useEffect(() => {
    if (isOpen && userId) {
      createNewSession();
    }
  }, [isOpen, userId]);

  // Load suggestions only after first user message
  useEffect(() => {
    if (isOpen && messages.length > 2) {
      // Load suggestions after user has sent their first message
      // (messages[0] is welcome, messages[1] is first user message, messages[2] is first response)
      loadSuggestions();
    }
  }, [isOpen, messages.length]);
  



  const createNewSession = async () => {
    try {
      const response = await apiService.createChatSession();
      setSessionId(response.session_id);
      localStorage.setItem('session_id', response.session_id);
    } catch (error) {
      console.error('Failed to create new session:', error);
      // Fallback to local session ID
      const fallbackSessionId = crypto.randomUUID();
      setSessionId(fallbackSessionId);
      localStorage.setItem('session_id', fallbackSessionId);
    }
  };


  const loadSuggestions = async () => {
    setIsLoadingSuggestions(true);
    try {
      const chatHistory = messages.map(msg => ({
        role: msg.role,
        content: msg.content
      }));
      
      const lastAssistantMessage = messages.filter(m => m.role === 'assistant').pop();
      
      const response = await apiService.getChatSuggestions({
        chat_history: chatHistory,
        selected_drugs: effectiveDrugNames,
        last_response: lastAssistantMessage?.content
      });
      
      console.log('Suggestions API response:', response);
      
      if (response && response.suggestions && Array.isArray(response.suggestions)) {
        setSuggestions(response.suggestions);
        // Automatically show suggestions panel when suggestions are loaded
        if (response.suggestions.length > 0) {
          setRightPanelView('suggestions');
          setShowRightPanel(true);
        }
      } else {
        console.warn('Invalid suggestions response format:', response);
        setSuggestions(getDefaultSuggestions());
      }
    } catch (error) {
      console.error('Failed to load suggestions:', error);
      // Fallback to default suggestions
      setSuggestions(getDefaultSuggestions());
    } finally {
      setIsLoadingSuggestions(false);
    }
  };

  const getDefaultSuggestions = () => {
    if (isMultipleFiles) {
      if (collectionName) {
        return [
          "What are the common side effects across all drugs?",
          "Which drug has fewer interactions?",
          "Compare the dosage recommendations",
          "What are the key differences between these drugs?",
          "Compare effectiveness and safety profiles"
        ];
      }
      return [
        `Compare side effects between ${drugNames.slice(0, 2).join(' and ')}`,
        "Which drug has fewer interactions?",
        "Compare the dosage recommendations",
        "What are the key differences?",
        "Compare effectiveness and safety profiles"
      ];
    }
    return [
      "What are the main side effects?",
      "Tell me about drug interactions",
      "What is the recommended dosage?",
      "Explain the contraindications",
      "What are the warnings and precautions?"
    ];
  };

  useEffect(() => {
    if (isOpen) {
      // Debug: Show which endpoint will be used
      const debugInfo = {
        sourceFileIds,
        drugNames,
        collectionId,
        collectionName
      };
      
      
      // Determine which endpoint will be used based on our logic
      let endpointToUse = '';
      if (isDashboardCollectionChat) {
        endpointToUse = '/api/chat/query-multiple';
        console.log('Will use v1 endpoint because isDashboardCollectionChat=true (Dashboard collection chat)');
      } else if (isDocXChat) {
        endpointToUse = '/api/chat_v2/query-multiple-v2';
        console.log('Will use v2 endpoint because isDocXChat=true (Dashboard document chat)');
      } else if (isCollectionChat) {
        endpointToUse = '/api/chat/query-multiple';
        console.log('Will use v1 endpoint because isCollectionChat=true (Collection page chat)');
      } else if (sourceFileIds && sourceFileIds.length > 0) {
        endpointToUse = '/api/chat_v2/query-multiple-v2';
        console.log('Will use v2 endpoint because sourceFileIds exists and has length > 0 (legacy)');
      } else if (collectionId !== undefined && collectionId !== null) {
        endpointToUse = '/api/chat/query-multiple';
        console.log('Will use v1 endpoint because collectionId exists but no sourceFileIds (legacy)');
      } else {
        endpointToUse = 'UNKNOWN';
        console.log('Will use UNKNOWN endpoint - this should not happen');
      }
      
      console.log('Expected endpoint:', endpointToUse);
      console.log('=================================');
      
      if (initialMessage) {
        sendMessage(initialMessage);
      } else {
        const welcomeContent = (isCollectionChat || isDashboardCollectionChat)
          ? `I can help you analyze information from the **${collectionName || 'collection'}** collection. What would you like to know?`
          : isMultipleFiles
            ? collectionName 
              ? `I can help you analyze information from the **${collectionName}** collection containing ${sourceFileIds.length} FDA documents. What would you like to know?`
              : `I can help you compare and analyze information across these ${sourceFileIds.length} drugs: **${drugNames.filter(Boolean).join(', ') || 'FDA documents'}**. What would you like to know?`
            : `I can provide detailed information about **${drugNames[0] || 'this FDA document'}** based on official FDA documentation. What would you like to know?`;
        
        setMessages([{
          id: '1',
          role: 'assistant',
          content: welcomeContent,
          timestamp: new Date()
        }]);
      }
      
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen, sourceFileIds, drugNames, isMultipleFiles, initialMessage, isCollectionChat, isDashboardCollectionChat, collectionName]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;
    
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, { ...userMessage, status: 'sending' }]);
    setInputMessage('');
    setIsLoading(true);
    
    // Update status to sent after a short delay
    setTimeout(() => {
      setMessages(prev => prev.map(msg => 
        msg.id === userMessage.id ? { ...msg, status: 'sent' } : msg
      ));
    }, 300);
    
    // Update status to delivered after another delay
    setTimeout(() => {
      setMessages(prev => prev.map(msg => 
        msg.id === userMessage.id ? { ...msg, status: 'delivered' } : msg
      ));
    }, 800);
    
    const loadingMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: 'Analyzing documents...',
      timestamp: new Date(),
      isLoading: true
    };
    
    setMessages(prev => [...prev, loadingMessage]);
    
    try {
      // Use document-specific chat endpoint for DocXAI
      const requestPayload: any = { 
        message: message
      };

      // Set docXChat flag if it's a dashboard chat
      if (isDocXChat) {
        requestPayload.docXChat = true;
      }

      // Add source page flags to help API service determine which endpoint to use
      if (isDashboardCollectionChat) {
        requestPayload.isDashboardCollectionChat = true;  // Dashboard collection chat - use old endpoint
      } else if (isCollectionChat) {
        requestPayload.collectionChat = true;  // Collection page chat - use old endpoint
      }

      // Always include collection_id if available for context
      if (collectionId !== undefined && collectionId !== null && collectionId !== -1) {
        requestPayload.collection_id = collectionId;
      }
      
      // Add global search flag if enabled
      if (globalSearch) {
        requestPayload.global_search = true;
      }
      
      // Always include source file IDs
      if (sourceFileIds && sourceFileIds.length > 1) {
        // Multiple files - use source_file_ids
        requestPayload.source_file_ids = sourceFileIds;
      } else if (sourceFileIds && sourceFileIds.length === 1) {
        // Single file - use source_file_id for backward compatibility, but also include as array
        requestPayload.source_file_id = sourceFileIds[0];
        requestPayload.source_file_ids = sourceFileIds;
      }


      const response = await apiService.sendChatMessage(requestPayload);
      
      setMessages(prev => {
        // Preserve all existing messages with their complete properties (including sourceInfo)
        const existingMessages = prev.filter(msg => !msg.isLoading);
        
        // Create new assistant message with enhanced fields
        const newAssistantMessage: ChatMessage = {
          id: response.id,
          role: 'assistant',
          content: response.content,
          timestamp: new Date(response.timestamp),
          source_documents: response.source_documents,
          contentType: response.contentType || 'html',
          // Enhanced fields with safe fallbacks
          cited_content: response.cited_content,
          intent: response.intent,
          conversation_summary: response.conversation_summary,
          enhanced_query: response.enhanced_query,
          confidence_scores: response.confidence_scores
        };
        
        // Debug log
        console.log('Assistant message with source_documents:', {
          hasSourceDocs: !!response.source_documents,
          sourceDocsCount: response.source_documents?.length || 0,
          sourceDocs: response.source_documents
        });
        
        return [...existingMessages, newAssistantMessage];
      });
      
      // Reload suggestions after new message
      setTimeout(loadSuggestions, 500);
    } catch (error) {
      console.error('Failed to send message:', error);
      
      setMessages(prev => {
        const filtered = prev.filter(msg => !msg.isLoading);
        
        let errorMessage = 'I apologize, but I encountered an error processing your request.';
        
        if (error instanceof Error) {
          if (error.message.includes('404')) {
            errorMessage = 'The chat service is currently unavailable. Please ensure the backend server is running.';
          } else if (error.message.includes('401')) {
            errorMessage = 'Authentication error. Please log in again.';
          }
        }
        
        return [...filtered, {
          id: Date.now().toString(),
          role: 'assistant',
          content: errorMessage,
          timestamp: new Date()
        }];
      });
      
      toast.error('Failed to get response. Check console for details.');
    } finally {
      setIsLoading(false);
      
      // Mark user message as read when assistant responds
      setMessages(prev => prev.map(msg => 
        msg.role === 'user' && msg.status === 'delivered' ? { ...msg, status: 'read' } : msg
      ));
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputMessage);
    }
  };

  const copyMessage = async (content: string) => {
    const success = await copyToClipboard(content);
    if (success) {
      toast.success('Copied to clipboard');
    } else {
      toast.error('Failed to copy to clipboard');
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputMessage(suggestion);
    textareaRef.current?.focus();
  };
  
  // Removed edit, delete, and reply functionality as requested
  
  // Load full conversation history when clicking on a history item
  const handleLoadHistorySession = async (sessionId: string) => {
    try {
      setLoadingHistory(true);
      const response = await apiService.getChatSession(sessionId);
      
      if (response && response.chats) {
        // Convert the chat history to messages format
        const historicalMessages: ChatMessage[] = [];
        
        response.chats.forEach((chat: any) => {
          // Add user message
          historicalMessages.push({
            id: `${chat.id}-query`,
            role: 'user',
            content: chat.query,
            timestamp: new Date(chat.created_at)
          });
          
          // Add assistant response
          historicalMessages.push({
            id: `${chat.id}-response`,
            role: 'assistant',
            content: chat.response,
            timestamp: new Date(chat.created_at),
            source_documents: chat.source_documents,
            sourceInfo: chat.source_info
          });
        });
        
        // Update messages with the historical conversation
        setMessages(historicalMessages);
        
        // Update session ID to continue in the same session
        setSessionId(sessionId);
        localStorage.setItem('session_id', sessionId);
        
        // Close the history panel
        setShowRightPanel(false);
        
        toast.success('Conversation history loaded');
      }
    } catch (error) {
      console.error('Failed to load conversation history:', error);
      toast.error('Failed to load conversation history');
    } finally {
      setLoadingHistory(false);
    }
  };
  
  // Load a specific query from history
  const handleLoadQuery = (query: string) => {
    setInputMessage(query);
    textareaRef.current?.focus();
    // Optionally close the history panel
    setShowRightPanel(false);
  };


  const formatChatMessage = (content: string) => {
    // Check if content is already HTML (contains HTML tags like <div>, <table>, <p>, etc.)
    const htmlTags = /<(div|table|p|h[1-6]|ul|ol|li|tr|td|th|thead|tbody)\b[^>]*>/i;
    
    if (htmlTags.test(content)) {
      // Content is already HTML, render it directly with horizontal scroll support
      return (
        <div className="overflow-x-auto">
          <div 
            className="prose prose-sm max-w-none [&_table]:min-w-full [&_table]:table-auto [&_pre]:overflow-x-auto [&_pre]:max-w-full" 
            dangerouslySetInnerHTML={{ __html: content }} 
          />
        </div>
      );
    }

    // Preprocess content to add line breaks if missing
    let processedContent = content;
    
    // If content appears to be one long line, add line breaks intelligently
    if (!processedContent.includes('\n') || processedContent.split('\n').length < 3) {
      // Add line breaks before bullet points
      processedContent = processedContent.replace(/([.!?:])(\s*)(\*\s+)/g, '$1\n\n$3');
      
      // Add line breaks before section headers (text ending with colon followed by content)
      processedContent = processedContent.replace(/([.!?])\s+([A-Z][^:]+:)\s*([A-Z])/g, '$1\n\n$2\n$3');
      
      // Add line breaks after colons when followed by a capital letter or bullet
      processedContent = processedContent.replace(/:(\s*)([A-Z*])/g, ':\n$1$2');
      
      // Split long lists at bullet points
      processedContent = processedContent.replace(/(\*\s+[^*]+)(\*\s+)/g, '$1\n$2');
    }
    
    return processedContent
      .split('\n')
      .map((line, index) => {
        // Handle bold text **text**
        let formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-gray-900">$1</strong>');
        
        // Handle headers (###, ##, #)
        if (line.match(/^###\s+(.+)/)) {
          formatted = `<h3 class="text-base font-semibold text-gray-900 mt-3 mb-2">${line.replace(/^###\s+/, '')}</h3>`;
        } else if (line.match(/^##\s+(.+)/)) {
          formatted = `<h2 class="text-lg font-semibold text-gray-900 mt-4 mb-2">${line.replace(/^##\s+/, '')}</h2>`;
        } else if (line.match(/^#\s+(.+)/)) {
          formatted = `<h1 class="text-xl font-bold text-gray-900 mt-4 mb-3">${line.replace(/^#\s+/, '')}</h1>`;
        }
        
        // Handle section headers (text ending with colon)
        if (line.match(/^[A-Z][^:]+:$/)) {
          formatted = `<h3 class="text-base font-semibold text-gray-900 mt-3 mb-2">${formatted}</h3>`;
        }
        
        // Handle bullet points (- or • or *)
        if (line.trim().match(/^[-•*]\s+/)) {
          const bulletContent = formatted.replace(/^[-•*]\s*/, '');
          formatted = `<div style="margin-left: 1rem; display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
            <span style="color: #3B82F6; flex-shrink: 0;">•</span>
            <span>${bulletContent}</span>
          </div>`;
        }
        
        // Handle numbered lists (1., 2., etc.)
        if (/^\s*\d+\.\s/.test(line)) {
          formatted = `<div style="margin-left: 1rem; margin-bottom: 0.5rem;">${formatted}</div>`;
        }
        
        // Handle indented items (sub-bullets)
        if (line.match(/^\s{2,}[-•*]\s/)) {
          const indent = Math.floor((line.match(/^\s*/)?.[0].length || 0) / 2) * 1;
          const bulletContent = formatted.replace(/^\s*[-•*]\s*/, '');
          formatted = `<div style="margin-left: ${1 + indent}rem; display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
            <span style="color: #93C5FD; flex-shrink: 0;">◦</span>
            <span>${bulletContent}</span>
          </div>`;
        }
        
        // Highlight dosages
        formatted = formatted.replace(/(\d+\s*mg|\d+\s*mcg|\d+\s*g|\d+\s*ml)/gi, '<span class="bg-blue-50 text-blue-700 px-1 py-0.5 rounded text-xs font-medium">$1</span>');
        
        // Highlight medical terms
        const medicalTerms = [
          'pneumonitis', 'colitis', 'hepatitis', 'corticosteroids', 'immunosuppressants', 
          'prednisone', 'diarrhea', 'nausea', 'vomiting', 'rash', 'arthritis', 'myositis',
          'pancreatitis', 'uveitis', 'adrenal insufficiency'
        ];
        medicalTerms.forEach(term => {
          const regex = new RegExp(`\\b(${term})\\b`, 'gi');
          formatted = formatted.replace(regex, '<span class="text-indigo-600 font-medium">$1</span>');
        });
        
        // Don't render empty lines as separate elements
        if (!line.trim()) {
          return null;
        }
        
        // For regular text (not headers or lists), wrap in a paragraph-like span
        if (!line.match(/^<(h[1-3]|div)/) && !formatted.includes('<div')) {
          return (
            <span key={index} style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span dangerouslySetInnerHTML={{ __html: formatted }} />
            </span>
          );
        }
        
        return <span key={index} dangerouslySetInnerHTML={{ __html: formatted }} />;
      })
      .filter(Boolean); // Remove null entries
  };



  const [showExportMenu, setShowExportMenu] = useState(false);
  
  const exportChat = (exportFormat: 'txt' | 'pdf' | 'html') => {
    if (exportFormat === 'txt') {
      const content = messages.map(msg => 
        `[${format(msg.timestamp, 'yyyy-MM-dd HH:mm:ss')}] ${msg.role.toUpperCase()}: ${msg.content}`
      ).join('\n\n');
      
      const blob = new Blob([content], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `chat-export-${format(new Date(), 'yyyy-MM-dd-HHmmss')}.txt`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      toast.success('Chat exported as text file');
    } else if (exportFormat === 'pdf') {
      downloadPDF(messages, collectionName, drugNames);
      toast.success('Opening print dialog - select "Save as PDF"');
    } else if (exportFormat === 'html') {
      downloadHTML(messages, collectionName, drugNames);
      toast.success('Chat exported as HTML file');
    }
    
    setShowExportMenu(false);
  };

  const shareChat = () => {
    setIsShareModalOpen(true);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className={cn(
          "fixed z-50 bg-white shadow-2xl duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          isMaximized 
            ? 'inset-0 w-full h-full rounded-none' 
            : 'left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] w-[98vw] max-w-[1800px] h-[92vh] max-h-[900px] rounded-xl',
          "flex overflow-hidden border border-gray-200"
        )}>
          

          
          {/* Main Chat Area */}
          <div className="flex-1 flex flex-col bg-white">
            {/* Header */}
            <div className="px-8 py-6 border-b border-slate-200 bg-gradient-to-r from-blue-600 via-blue-700 to-indigo-700 text-white shadow-lg">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <DialogTitle className="text-2xl font-bold flex items-center gap-4">
                      <div className="p-3 bg-white/20 rounded-xl backdrop-blur-sm border border-white/20">
                        <MessageCircle className="h-6 w-6" />
                      </div>
                      {isMultipleFiles ? 'Multi-Drug Analysis Chat' : 'FDA Drug Assistant'}
                    </DialogTitle>
                    
                    <p className="text-blue-100 text-sm mt-2 font-medium">
                      {isMultipleFiles 
                        ? `Analyzing ${sourceFileIds.length} FDA documents for comprehensive insights`
                        : 'Powered by official FDA documentation and clinical data'
                      }
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem onClick={() => exportChat('txt')}>
                        <FileText className="h-4 w-4 mr-2" />
                        Export as Text
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => exportChat('pdf')}>
                        <FileDown className="h-4 w-4 mr-2" />
                        Export as PDF
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => exportChat('html')}>
                        <FileText className="h-4 w-4 mr-2" />
                        Export as HTML
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                  
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={shareChat}
                          className="h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200"
                        >
                          <Share2 className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Share conversation</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  
                  {/* Suggestions Button */}
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (rightPanelView === 'suggestions' && showRightPanel) {
                              setShowRightPanel(false);
                            } else {
                              setRightPanelView('suggestions');
                              setShowRightPanel(true);
                            }
                          }}
                          className={cn(
                            "h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200",
                            rightPanelView === 'suggestions' && showRightPanel && "bg-white/20"
                          )}
                        >
                          <Lightbulb className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Suggestions</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  
                  {/* Collection Button */}
                  {collectionName && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              if (rightPanelView === 'collection' && showRightPanel) {
                                setShowRightPanel(false);
                              } else {
                                setRightPanelView('collection');
                                setShowRightPanel(true);
                              }
                            }}
                            className={cn(
                              "h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200",
                              rightPanelView === 'collection' && showRightPanel && "bg-white/20"
                            )}
                          >
                            <FolderOpen className="h-4 w-4" />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Collection</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                  
                  {/* History Button */}
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (rightPanelView === 'history' && showRightPanel) {
                              setShowRightPanel(false);
                            } else {
                              setRightPanelView('history');
                              setShowRightPanel(true);
                            }
                          }}
                          className={cn(
                            "h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200",
                            rightPanelView === 'history' && showRightPanel && "bg-white/20"
                          )}
                        >
                          <History className="h-4 w-4" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>History</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                  
                  <Button
                    onClick={() => setIsMaximized(!isMaximized)}
                    variant="ghost"
                    size="sm"
                    className="h-10 w-10 p-0 text-white hover:bg-white/20 rounded-lg transition-all duration-200"
                    title={isMaximized ? "Restore" : "Maximize"}
                  >
                    {isMaximized ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                  </Button>
                  
                  <Button
                    onClick={onClose}
                    variant="ghost"
                    size="sm"
                    className="h-10 w-10 p-0 text-white hover:bg-red-500/20 hover:text-red-100 rounded-lg transition-all duration-200"
                    title="Close"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            {/* Main Content Area - Chat and Suggestions */}
            <div className="flex-1 flex overflow-hidden">
              {/* Messages Area */}
              <div className="flex-1 flex flex-col">
                <ScrollArea className="flex-1 bg-gradient-to-b from-slate-50 to-white">
                  <div className="w-full px-6 py-3 space-y-3">
                <AnimatePresence>
                  {messages.map((message, index) => {
                    const previousMessage = index > 0 ? messages[index - 1] : null;
                    const showDateSeparator = shouldShowDateSeparator(
                      message.timestamp,
                      previousMessage?.timestamp || null
                    );
                    
                    return (
                      <Fragment key={message.id}>
                        {showDateSeparator && (
                          <div className="flex items-center gap-3 my-4">
                            <div className="flex-1 h-px bg-slate-200" />
                            <span className="text-xs text-slate-500 font-medium px-2">
                              {getDateSeparatorText(message.timestamp)}
                            </span>
                            <div className="flex-1 h-px bg-slate-200" />
                          </div>
                        )}
                        
                    <motion.div
                      key={message.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                      transition={{ duration: 0.2, ease: "easeOut" }}
                      className={`flex gap-2 ${
                        message.role === 'user' ? 'justify-end' : 'justify-start'
                      }`}
                    >
                      {message.role === 'assistant' && (
                        <div className="flex-shrink-0">
                          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-sm">
                            <Bot className="h-3.5 w-3.5 text-white" />
                          </div>
                        </div>
                      )}
                      
                      <div className={cn(
                        "max-w-none flex-1 group relative",
                        message.role === 'user' ? 'max-w-[75%]' : 'max-w-[80%]'
                      )}>
                        <div
                          className={cn(
                            "rounded-lg shadow-sm border text-sm",
                            message.role === 'user'
                              ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white border-blue-300 rounded-tr-md px-3 py-2 shadow-md'
                              : 'bg-white border-slate-200 rounded-tl-md px-3 py-2'
                          )}
                        >
                          {message.isLoading ? (
                            <div className="flex items-center gap-2">
                              <div className="flex space-x-1">
                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                              </div>
                              <span className="text-slate-600 text-sm">{message.content}</span>
                            </div>
                          ) : (
                            <>
                              
                              {/* Message content */}
                              <div 
                                className={cn(
                                  "text-sm leading-relaxed",
                                  message.role === 'user' ? 'text-white [&_span]:!text-white [&_p]:!text-white [&_strong]:!text-white [&_em]:!text-white' : 'text-slate-800'
                                )}
                              >
                                {formatChatMessage(message.cited_content || message.content)}
                              </div>
                              
                              {/* Edited indicator */}
                              {message.isEdited && (
                                <div className="text-xs text-slate-500 mt-1">
                                  (edited)
                                </div>
                              )}
                              
                              {/* Intent and Confidence Information */}
                              {message.role === 'assistant' && (message.intent || message.confidence_scores) && (
                                <div className="mt-2 flex flex-wrap gap-2 text-xs">
                                  {message.intent && (
                                    <Badge variant="secondary" className="px-2 py-1">
                                      Intent: {message.intent.replace('_', ' ')}
                                    </Badge>
                                  )}
                                  {message.confidence_scores && (
                                    <Badge variant="secondary" className="px-2 py-1">
                                      Confidence: {Math.round(message.confidence_scores.retrieval_confidence * 100)}%
                                    </Badge>
                                  )}
                                </div>
                              )}
                              
                              {/* Source Documents */}
                              {message.role === 'assistant' && message.source_documents && message.source_documents.length > 0 && (
                                <EnhancedSourceDocuments documents={message.source_documents} className="mt-3" />
                              )}
                              
                              {/* Actions and Timestamp */}
                              {!message.isLoading && (
                                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100">
                                  <div className="flex items-center gap-1">
                                    {message.role === 'assistant' && (
                                      <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => copyMessage(message.content)}
                                        className="h-5 px-2 text-xs hover:bg-slate-100 rounded"
                                      >
                                        <Copy className="h-2.5 w-2.5 mr-1" />
                                        Copy
                                      </Button>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-2 text-xs text-slate-400 text-right">
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <span className="cursor-help">
                                            {format(message.timestamp, 'HH:mm')}
                                          </span>
                                        </TooltipTrigger>
                                        <TooltipContent>
                                          {getFullTimestamp(message.timestamp)}
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                    {message.role === 'user' && message.status && (
                                      <span className="flex items-center">
                                        {message.status === 'sending' && (
                                          <Loader2 className="h-3 w-3 animate-spin" />
                                        )}
                                        {message.status === 'sent' && (
                                          <Check className="h-3 w-3" />
                                        )}
                                        {message.status === 'delivered' && (
                                          <CheckCheck className="h-3 w-3" />
                                        )}
                                        {message.status === 'read' && (
                                          <CheckCheck className="h-3 w-3 text-blue-500" />
                                        )}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                      
                      {message.role === 'user' && (
                        <div className="flex-shrink-0">
                          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-slate-400 to-slate-600 flex items-center justify-center shadow-sm">
                            <User className="h-3.5 w-3.5 text-white" />
                          </div>
                        </div>
                      )}
                    </motion.div>
                      </Fragment>
                    );
                  })}
                  
                </AnimatePresence>
                    <div ref={messagesEndRef} />
                  </div>
                </ScrollArea>

                {/* Input Area */}
                <div className="border-t border-slate-200 bg-gradient-to-b from-slate-50 to-white">
                  <div className="p-4">
                    <div className="w-full">
                      <div className="flex gap-3">
                    <div className="flex-1 relative">
                      
                      <Textarea
                        ref={textareaRef}
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder={collectionName ? `Ask anything about ${collectionName}...` : `Ask anything about ${drugNames.join(', ')}...`}
                        className="w-full resize-none border border-slate-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 min-h-[60px] max-h-[120px] bg-slate-50 focus:bg-white"
                        disabled={isLoading}
                      />
                      {/* Character count removed */}
                    </div>
                    <div className="flex flex-col">
                      <Button
                        onClick={() => sendMessage(inputMessage)}
                        disabled={!inputMessage.trim() || isLoading}
                        className="h-[60px] px-4 bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white shadow-sm transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm"
                      >
                        {isLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <>
                            <Send className="h-4 w-4 mr-1" />
                            Send
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center gap-4">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          setMessages([messages[0]]);
                          setInputMessage('');
                          setSuggestions(getDefaultSuggestions());
                          createNewSession();
                        }}
                        className="flex items-center gap-2 text-sm hover:bg-slate-50 border-slate-200 rounded-md h-8 px-3 font-medium"
                      >
                        <RefreshCw className="h-4 w-4" />
                        New Chat
                      </Button>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                      <span className="flex items-center gap-1">
                        <AlertCircle className="h-3 w-3 text-blue-500" />
                        Press Enter to send • Shift+Enter for new line
                      </span>
                    </div>
                  </div>
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Right Side Panel - Suggestions or Collection Details */}
              <AnimatePresence>
                {showRightPanel && (
                  <motion.div
                    initial={{ width: 0, opacity: 0 }}
                    animate={{ width: 380, opacity: 1 }}
                    exit={{ width: 0, opacity: 0 }}
                    transition={{ duration: 0.3, ease: "easeInOut" }}
                    className="border-l border-slate-200 bg-gradient-to-b from-slate-50 to-white flex flex-col overflow-hidden"
                  >
                    {/* Panel Header */}
                    <div className="p-4 border-b border-slate-200 bg-white flex-shrink-0">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {rightPanelView === 'suggestions' && (
                            <>
                              <Lightbulb className="h-4 w-4 text-blue-600" />
                              <span className="text-sm font-semibold text-slate-800">Suggestions</span>
                            </>
                          )}
                          {rightPanelView === 'collection' && (
                            <>
                              <FolderOpen className="h-4 w-4 text-blue-600" />
                              <span className="text-sm font-semibold text-slate-800">{collectionName || 'Collection'}</span>
                            </>
                          )}
                          {rightPanelView === 'history' && (
                            <>
                              <History className="h-4 w-4 text-blue-600" />
                              <span className="text-sm font-semibold text-slate-800">Chat History</span>
                            </>
                          )}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setShowRightPanel(false)}
                          className="h-6 w-6 p-0"
                        >
                          <X className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    
                    {/* Panel Content */}
                    <div className="flex-1 flex flex-col overflow-hidden">
                      {rightPanelView === 'suggestions' ? (
                        <>
                          {isLoadingSuggestions && (
                            <div className="flex items-center justify-center p-4">
                              <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                            </div>
                          )}
                          <ScrollArea className="flex-1">
                            <div className="p-4">
                            <div className="space-y-2">
                              {suggestions.map((suggestion, idx) => (
                                <motion.div
                                  key={idx}
                                  initial={{ opacity: 0, y: 10 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{ delay: idx * 0.05 }}
                                  className="w-full"
                                >
                                  <Button
                                    variant="outline"
                                    onClick={() => handleSuggestionClick(suggestion)}
                                    disabled={isLoading}
                                    className="w-full justify-start text-left h-auto py-3 px-4 bg-white hover:bg-blue-50 hover:border-blue-300 border-slate-200 transition-all duration-150 overflow-hidden"
                                  >
                                    <div className="flex items-center gap-3 w-full">
                                      <Lightbulb className="h-3.5 w-3.5 text-blue-500 flex-shrink-0" />
                                      <span className="text-sm text-slate-700 leading-normal text-left flex-1 break-words whitespace-normal overflow-hidden">
                                        {suggestion}
                                      </span>
                                    </div>
                                  </Button>
                                </motion.div>
                              ))}
                            </div>
                          </div>
                          {suggestions.length === 0 && !isLoadingSuggestions && (
                            <div className="text-center p-4">
                              <div className="text-xs text-slate-500">
                                {messages.length <= 1 ? (
                                  <>
                                    <Lightbulb className="h-8 w-8 text-slate-300 mx-auto mb-2" />
                                    <p>Ask a question to see suggestions</p>
                                  </>
                                ) : (
                                  <p>No suggestions available</p>
                                )}
                              </div>
                            </div>
                          )}
                        </ScrollArea>
                      </>
                    ) : rightPanelView === 'collection' ? (
                      /* Collection Details View - Virtual Drug List */
                      <div className="flex-1 overflow-hidden p-4">
                        {collectionId ? (
                          <VirtualDrugList
                            collectionId={collectionId}
                            collectionName={collectionName || 'Collection'}
                            onDrugClick={(drugName) => {
                              // Optionally auto-fill the input with the drug name
                              setInputMessage(prev => prev ? `${prev} ${drugName}` : drugName);
                              textareaRef.current?.focus();
                            }}
                            height={350}
                            itemHeight={60}
                            className="h-full"
                          />
                        ) : (
                          <div className="text-center p-8">
                            <p className="text-sm text-gray-500">No collection available</p>
                          </div>
                        )}
                      </div>
                    ) : (
                      /* History View */
                      <div className="flex-1 flex flex-col overflow-hidden">
                        {loadingHistory && (
                          <div className="flex items-center justify-center p-4">
                            <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                            <span className="ml-2 text-sm text-slate-500">Loading history...</span>
                          </div>
                        )}
                        <ChatHistorySidebar
                          onSelectHistory={(item) => {
                            if (item.session_id) {
                              handleLoadHistorySession(item.session_id);
                            }
                          }}
                          onLoadQuery={handleLoadQuery}
                          className="flex-1 border-0"
                        />
                      </div>
                    )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
      
      {/* Share Modal */}
      {isShareModalOpen && sessionId && (
        <ShareChatModal
          isOpen={isShareModalOpen}
          onClose={() => setIsShareModalOpen(false)}
          messages={messages}
          sessionId={sessionId}
          collectionName={collectionName}
        />
      )}
    </Dialog>
  );
}