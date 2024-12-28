"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, FileText, Loader2, MessageSquare, X, Sparkles, Clock } from "lucide-react";
import { apiService } from "../../services/api";

interface ChatMessage {
  id: string;
  type: "user" | "assistant";
  content: string;
  timestamp: Date;
  contentType?: "markdown" | "html";
}

interface ChatInterfaceProps {
  selectedDrug?: {
    id: string;
    drug_name: string;
    indication: string;
    manufacturer: string;
  } | null;
  onClose?: () => void;
}

// Utility function to format chat messages with line breaks and markdown
const formatChatMessage = (content: string, contentType?: string) => {
  // Check if content is HTML
  if (contentType === 'html' || /<(div|table|p|h[1-6]|ul|ol|li|tr|td|th|thead|tbody)\b[^>]*>/i.test(content)) {
    return (
      <div className="overflow-x-auto max-w-full">
        <div 
          className="prose prose-sm max-w-none [&_table]:min-w-full [&_table]:table-auto [&_pre]:overflow-x-auto [&_pre]:max-w-full" 
          dangerouslySetInnerHTML={{ __html: content }} 
        />
      </div>
    );
  }
  
  // Original markdown formatting for non-HTML content
  return content
    .split('\n')
    .map((line, index) => {
      // Handle bold text **text**
      let formatted = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      
      // Handle bullet points (- or •)
      if (line.trim().startsWith('- ') || line.trim().startsWith('• ')) {
        formatted = `<span style="margin-left: 1rem;">• ${formatted.replace(/^[-•]\s*/, '')}</span>`;
      }
      
      // Handle numbered lists (1., 2., etc.)
      if (/^\s*\d+\.\s/.test(line)) {
        formatted = `<span style="margin-left: 1rem;">${formatted}</span>`;
      }
      
      // Handle indented items (  - or    - for sub-bullets)
      if (line.match(/^\s{2,}[-•]\s/)) {
        const indent = Math.floor((line.match(/^\s*/)?.[0].length || 0) / 2) * 1;
        formatted = `<span style="margin-left: ${1 + indent}rem;">• ${formatted.replace(/^\s*[-•]\s*/, '')}</span>`;
      }
      
      return (
        <span key={index} style={{ display: 'block', marginBottom: '0.25rem' }}>
          <span dangerouslySetInnerHTML={{ __html: formatted }} />
        </span>
      );
    });
};

