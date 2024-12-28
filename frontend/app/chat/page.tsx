// Minor update
"use client";

import { useState, useEffect, useRef, Suspense } from 'react';
import type { JSX } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { 
  Send, 
  ArrowLeft, 
  Bot, 
  User,
  Loader2,
  FileText,
  Sparkles,
  RefreshCw,
  Copy,
  MessageSquare,
  BookOpen,
  Info,
  ChevronDown,
  ChevronUp,
  Pill,
  AlertCircle
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { ChatMessageFormatter } from '@/components/dashboard/ChatMessageFormatter';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  drugName?: string;
  drugNames?: string[];
  isLoading?: boolean;
}

interface DrugInfo {
  source_file_id: number;
  drug_name: string;
  file_name: string;
}

function ChatPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  
  // Get file IDs or collection ID from URL parameters
  const fileParam = searchParams.get('file');
  const filesParam = searchParams.get('files');
  const collectionParam = searchParams.get('collection');
  
  // Get return navigation parameters
  const returnQuery = searchParams.get('returnQuery');
  const returnFilter = searchParams.get('returnFilter');
  const shouldReturnToSearch = searchParams.get('returnSearch') === 'true';
  
  const isCollection = !!collectionParam;
  const collectionId = collectionParam ? parseInt(collectionParam) : null;
  const isMultipleFiles = !!filesParam;
  const fileIds = isMultipleFiles 
    ? filesParam.split(',').map(id => parseInt(id))
    : fileParam ? [parseInt(fileParam)] : [];
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [drugInfo, setDrugInfo] = useState<DrugInfo[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [collectionInfo, setCollectionInfo] = useState<{name: string; description?: string} | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    // Generate session ID
    const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    setSessionId(newSessionId);
    
    // Load drug or collection information
    if (isCollection) {
      loadCollectionInfo();
    } else {
      loadDrugInfo();
    }
    
    // Add welcome message
    let welcomeContent = '';
    if (isCollection) {
      // Show loading state while collection info loads
      welcomeContent = `Loading collection information...`;
    } else if (isMultipleFiles) {
      welcomeContent = `Ready to analyze and compare multiple FDA drug documents.

What would you like to know?`;
    } else {
      welcomeContent = `Ready to provide information from FDA documentation.

What would you like to know about this medication?`;
    }
    
    setMessages([{
      id: '1',
      role: 'assistant',
      content: welcomeContent,
      timestamp: new Date()
    }]);
    
    // Load initial suggestions
    loadSuggestions();
  }, []);

  // Update welcome message when collection info loads
  useEffect(() => {
    if (isCollection && collectionInfo && drugInfo.length > 0) {
      const welcomeContent = `Ready to analyze the **"${collectionInfo.name}"** collection (${drugInfo.length} documents)${collectionInfo.description ? ` - ${collectionInfo.description}` : ''}.

How can I help you explore this collection?`;

      // Update the first message if it's the loading message
      setMessages(prev => {
        if (prev.length === 1 && prev[0].content.includes('Loading Collection Information')) {
          return [{
            id: '1',
            role: 'assistant',
            content: welcomeContent,
            timestamp: new Date()
          }];
        }
        return prev;
      });
    }
  }, [isCollection, collectionInfo, drugInfo]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadCollectionInfo = async () => {
    if (!collectionId) return;
    
    try {
      const response = await apiService.getCollectionDetails(collectionId);
      setCollectionInfo({
        name: response.collection.name,
        description: response.collection.description
      });
      
      // Load drug info from collection documents
      const drugInfoList: DrugInfo[] = [];
      for (const doc of response.documents) {
        drugInfoList.push({
          source_file_id: doc.id,
          drug_name: doc.drug_name || 'Unknown Drug',
          file_name: doc.file_name
        });
      }
      setDrugInfo(drugInfoList);
    } catch (error) {
      console.error('Failed to load collection information:', error);
    }
  };

  const loadDrugInfo = async () => {
    try {
      const drugInfoList: DrugInfo[] = [];
      
      for (const fileId of fileIds) {
        const response = await apiService.getSourceFile(fileId);
        drugInfoList.push({
          source_file_id: fileId,
          drug_name: response.drug_name || 'Unknown Drug',
          file_name: response.file_name
        });
      }
      
      setDrugInfo(drugInfoList);
    } catch (error) {
      console.error('Failed to load drug information:', error);
    }
  };

  const loadSuggestions = async () => {
    try {
      // Default suggestions based on context
      let defaultSuggestions: string[];
      
      if (isCollection) {
        defaultSuggestions = [
          'What are the main topics covered in this collection?',
          'Compare information across different documents',
          'Find all mentions of specific side effects',
          'Summarize key findings from all documents',
          'What patterns emerge across these documents?'
        ];
      } else if (isMultipleFiles) {
        defaultSuggestions = [
          'Compare the indications of these drugs',
          'What are the main differences in side effects?',
          'Compare the dosing regimens',
          'Which drug has more drug interactions?',
          'Compare the mechanisms of action'
        ];
      } else {
        defaultSuggestions = [
          'What is this drug used for?',
          'What are the common side effects?',
          'What is the recommended dosage?',
          'Are there any contraindications?',
          'What are the drug interactions?'
        ];
      }
      
      setSuggestions(defaultSuggestions);
    } catch (error) {
      console.error('Failed to load suggestions:', error);
    }
  };

  const sendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;
    
    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date(),
      drugNames: drugInfo.map(d => d.drug_name)
    };
    
    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    
    // Add loading message
    const loadingMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: 'Thinking...',
      timestamp: new Date(),
      isLoading: true
    };
    
    setMessages(prev => [...prev, loadingMessage]);
    
    try {
      let response;
      
      if (isCollection && collectionId) {
        // For collections, we need to query multiple documents
        // Get all file IDs from the collection's documents
        const collectionFileIds = drugInfo.map(d => d.source_file_id);
        
        const requestPayload = {
          message: message,
          source_file_ids: collectionFileIds,
          session_id: sessionId
        };
        
        response = await apiService.sendChatMessage(requestPayload);
      } else if (fileIds.length > 0) {
        // For specific files
        const requestPayload = {
          message: message,
          source_file_ids: fileIds,
          session_id: sessionId
        };
        
        response = await apiService.sendChatMessage(requestPayload);
      } else {
        // Use unified chat endpoint as fallback
        const requestPayload = { 
          message: message,
          session_id: sessionId || undefined,
          user_id: undefined // Will be set by backend from auth
        };

        response = await apiService.sendUnifiedChatMessage(requestPayload);
      }
      
      // Remove loading message and add actual response with source information
      setMessages(prev => {
        const filtered = prev.filter(msg => !msg.isLoading);
        
        // Add collection context to the response if in collection mode
        let enhancedContent = response.content;
        if (isCollection && collectionInfo && messages.length === 1) {
          // Only add context for the first real response (after welcome message)
          const collectionContext = `Based on analysis of ${drugInfo.length} documents in the "${collectionInfo.name}" collection:\n\n`;
          enhancedContent = collectionContext + response.content;
        }
        
        return [...filtered, {
          id: response.id || Date.now().toString(),
          role: 'assistant',
          content: enhancedContent,
          timestamp: new Date(response.timestamp || Date.now()),
          drugNames: drugInfo.map(d => d.drug_name)
        }];
      });
      
      // Update suggestions based on conversation
      // You could make this smarter by analyzing the conversation context
      if (messages.length > 2) {
        let contextualSuggestions: string[];
        
        if (isCollection) {
          contextualSuggestions = [
            'Show me common themes across all documents',
            'What are the key differences between documents?',
            'Find specific information across the collection',
            'Summarize findings by document type',
            'Compare methodologies used in different documents'
          ];
        } else if (isMultipleFiles) {
          contextualSuggestions = [
            'Tell me more about the efficacy differences',
            'Compare the safety profiles in detail',
            'Which drug is preferred for elderly patients?',
            'Compare the clinical trial results',
            'What about cost considerations?'
          ];
        } else {
          contextualSuggestions = [
            'Tell me more about the clinical trials',
            'What about use in special populations?',
            'How does it compare to similar drugs?',
            'What monitoring is required?',
            'Are there any recent safety updates?'
          ];
        }
        
        setSuggestions(contextualSuggestions);
      }
      
    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Remove loading message and show error
      setMessages(prev => {
        const filtered = prev.filter(msg => !msg.isLoading);
        
        let errorMessage = 'I apologize, but I encountered an error processing your request.';
        
        if (error instanceof Error) {
          if (error.message.includes('404')) {
            errorMessage = 'I apologize, but the chat service is currently unavailable. Please ensure the backend server is running on port 8090.';
          } else if (error.message.includes('Network')) {
            errorMessage = 'I apologize, but I cannot connect to the chat service. Please check your internet connection and ensure the backend server is running.';
          }
        }
        
        return [...filtered, {
          id: Date.now().toString(),
          role: 'assistant',
          content: errorMessage,
          timestamp: new Date()
        }];
      });
      
      toast.error('Failed to connect to chat service. Please check if the backend is running.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputMessage(suggestion);
    textareaRef.current?.focus();
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputMessage);
    }
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
    toast.success('Message copied to clipboard');
  };

  const handleNewChat = () => {
    const params = new URLSearchParams();
    if (isMultipleFiles) {
      params.set('files', filesParam!);
    } else {
      params.set('file', fileParam!);
    }
    router.push(`/chat?${params.toString()}`);
    router.refresh();
  };

  const formatResponse = (text: string) => {
    // Process text to handle line breaks and sections
    const processedText = text
      // First, standardize line breaks and remove extra spaces
      .replace(/\r\n/g, '\n')
      .replace(/\n{3,}/g, '\n\n')
      
      // Handle markdown patterns
      .replace(/\*\*([^*]+)\*\*/g, '$1') // Remove ** around text
      .replace(/\*\*/g, '') // Remove any remaining **
      .replace(/\* \*/g, '*') // Convert * * to single *
      .replace(/\*/g, '•') // Convert * to bullet
      .replace(/•\s*•/g, '•') // Remove double bullets
      
      // Standardize bullet points
      .replace(/^[•\-]\s*/gm, '• ') // Convert bullets at start of lines
      .replace(/\n[•\-]\s*/g, '\n• ') // Convert bullets after newlines
      
      // Fix common formatting issues
      .replace(/([^:])(\n+)([•])/g, '$1\n\n$3') // Add proper spacing before bullets
      .replace(/([.:])([A-Z])/g, '$1\n$2') // Split sentences that got merged
      .replace(/\n{3,}/g, '\n\n') // Clean up multiple line breaks again
      .replace(/\s+/g, ' ') // Clean up multiple spaces
      .split('\n')
      .map(line => line.trim()) // Trim each line
      .filter(line => line) // Remove empty lines
      .join('\n')
      .trim();

    // Define text types
    type TextType = 'header' | 'bullet' | 'empty' | 'text';

    // Helper function to determine text type
    const getTextType = (line: string): TextType => {
      line = line.trim();
      if (line.endsWith(':')) return 'header';
      if (line.startsWith('•')) return 'bullet';
      if (line.length === 0) return 'empty';
      return 'text';
    };

    // Helper function to get indentation level
    const getIndentationLevel = (line: string): number => {
      const match = line.match(/^\s*/);
      return match ? Math.floor(match[0].length / 2) : 0;
    };

    const renderContent = () => {
      const lines = processedText.split('\n');
      let currentIndentLevel = 0;
      let inList = false;
      let previousWasHeader = false;

      return lines.map((line, index) => {
        const textType = getTextType(line);
        const indentLevel = getIndentationLevel(line);

        // Update list state
        if (textType === 'bullet') {
          if (!inList) {
            inList = true;
            currentIndentLevel = indentLevel;
          }
        } else if (textType === 'header') {
          inList = false;
          currentIndentLevel = 0;
          previousWasHeader = true;
        } else {
          if (!previousWasHeader) {
            inList = false;
            currentIndentLevel = 0;
          }
          previousWasHeader = false;
        }

        // Calculate relative indentation for nested lists
        const relativeIndent = inList ? indentLevel - currentIndentLevel : 0;

        switch (textType) {
          case 'header':
            return (
              <h3 key={index} className="text-lg font-medium text-gray-800 mt-6 mb-2">
                {line.trim()}
              </h3>
            );

          case 'bullet':
            return (
              <div 
                key={index} 
                className="flex items-start gap-2 my-1.5"
                style={{ marginLeft: `${relativeIndent * 1.5}rem` }}
              >
                <span className="text-gray-400 mt-1">•</span>
                <span className="text-sm text-gray-700 flex-1">
                  {line.substring(line.indexOf('•') + 1).trim()}
                </span>
              </div>
            );

          case 'empty':
            return <div key={index} className="h-2" />;

          default:
            return (
              <p key={index} className="text-sm text-gray-700 my-2">
                {line.trim()}
              </p>
            );
        }
      });
    };

    return (
      <div className="space-y-2">
        <div className="bg-white rounded-lg shadow-sm p-6 border border-gray-100">
          <div className="prose prose-sm max-w-none">
            {renderContent()}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-full px-4 sm:px-6 lg:px-8">
          <div className="py-2 flex items-center justify-between">
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
              className="hover:bg-gray-100 border-gray-300 text-gray-700 btn-professional-subtle"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to {shouldReturnToSearch ? 'Search Results' : 'Dashboard'}
            </Button>
            
            {/* Header Info */}
            <div className="flex items-center gap-4">
              <div className="hidden md:flex items-center gap-2">
                {isCollection && collectionInfo ? (
                  <Badge 
                    variant="outline" 
                    className="border-indigo-300 text-indigo-700 bg-indigo-50"
                  >
                    <BookOpen className="h-3 w-3 mr-1" />
                    Collection: {collectionInfo.name}
                  </Badge>
                ) : (
                  drugInfo.map((drug, index) => (
                    <Badge 
                      key={drug.source_file_id} 
                      variant="outline" 
                      className="border-gray-300 text-gray-700"
                    >
                      <FileText className="h-3 w-3 mr-1" />
                      {drug.drug_name}
                    </Badge>
                  ))
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNewChat}
                className="border-gray-300 text-gray-700 hover:bg-gray-50 btn-professional-subtle"
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                New Chat
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-full px-4 sm:px-6 lg:px-8 py-4">
        {/* Page Title */}
        <div className="mb-6">
          <h1 className="page-title">
            {isCollection ? 'Collection Chat' : isMultipleFiles ? 'Multi-Drug Analysis' : 'Drug Information Chat'}
          </h1>
          <p className="text-gray-600 mt-1">
            {isCollection 
              ? `Explore documents in "${collectionInfo?.name || 'this collection'}" with AI assistance`
              : `Ask questions about ${isMultipleFiles ? 'these FDA-approved drugs' : 'this FDA-approved drug'} based on official documentation`
            }
          </p>
        </div>

        {/* Main Chat Area */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Chat Messages */}
          <div className="xl:col-span-9">
            <Card className="shadow-lg border-0 h-[calc(100vh-240px)] flex flex-col bg-white overflow-hidden">
              <CardContent className="flex-1 overflow-y-auto p-0 bg-gradient-to-b from-gray-50/50 to-white">
                <div className="h-full">
                  {messages.length === 0 ? (
                    <div className="h-full flex items-center justify-center p-8">
                      <div className="text-center max-w-lg">
                        <div className="bg-gradient-to-br from-blue-500 to-blue-600 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg">
                          <Bot className="h-10 w-10 text-white" />
                        </div>
                        <h3 className="text-xl font-semibold text-gray-900 mb-2">Welcome to FDA Drug Chat</h3>
                        <p className="text-gray-600 mb-6">I'm here to help you understand FDA drug documentation. Ask me anything!</p>
                        <div className="flex flex-wrap justify-center gap-2">
                          {suggestions.slice(0, 3).map((suggestion, index) => (
                            <Button
                              key={index}
                              variant="outline"
                              size="sm"
                              onClick={() => handleSuggestionClick(suggestion)}
                              className="text-sm border-blue-300 text-blue-600 hover:bg-blue-50 btn-professional-subtle"
                            >
                              {suggestion}
                            </Button>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="p-6 space-y-6">
                      {messages.map((message, index) => {
                        const showTimestamp = index === 0 || 
                          (message.timestamp.getTime() - messages[index - 1].timestamp.getTime() > 300000); // 5 minutes
                        
                        return (
                          <div key={message.id}>
                            {showTimestamp && (
                              <div className="flex justify-center my-4">
                                <span className="text-xs text-gray-500 bg-gray-100 px-3 py-1 rounded-full">
                                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                              </div>
                            )}
                            <div
                              className={`flex gap-3 ${
                                message.role === 'user' ? 'justify-end' : 'justify-start'
                              }`}
                            >
                              {message.role === 'assistant' && (
                                <div className="flex-shrink-0">
                                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center shadow-md">
                                    <Bot className="h-5 w-5 text-white" />
                                  </div>
                                </div>
                              )}
                              
                              <div
                                className={`max-w-[80%] ${
                                  message.role === 'user'
                                    ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white rounded-2xl rounded-tr-md shadow-md'
                                    : 'bg-white border border-gray-200 rounded-2xl rounded-tl-md shadow-md'
                                } px-5 py-4 transition-all duration-200 hover:shadow-lg`}
                              >
                                {message.isLoading ? (
                                  <div className="flex items-center gap-3">
                                    <div className="flex space-x-1">
                                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                                    </div>
                                    <span className="text-gray-500 text-sm">Analyzing FDA documents...</span>
                                  </div>
                                ) : (
                                  <>
                                    {message.role === 'user' ? (
                                      <p className="text-sm leading-relaxed">{message.content}</p>
                                    ) : (
                                      message.content.includes("IMJUDO") ? formatResponse(message.content) : <p className="text-sm text-gray-800">{message.content}</p>
                                    )}
                                    {message.role === 'assistant' && !message.isLoading && (
                                      <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
                                        <Button
                                          variant="ghost"
                                          size="sm"
                                          onClick={() => copyMessage(message.content)}
                                          className="h-7 px-2 text-xs text-gray-500 hover:text-gray-700 hover:bg-blue-50 btn-professional-subtle"
                                        >
                                          <Copy className="h-3 w-3 mr-1" />
                                          Copy
                                        </Button>
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                              
                              {message.role === 'user' && (
                                <div className="flex-shrink-0">
                                  <div className="h-10 w-10 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 flex items-center justify-center shadow-md">
                                    <User className="h-5 w-5 text-white" />
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                      <div ref={messagesEndRef} />
                    </div>
                  )}
                </div>
              </CardContent>
              
              {/* Input Area */}
              <div className="border-t bg-white p-6">
                <div className="flex gap-3 items-end">
                  <div className="flex-1">
                    <Textarea
                      ref={textareaRef}
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="Type your message here..."
                      className="w-full resize-none bg-gray-50 border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm hover:bg-gray-100 transition-colors duration-200"
                      rows={3}
                      disabled={isLoading}
                    />
                    <div className="flex items-center justify-between mt-2">
                      <p className="text-xs text-gray-500">
                        Press Enter to send, Shift+Enter for new line
                      </p>
                      <p className="text-xs text-gray-500">
                        {inputMessage.length}/2000
                      </p>
                    </div>
                  </div>
                  <Button
                    onClick={() => sendMessage(inputMessage)}
                    disabled={!inputMessage.trim() || isLoading}
                    className="px-6 py-6 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-lg btn-professional transition-all duration-200 transform hover:scale-105"
                  >
                    {isLoading ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Send className="h-5 w-5" />
                    )}
                  </Button>
                </div>
              </div>
            </Card>
          </div>

          {/* Suggestions Sidebar */}
          <div className="xl:col-span-3 space-y-6">
            <Card className="shadow-lg border-0">
              <CardHeader className="bg-gradient-to-r from-blue-50 to-indigo-50 border-b">
                <CardTitle className="text-lg font-semibold flex items-center gap-2 text-gray-900">
                  <Sparkles className="h-5 w-5 text-blue-600" />
                  Suggested Questions
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-2">
                {suggestions.map((suggestion, index) => (
                  <Button
                    key={index}
                    variant="outline"
                    className="w-full justify-start text-left h-auto py-3 px-4 border hover:bg-blue-50 hover:border-blue-300 transition-all duration-200 group btn-professional-subtle"
                    onClick={() => handleSuggestionClick(suggestion)}
                    disabled={isLoading}
                  >
                    <span className="text-sm text-gray-700 group-hover:text-blue-700">{suggestion}</span>
                  </Button>
                ))}
              </CardContent>
            </Card>

            {/* Document Info */}
            <Card className="shadow-lg border-0">
              <CardHeader className="bg-gradient-to-r from-indigo-50 to-purple-50 border-b">
                <CardTitle className="text-lg font-semibold flex items-center gap-2 text-gray-900">
                  <Info className="h-5 w-5 text-indigo-600" />
                  {isCollection ? 'Collection Information' : 'Document Information'}
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-4">
                {isCollection && collectionInfo && (
                  <div className="p-3 bg-indigo-50 rounded-lg border border-indigo-100 mb-3">
                    <div className="flex items-center gap-2 mb-1">
                      <BookOpen className="h-4 w-4 text-indigo-600" />
                      <p className="font-medium text-sm text-indigo-900">{collectionInfo.name}</p>
                    </div>
                    {collectionInfo.description && (
                      <p className="text-xs text-indigo-700 ml-6">{collectionInfo.description}</p>
                    )}
                    <p className="text-xs text-indigo-600 ml-6 mt-1">{drugInfo.length} documents in collection</p>
                  </div>
                )}
                {drugInfo.map((drug) => (
                  <div key={drug.source_file_id} className="p-3 bg-gray-50 rounded-lg space-y-1 border border-gray-100">
                    <div className="flex items-center gap-2">
                      <Pill className="h-4 w-4 text-indigo-600" />
                      <p className="font-medium text-sm text-gray-900">{drug.drug_name}</p>
                    </div>
                    <p className="text-xs text-gray-600 ml-6">{drug.file_name}</p>
                  </div>
                ))}
                <div className="pt-4 border-t border-gray-200">
                  <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                    <div className="flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-xs font-medium text-amber-800 mb-1">Important Notice</p>
                        <p className="text-xs text-amber-700 leading-relaxed">
                          Responses are based on FDA documents and may not include recent updates. Always consult healthcare professionals for medical advice.
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500 mx-auto mb-4" />
          <p className="text-gray-600">Loading chat...</p>
        </div>
      </div>
    }>
      <ChatPageContent />
    </Suspense>
  );
}