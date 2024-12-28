"use client";

import { useState, useEffect, useRef } from 'react';
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
  ChevronDown,
  AlertCircle,
  ArrowRight,
  Lightbulb,
  MessageCircle,
  Maximize2,
  Minimize2
} from 'lucide-react';
import { apiService } from '@/services/api';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isLoading?: boolean;
  suggestions?: string[];
}

interface ChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  sourceFileIds: number[];
  drugNames: string[];
}

const quickSuggestions = [
  "What are the main side effects?",
  "Tell me about drug interactions",
  "What is the recommended dosage?",
  "Explain the contraindications",
  "What are the warnings and precautions?",
  "Describe the mechanism of action"
];

export function ChatModal({ isOpen, onClose, sourceFileIds, drugNames }: ChatModalProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isMultipleFiles = sourceFileIds.length > 1;

  useEffect(() => {
    if (isOpen) {
      // Initialize with welcome message
      const welcomeContent = isMultipleFiles
        ? `I can help you compare and analyze information across these ${sourceFileIds.length} drugs: **${drugNames.filter(Boolean).join(', ') || 'FDA documents'}**. What would you like to know?`
        : `I can provide detailed information about **${drugNames[0] || 'this FDA document'}** based on official FDA documentation. What would you like to know?`;
      
      const suggestions = isMultipleFiles 
        ? [
            `Compare side effects between ${drugNames.filter(Boolean).slice(0, 2).join(' and ') || 'these drugs'}`,
            "Which drug has fewer interactions?",
            "Compare the dosage recommendations",
            "What are the key differences?"
          ]
        : quickSuggestions.slice(0, 4);
      
      setMessages([{
        id: '1',
        role: 'assistant',
        content: welcomeContent,
        timestamp: new Date(),
        suggestions
      }]);
      
      // Focus input
      setTimeout(() => textareaRef.current?.focus(), 100);
    }
  }, [isOpen, sourceFileIds, drugNames, isMultipleFiles]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const sendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return;
    
    // Add user message
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: message,
      timestamp: new Date()
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
      // Use document-specific chat endpoint for DocXAI
      const requestPayload: any = { 
        message: message
      };

      // Add source file ID based on sourceFileIds prop
      if (sourceFileIds && sourceFileIds.length > 1) {
        // Multiple files - use source_file_ids
        requestPayload.source_file_ids = sourceFileIds;
      } else if (sourceFileIds && sourceFileIds.length === 1) {
        // Single file - use source_file_id
        requestPayload.source_file_id = sourceFileIds[0];
      }

      const response = await apiService.sendChatMessage(requestPayload);
      
      // Remove loading message and add actual response
      setMessages(prev => {
        const filtered = prev.filter(msg => !msg.isLoading);
        
        // Generate follow-up suggestions based on the topic
        const suggestions = [
          "Tell me more about this",
          "Are there any alternatives?",
          "What should I be careful about?",
          "Can you explain in simpler terms?"
        ];
        
        return [...filtered, {
          id: response.id || Date.now().toString(),
          role: 'assistant',
          content: response.content,
          timestamp: new Date(response.timestamp || Date.now()),
          suggestions
        }];
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Remove loading message and show error
      setMessages(prev => {
        const filtered = prev.filter(msg => !msg.isLoading);
        
        let errorMessage = 'I apologize, but I encountered an error processing your request.';
        
        if (error instanceof Error) {
          if (error.message.includes('404')) {
            errorMessage = 'The chat service is currently unavailable. Please ensure the backend server is running on port 8090.';
          } else if (error.message.includes('401')) {
            errorMessage = 'Authentication error. Please log in again.';
          } else if (error.message.includes('Invalid response')) {
            errorMessage = 'The server returned an invalid response. Please try again.';
          } else {
            errorMessage = `Error: ${error.message}`;
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
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputMessage);
    }
  };

  const copyMessage = (content: string) => {
    navigator.clipboard.writeText(content);
    toast.success('Copied to clipboard');
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputMessage(suggestion);
    textareaRef.current?.focus();
    setShowSuggestions(false);
  };


  const formatChatMessage = (content: string) => {
    // Check if content is already HTML (contains HTML tags like <div>, <table>, <p>, etc.)
    const htmlTags = /<(div|table|p|h[1-6]|ul|ol|li|tr|td|th|thead|tbody)\b[^>]*>/i;
    
    if (htmlTags.test(content)) {
      // Content is already HTML, render it directly
      return <div dangerouslySetInnerHTML={{ __html: content }} />;
    }

    // Preprocess content to add line breaks if missing
    let processedContent = content;
    
    // If content appears to be one long line, add line breaks intelligently
    if (!processedContent.includes('\n') || processedContent.split('\n').length < 3) {
      // Add line breaks before bullet points
      processedContent = processedContent.replace(/([.!?:])(\s*)(\*\s+)/g, '$1\n\n$3');
      
      // Add line breaks before section headers
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
        
        // Handle headers
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
        
        // Handle bullet points
        if (line.trim().match(/^[-•*]\s+/)) {
          const bulletContent = formatted.replace(/^[-•*]\s*/, '');
          formatted = `<div style="margin-left: 1rem; display: flex; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.5rem;">
            <span style="color: #3B82F6; flex-shrink: 0;">•</span>
            <span>${bulletContent}</span>
          </div>`;
        }
        
        // Handle numbered lists
        if (/^\s*\d+\.\s/.test(line)) {
          formatted = `<div style="margin-left: 1rem; margin-bottom: 0.5rem;">${formatted}</div>`;
        }
        
        // Handle indented items
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
        
        // Don't render empty lines
        if (!line.trim()) {
          return null;
        }
        
        // For regular text, wrap in a paragraph-like span
        if (!line.match(/^<(h[1-3]|div)/) && !formatted.includes('<div')) {
          return (
            <span key={index} style={{ display: 'block', marginBottom: '0.75rem' }}>
              <span dangerouslySetInnerHTML={{ __html: formatted }} />
            </span>
          );
        }
        
        return <span key={index} dangerouslySetInnerHTML={{ __html: formatted }} />;
      })
      .filter(Boolean);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content className={`fixed z-50 grid gap-4 border bg-background shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 ${isMaximized ? 'inset-0 w-full h-full' : 'left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%] w-[90vw] max-w-7xl h-[85vh]'} p-0 flex flex-col overflow-hidden rounded-lg`}>
        <DialogHeader className="px-6 py-5 border-b bg-gradient-to-r from-blue-600 to-indigo-700 text-white">
          <div className="flex items-start justify-between">
            <div>
              <DialogTitle className="text-2xl font-bold flex items-center gap-3 mb-2">
                <div className="p-2 bg-white/20 rounded-lg backdrop-blur-sm">
                  <MessageCircle className="h-6 w-6" />
                </div>
                {isMultipleFiles ? 'Multi-Drug Analysis' : 'FDA Drug Assistant'}
              </DialogTitle>
              <div className="flex items-center gap-2 flex-wrap">
                {drugNames.map((name, index) => (
                  <Badge key={index} className="bg-white/20 text-white border-white/30 backdrop-blur-sm">
                    <FileText className="h-3 w-3 mr-1" />
                    {name}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsMaximized(!isMaximized)}
                className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title={isMaximized ? "Restore" : "Maximize"}
              >
                {isMaximized ? <Minimize2 className="h-5 w-5" /> : <Maximize2 className="h-5 w-5" />}
              </button>
              <button
                onClick={onClose}
                className="p-2 hover:bg-white/20 rounded-lg transition-colors"
                title="Close"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        </DialogHeader>

        {/* Messages Area */}
        <ScrollArea className="flex-1 bg-gray-50">
          <div className="max-w-4xl mx-auto p-6 space-y-6">
            <AnimatePresence>
              {messages.map((message, index) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                  className={`flex gap-4 ${
                    message.role === 'user' ? 'justify-end' : 'justify-start'
                  }`}
                >
                  {message.role === 'assistant' && (
                    <div className="flex-shrink-0">
                      <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
                        <Bot className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  )}
                  
                  <div className="flex-1 max-w-[80%]">
                    <div
                      className={`${
                        message.role === 'user'
                          ? 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-2xl rounded-tr-md shadow-lg'
                          : 'bg-white border border-gray-200 rounded-2xl rounded-tl-md shadow-md'
                      } px-5 py-4`}
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
                          <div className="text-sm leading-relaxed">
                            {formatChatMessage(message.content)}
                          </div>
                          
                          
                          {/* Actions */}
                          {message.role === 'assistant' && !message.isLoading && (
                            <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
                              <div className="flex items-center gap-2">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => copyMessage(message.content)}
                                  className="h-8 px-3 text-xs hover:bg-blue-50 hover:text-blue-700 btn-professional-subtle"
                                >
                                  <Copy className="h-3 w-3 mr-1" />
                                  Copy
                                </Button>
                              </div>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                    
                    {/* Suggestions */}
                    {message.suggestions && message.role === 'assistant' && !message.isLoading && (
                      <motion.div
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="mt-3 space-y-2"
                      >
                        <div className="flex items-center gap-2 text-xs text-gray-500">
                          <Lightbulb className="h-3 w-3" />
                          <span>Suggested questions:</span>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          {message.suggestions.map((suggestion, idx) => (
                            <button
                              key={idx}
                              onClick={() => handleSuggestionClick(suggestion)}
                              className="px-3 py-1.5 bg-white border border-gray-200 rounded-full text-xs text-gray-700 hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700 transition-all duration-200 flex items-center gap-1 group"
                            >
                              {suggestion}
                              <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </button>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </div>
                  
                  {message.role === 'user' && (
                    <div className="flex-shrink-0">
                      <div className="h-12 w-12 rounded-2xl bg-gradient-to-br from-gray-400 to-gray-600 flex items-center justify-center shadow-lg">
                        <User className="h-6 w-6 text-white" />
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="border-t border-gray-200 bg-white">
          {/* Quick Actions */}
          {showSuggestions && messages.length === 1 && (
            <div className="border-b border-gray-100 p-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles className="h-4 w-4 text-blue-500" />
                <span className="text-sm font-medium text-gray-700">Quick Questions</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {(isMultipleFiles ? [
                  `Compare side effects`,
                  `Which is more effective?`,
                  `Drug interactions comparison`,
                  `Dosage differences`,
                  `Cost comparison`,
                  `Safety profiles`
                ] : quickSuggestions).map((suggestion, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="px-4 py-2 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-xl text-sm text-gray-700 hover:from-blue-100 hover:to-indigo-100 hover:border-blue-300 transition-all duration-200 text-left flex items-center gap-2 group"
                  >
                    <MessageSquare className="h-4 w-4 text-blue-500 flex-shrink-0" />
                    <span className="flex-1">{suggestion}</span>
                    <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity text-blue-500" />
                  </button>
                ))}
              </div>
            </div>
          )}
          
          <div className="p-4">
            <div className="flex gap-3">
              <div className="flex-1 relative">
                <Textarea
                  ref={textareaRef}
                  value={inputMessage}
                  onChange={(e) => {
                    setInputMessage(e.target.value);
                    setIsTyping(e.target.value.length > 0);
                  }}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask anything about the drug(s)..."
                  className="w-full resize-none border-2 border-gray-200 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 pr-12"
                  rows={3}
                  disabled={isLoading}
                />
                {isTyping && (
                  <div className="absolute bottom-3 right-3">
                    <Badge variant="secondary" className="text-xs">
                      {inputMessage.length} chars
                    </Badge>
                  </div>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Button
                  onClick={() => sendMessage(inputMessage)}
                  disabled={!inputMessage.trim() || isLoading}
                  className="h-full px-6 bg-gradient-to-r from-blue-600 to-indigo-700 hover:from-blue-700 hover:to-indigo-800 text-white shadow-lg btn-professional transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isLoading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                  ) : (
                    <>
                      <Send className="h-5 w-5 mr-2" />
                      Send
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setMessages([messages[0]]);
                    setInputMessage('');
                    setShowSuggestions(true);
                  }}
                  className="flex items-center gap-1 border-gray-300 text-gray-700 hover:bg-gray-50 btn-professional-subtle"
                >
                  <RefreshCw className="h-3 w-3" />
                  Reset
                </Button>
              </div>
            </div>
            <div className="flex items-center justify-between mt-3">
              <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  Press Enter to send • Shift+Enter for new line
                </span>
              </div>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <Sparkles className="h-3 w-3 text-blue-500" />
                <span>AI-powered analysis</span>
              </div>
            </div>
          </div>
        </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </Dialog>
  );
}