export function ChatInterface({ selectedDrug, onClose }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Add welcome message when component mounts or drug changes
    const welcomeMessage: ChatMessage = {
      id: Date.now().toString(),
      type: "assistant",
      content: selectedDrug 
        ? `Hello! I'm here to help you learn about ${selectedDrug.drug_name}. You can ask me questions about its indication, dosage, efficacy, safety profile, or any other aspect of this drug. What would you like to know?`
        : "Hello! I'm your FDA document assistant. You can ask me questions about any of the drugs in our database, their indications, safety profiles, dosing, or clinical trial data. How can I help you today?",
      timestamp: new Date()
    };
    setMessages([welcomeMessage]);
  }, [selectedDrug]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: "user",
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);

    try {
      // Use unified chat endpoint for better fallback support
      const requestPayload = { 
        message: inputValue,
        session_id: localStorage.getItem('session_id') || undefined,
        user_id: undefined // Will be set by backend from auth
      };
      
      const response = await apiService.sendUnifiedChatMessage(requestPayload);
      
      const assistantMessage: ChatMessage = {
        id: response.id,
        type: "assistant",
        content: response.content,
        timestamp: new Date(response.timestamp),
        contentType: "html"
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: "assistant",
        content: "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-xl border border-blue-100/50 backdrop-blur-xl">
      {/* Enhanced Header */}
      <div className="flex items-center justify-between p-6 border-b border-blue-100/50 bg-gradient-to-r from-blue-600/5 to-indigo-600/5">
        <div className="flex items-center space-x-4">
          <div className="relative">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
              <MessageSquare className="w-6 h-6 text-white" />
            </div>
            <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-xl bg-gradient-to-r from-blue-800 to-indigo-700 bg-clip-text text-transparent">
              {selectedDrug ? `Chat about ${selectedDrug.drug_name}` : "FDA Document Assistant"}
            </h3>
            <p className="text-sm text-blue-600/70 font-medium">
              {selectedDrug ? "Ask questions about this drug" : "Ask questions about any FDA document"}
            </p>
          </div>
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-blue-100/50 rounded-full">
            <Sparkles className="w-4 h-4 text-blue-600" />
            <span className="text-xs font-semibold text-blue-700">AI Assistant</span>
          </div>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-xl hover:bg-white/50 transition-all duration-200"
          >
            <X className="w-6 h-6" />
          </button>
        )}
      </div>

      {/* Enhanced Messages Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-blue-200 scrollbar-track-transparent">
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`flex gap-3 animate-slide-in ${message.type === "user" ? "justify-end" : "justify-start"}`}
            style={{ animationDelay: `${messages.length > 5 ? 0 : index * 0.1}s` }}
          >
                {message.type === "assistant" && (
              <div className="relative flex-shrink-0">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                  <Bot className="w-5 h-5 text-white" />
                </div>
                <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white"></div>
                  </div>
                )}
                
            <div className={`group ${message.type === "user" ? "max-w-sm lg:max-w-lg order-first" : "flex-1"}`}>
                  <div
                className={`px-5 py-4 rounded-2xl shadow-lg backdrop-blur-sm transition-all duration-300 hover:shadow-xl ${
                      message.type === "user"
                    ? "bg-gradient-to-br from-blue-600 to-indigo-700 text-white ml-auto" 
                    : "bg-white/80 text-gray-800 border border-blue-100/50"
                    }`}
                  >
                <div className="text-sm leading-relaxed font-medium">{formatChatMessage(message.content, message.contentType)}</div>
                  
                  
                {/* Timestamp */}
                <div className={`flex items-center gap-1 mt-3 pt-2 border-t ${
                  message.type === "user" 
                    ? "border-white/20" 
                    : "border-gray-200/50"
                }`}>
                  <Clock className={`w-3 h-3 ${
                    message.type === "user" ? "text-white/70" : "text-gray-500"
                  }`} />
                  <p className={`text-xs font-medium ${
                    message.type === "user" ? "text-white/70" : "text-gray-500"
                  }`}>
                    {formatTime(message.timestamp)}
                  </p>
                </div>
              </div>
            </div>
            
            {message.type === "user" && (
              <div className="flex-shrink-0">
                <div className="w-10 h-10 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center shadow-lg">
                  <User className="w-5 h-5 text-white" />
                </div>
              </div>
            )}
          </div>
        ))}
        
        {/* Enhanced Loading State */}
        {isLoading && (
          <div className="flex gap-3 justify-start animate-slide-in">
            <div className="relative flex-shrink-0">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl animate-pulse opacity-30"></div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm px-5 py-4 rounded-2xl shadow-lg border border-blue-100/50">
              <div className="flex items-center gap-3">
                <div className="flex space-x-1">
                  <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce"></div>
                  <div 
                    className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div 
                    className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
                <span className="text-sm text-gray-600 font-medium">AI is analyzing...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Enhanced Input Form */}
      <form onSubmit={handleSubmit} className="p-6 border-t border-blue-100/50 bg-gradient-to-r from-blue-50/30 to-indigo-50/30">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
              placeholder={selectedDrug ? `Ask about ${selectedDrug.drug_name}...` : "Ask about FDA documents..."}
            disabled={isLoading}
              className="w-full px-5 py-4 pr-12 bg-white/80 backdrop-blur-sm border border-blue-200/50 rounded-2xl 
                focus:outline-none focus:ring-3 focus:ring-blue-500/30 focus:border-blue-400
                disabled:opacity-50 disabled:cursor-not-allowed
                placeholder:text-gray-500 text-gray-800 font-medium
                shadow-lg transition-all duration-300
                hover:shadow-xl hover:bg-white/90"
            />
            <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
              {inputValue.trim() && !isLoading && (
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="px-6 py-4 bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-2xl 
              hover:from-blue-700 hover:to-indigo-800 
              disabled:opacity-50 disabled:cursor-not-allowed 
              transition-all duration-300 shadow-lg hover:shadow-xl
              group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            {isLoading ? (
              <Loader2 className="w-5 h-5 animate-spin relative z-10" />
            ) : (
              <Send className="w-5 h-5 relative z-10 transition-transform group-hover:scale-110" />
            )}
          </button>
        </div>
        
        {/* Input Helper */}
        <div className="flex items-center justify-between mt-3 px-1">
          <p className="text-xs text-gray-500 font-medium">
            Press Enter to send • Ask about indications, safety, or clinical data
          </p>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 bg-green-400 rounded-full"></div>
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div>
              <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full"></div>
            </div>
            <span className="font-medium">AI Powered</span>
          </div>
        </div>
      </form>
    </div>
  );
} 