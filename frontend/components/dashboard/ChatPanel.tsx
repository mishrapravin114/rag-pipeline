"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, FileText, Loader2, MessageSquare, X, Maximize2, Minimize2, Sparkles, Clock } from "lucide-react";
import { apiService } from "../../services/api";
import { API_BASE_URL } from '@/config/api';

interface ChatMessage {
  id: string;
  content: string;
  role: "user" | "assistant";
  timestamp: Date;
  entityId?: string;
}

interface ChatPanelProps {
  isOpen: boolean;
  onClose: () => void;
  selectedEntity?: {
    id: string;
    source_file_id?: number;
    entity_name: string;
    indication: string;
    manufacturer: string;
  } | null;
  selectedEntitys?: {
    id: string;
    source_file_id?: number;
    entity_name: string;
    indication: string;
    manufacturer: string;
  }[] | null;
}

// Utility function to format chat messages - handles both HTML and markdown content
const formatChatMessage = (content: string) => {
  // Check if content is already HTML (contains HTML tags like <div>, <table>, <p>, etc.)
  const htmlTags = /<(div|table|p|h[1-6]|ul|ol|li|tr|td|th|thead|tbody)\b[^>]*>/i;
  
  if (htmlTags.test(content)) {
    // Content is already HTML, render it directly
    return <div dangerouslySetInnerHTML={{ __html: content }} />;
  }
  
  // Content is markdown/plain text, process it
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

export function ChatPanel({ isOpen, onClose, selectedEntity, selectedEntitys }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      
      // Add welcome message when chat opens
      let welcomeContent: string;
      
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name).join(", ");
        welcomeContent = `Hello! I'm here to help you compare and learn about multiple entities: ${entityNames}. You can ask me questions about their indications, compare their safety profiles, dosing differences, or any other aspects across these entities. What would you like to know?`;
      } else if (selectedEntity) {
        welcomeContent = `Hello! I'm here to help you learn about ${selectedEntity.entity_name}. You can ask me questions about its indication, dosage, efficacy, safety profile, or any other aspect of this entity. What would you like to know?`;
      } else {
        welcomeContent = "Hello! I'm your FDA document assistant. You can ask me questions about any of the entities in our database, their indications, safety profiles, dosing, or clinical trial data. How can I help you today?";
      }
      
      const welcomeMessage: ChatMessage = {
        id: Date.now().toString(),
        content: welcomeContent,
        role: "assistant",
        timestamp: new Date(),
      };
      setMessages([welcomeMessage]);
      
      // Focus input when chat opens
      setTimeout(() => {
        inputRef.current?.focus();
      }, 100);
    }
  }, [isOpen, selectedEntity, selectedEntitys]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // Generate context-aware suggestions based on conversation
  const generateSuggestions = async () => {
    const lastAssistantMessage = messages.filter(m => m.role === "assistant").pop();
    const lastUserMessage = messages.filter(m => m.role === "user").pop();
    
    
    // Try to get LLM-based suggestions from backend
    try {
      // Only call backend if we have more than the welcome message
      if (messages.length > 1) {
        // Prepare chat history for API
        const chatHistory = messages.map(msg => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp
        }));
        
        // Prepare selected entities data
        const entitiesData = selectedEntitys?.map(d => ({ entity_name: d.entity_name })) || 
                         (selectedEntity ? [{ entity_name: selectedEntity.entity_name }] : []);
        
        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = {
          'Content-Type': 'application/json'
        };
        
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        
        const response = await fetch(`${API_BASE_URL}/api/chat/suggestions`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            chat_history: chatHistory,
            selected_entities: entitiesData,
            last_response: lastAssistantMessage?.content || ''
          })
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.suggestions && data.suggestions.length > 0) {
            setSuggestions(data.suggestions);
            return;
          }
        }
      }
    } catch (error) {
      console.error('Error fetching suggestions from backend:', error);
    }
    
    // Fallback to client-side suggestions for initial state or if API fails
    if (messages.length === 1) {
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name);
        setSuggestions([
          `Compare the indications of ${entityNames.join(' and ')}`,
          `What are the safety differences between ${entityNames.join(' vs ')}?`,
          `How do dosing regimens differ for ${entityNames.join(', ')}?`,
          `Which is more effective: ${entityNames[0]} or ${entityNames.slice(1).join(' or ')}?`
        ]);
      } else if (selectedEntity) {
        setSuggestions([
          `What is the indication for ${selectedEntity.entity_name}?`,
          `What are the most common side effects of ${selectedEntity.entity_name}?`,
          `What is the recommended dosage for ${selectedEntity.entity_name}?`,
          `Are there any contraindications for ${selectedEntity.entity_name}?`
        ]);
      } else {
        setSuggestions([
          "Search for entities by indication",
          "Compare multiple entities",
          "Show recent FDA approvals",
          "Explain entity safety monitoring"
        ]);
      }
      return;
    }

    // Context-aware suggestions based on last response
    const newSuggestions: string[] = [];
    const lastContent = lastAssistantMessage?.content.toLowerCase() || "";

    // If discussing indications
    if (lastContent.includes("indication") || lastContent.includes("treat")) {
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name);
        newSuggestions.push(
          `What clinical trials support these indications for ${entityNames.join(' and ')}?`,
          `Are there off-label uses for ${entityNames.join(' or ')}?`,
          `How does ${entityNames[0]} efficacy compare to ${entityNames.slice(1).join(' and ')}?`
        );
      } else if (selectedEntity) {
        newSuggestions.push(
          `What clinical trials support ${selectedEntity.entity_name}'s indication?`,
          `Are there any off-label uses for ${selectedEntity.entity_name}?`,
          `How does ${selectedEntity.entity_name} compare to standard of care?`
        );
      } else {
        newSuggestions.push(
          "What clinical trials support this indication?",
          "Are there any off-label uses?",
          "How does efficacy compare to other treatments?"
        );
      }
    }

    // If discussing safety/side effects
    if (lastContent.includes("side effect") || lastContent.includes("adverse") || lastContent.includes("safety")) {
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name);
        newSuggestions.push(
          `What are the contraindications for ${entityNames.join(' vs ')}?`,
          `Compare entity interactions between ${entityNames.join(' and ')}`,
          `Which requires more monitoring: ${entityNames.join(' or ')}?`,
          `Compare serious adverse events for ${entityNames.join(' vs ')}?`
        );
      } else if (selectedEntity) {
        newSuggestions.push(
          `What are the contraindications for ${selectedEntity.entity_name}?`,
          `Does ${selectedEntity.entity_name} have any entity interactions?`,
          `What monitoring is required for ${selectedEntity.entity_name}?`,
          `How common are serious adverse events with ${selectedEntity.entity_name}?`
        );
      } else {
        newSuggestions.push(
          "What are the contraindications?",
          "Are there any entity interactions?",
          "What monitoring is required?",
          "How common are serious adverse events?"
        );
      }
    }

    // If discussing dosage
    if (lastContent.includes("dose") || lastContent.includes("dosing") || lastContent.includes("administration")) {
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name);
        newSuggestions.push(
          `Compare dose adjustments for ${entityNames.join(' vs ')}`,
          `Which is easier to administer: ${entityNames.join(' or ')}?`,
          `Compare dosing frequency for ${entityNames.join(' and ')}`,
          `Do ${entityNames.join(' or ')} require dose titration?`
        );
      } else if (selectedEntity) {
        newSuggestions.push(
          `Are there dose adjustments for ${selectedEntity.entity_name} in special populations?`,
          `What if a dose of ${selectedEntity.entity_name} is missed?`,
          `Can ${selectedEntity.entity_name} be taken with food?`,
          `How should ${selectedEntity.entity_name} be stored?`
        );
      } else {
        newSuggestions.push(
          "Are there dose adjustments for special populations?",
          "What happens if a dose is missed?",
          "Can it be taken with food?",
          "How should it be stored?"
        );
      }
    }

    // If discussing efficacy
    if (lastContent.includes("efficacy") || lastContent.includes("effective") || lastContent.includes("clinical trial")) {
      if (selectedEntitys && selectedEntitys.length > 1) {
        const entityNames = selectedEntitys.map(d => d.entity_name);
        newSuggestions.push(
          `Compare primary endpoints for ${entityNames.join(' vs ')}`,
          `Which had larger clinical trials: ${entityNames.join(' or ')}?`,
          `Compare response rates between ${entityNames.join(' and ')}`,
          `Which shows faster onset: ${entityNames.join(' or ')}?`
        );
      } else if (selectedEntity) {
        newSuggestions.push(
          `What were the primary endpoints for ${selectedEntity.entity_name}?`,
          `How many patients were studied for ${selectedEntity.entity_name}?`,
          `What was the response rate for ${selectedEntity.entity_name}?`,
          `How long does ${selectedEntity.entity_name} treatment typically last?`
        );
      } else {
        newSuggestions.push(
          "What were the primary endpoints?",
          "How many patients were studied?",
          "What was the response rate?",
          "How long does treatment last?"
        );
      }
    }

    // If comparing entities
    if (selectedEntitys && selectedEntitys.length > 1 && lastContent.includes("compar")) {
      const entityNames = selectedEntitys.map(d => d.entity_name);
      newSuggestions.push(
        `Which has fewer side effects: ${entityNames.join(' or ')}?`,
        `Compare the costs of ${entityNames.join(' vs ')}`,
        `Is ${entityNames[0]} easier to administer than ${entityNames.slice(1).join(' or ')}?`,
        `Which has better adherence: ${entityNames.join(' or ')}?`
      );
    }

    // Always add some general follow-ups
    if (newSuggestions.length < 3) {
      newSuggestions.push(
        "Tell me more about this",
        "What else should I know?",
        "Are there any warnings?"
      );
    }

    // Only use client-side suggestions if we didn't get LLM suggestions
    if (messages.length > 1) {
      setSuggestions(newSuggestions.slice(0, 4)); // Limit to 4 suggestions
    }
  };

  // Update suggestions when messages change
  useEffect(() => {
    generateSuggestions();
  }, [messages]);
  
  // Add a small delay after receiving a new message to ensure smooth UX
  useEffect(() => {
    if (messages.length > 1 && messages[messages.length - 1].role === 'assistant') {
      // Regenerate suggestions after AI responds
      const timer = setTimeout(() => {
        generateSuggestions();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [messages.length]);

  const sendMessage = async (inputValue: string) => {
    if (!inputValue.trim()) return;

    // Add user message to chat
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: inputValue,
      role: 'user',
      timestamp: new Date()
    };
    setMessages(prev => [...prev, userMessage]);

    try {
      // Use document-specific chat endpoint for DocuGenius
      const requestPayload: any = { 
        message: inputValue
      };

      // Add source file ID(s) based on selected entity(s)
      if (selectedEntitys && selectedEntitys.length > 1) {
        // Multiple entities - use source_file_ids
        requestPayload.source_file_ids = selectedEntitys.map(d => d.source_file_id).filter(id => id);
      } else if (selectedEntity && selectedEntity.source_file_id) {
        // Single entity - use source_file_id
        requestPayload.source_file_id = selectedEntity.source_file_id;
      } else if (selectedEntitys && selectedEntitys.length === 1 && selectedEntitys[0].source_file_id) {
        // Single entity in array - use source_file_id
        requestPayload.source_file_id = selectedEntitys[0].source_file_id;
      }

      const response = await apiService.sendChatMessage(requestPayload);
      
      // Add AI response to chat
      const aiMessage: ChatMessage = {
        id: response.id,
        content: response.content,
        role: 'assistant',
        timestamp: new Date(response.timestamp),
      };
      setMessages(prev => [...prev, aiMessage]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Add error message
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        content: 'Sorry, I encountered an error processing your message.',
        role: 'assistant',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    setIsLoading(true);
    await sendMessage(inputValue);
    setInputValue("");
    setIsLoading(false);
  };

  const handleQuickQuestion = (question: string) => {
    setInputValue(question);
    setTimeout(() => {
      const form = document.querySelector('form');
      if (form) {
        form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    }, 100);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (!isOpen) return null;

  return (
    <div className={`fixed ${isMaximized ? 'inset-4' : 'bottom-4 right-4 w-96 h-[600px]'} bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-2xl border border-blue-100/50 backdrop-blur-xl z-50 flex flex-col transition-all duration-300`}>
      {/* Enhanced Header */}
      <div className="flex items-center justify-between p-5 border-b border-blue-100/50 bg-gradient-to-r from-blue-600/5 to-indigo-600/5 rounded-t-2xl">
        <div className="flex items-center space-x-3">
          <div className="relative">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
              <MessageSquare className="w-5 h-5 text-white" />
            </div>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
          </div>
          <div className="flex-1">
            <h3 className="font-bold text-base bg-gradient-to-r from-blue-800 to-indigo-700 bg-clip-text text-transparent">
              {selectedEntitys && selectedEntitys.length > 1 
                ? `Compare: ${selectedEntitys.map(d => d.entity_name).join(' vs ')}` 
                : selectedEntity 
                  ? `Chat about ${selectedEntity.entity_name}` 
                  : "FDA Document Assistant"}
            </h3>
            <p className="text-xs text-blue-600/70 font-medium">
              {selectedEntitys && selectedEntitys.length > 1
                ? `Analyzing ${selectedEntitys.length} entities side-by-side`
                : selectedEntity 
                  ? "Ask questions about this entity" 
                  : "Ask questions about any FDA document"}
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <div className="hidden sm:flex items-center gap-2 px-2 py-1 bg-blue-100/50 rounded-lg">
            <Sparkles className="w-3 h-3 text-blue-600" />
            <span className="text-xs font-semibold text-blue-700">AI</span>
          </div>
          <button
            onClick={() => setIsMaximized(!isMaximized)}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-white/50 transition-all duration-200"
          >
            {isMaximized ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-white/50 transition-all duration-200"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Enhanced Messages */}
      <div className="flex-1 overflow-y-auto p-5 space-y-4 scrollbar-thin scrollbar-thumb-blue-200 scrollbar-track-transparent">
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`flex gap-3 animate-slide-in ${message.role === "user" ? "justify-end" : "justify-start"}`}
            style={{ animationDelay: `${messages.length > 5 ? 0 : index * 0.1}s` }}
          >
                {message.role === "assistant" && (
              <div className="relative flex-shrink-0">
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-green-400 rounded-full border-2 border-white"></div>
                  </div>
                )}
                
            <div className={`group max-w-[85%] ${message.role === "user" ? "order-first" : ""}`}>
                  <div
                className={`px-4 py-3 rounded-xl shadow-lg backdrop-blur-sm transition-all duration-300 hover:shadow-xl ${
                      message.role === "user"
                    ? "bg-gradient-to-br from-blue-600 to-indigo-700 text-white ml-auto" 
                    : "bg-white/80 text-gray-800 border border-blue-100/50"
                    }`}
                  >
                <p className="text-sm leading-relaxed font-medium">{formatChatMessage(message.content)}</p>
                  
                  
                {/* Timestamp */}
                <div className={`flex items-center gap-1 mt-2 pt-2 border-t ${
                  message.role === "user" 
                    ? "border-white/20" 
                    : "border-gray-200/50"
                }`}>
                  <Clock className={`w-3 h-3 ${
                    message.role === "user" ? "text-white/70" : "text-gray-500"
                  }`} />
                  <p className={`text-xs font-medium ${
                    message.role === "user" ? "text-white/70" : "text-gray-500"
                  }`}>
                    {formatTime(message.timestamp)}
                  </p>
                </div>
              </div>
            </div>

            {message.role === "user" && (
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center shadow-lg">
                  <User className="w-4 h-4 text-white" />
                </div>
              </div>
            )}
          </div>
        ))}
        
        {/* Enhanced Loading State */}
        {isLoading && (
          <div className="flex gap-3 justify-start animate-slide-in">
            <div className="relative flex-shrink-0">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <Bot className="w-4 h-4 text-white" />
              </div>
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl animate-pulse opacity-30"></div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm px-4 py-3 rounded-xl shadow-lg border border-blue-100/50">
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
                  <div 
                    className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.1s" }}
                  ></div>
                  <div 
                    className="w-2 h-2 bg-purple-500 rounded-full animate-bounce"
                    style={{ animationDelay: "0.2s" }}
                  ></div>
                </div>
                <span className="text-sm text-gray-600 font-medium">AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Dynamic Suggestions */}
      {suggestions.length > 0 && !isLoading && (
        <div className="px-5 py-3 border-t border-blue-100/50 bg-gradient-to-r from-blue-50/30 to-indigo-50/30">
          <p className="text-xs text-blue-700 font-semibold mb-3 flex items-center gap-2">
            <Sparkles className="w-3 h-3" />
            {messages.length === 1 ? 'Quick questions:' : 'Follow-up questions:'}
          </p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                onClick={() => handleQuickQuestion(suggestion)}
                className="px-3 py-1.5 text-xs bg-gradient-to-r from-blue-100 to-indigo-100 text-blue-800 rounded-lg hover:from-blue-200 hover:to-indigo-200 transition-all duration-200 font-medium shadow-sm"
                disabled={isLoading}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Enhanced Input */}
      <form onSubmit={handleSubmit} className="p-5 border-t border-blue-100/50 bg-gradient-to-r from-blue-50/30 to-indigo-50/30 rounded-b-2xl">
        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type your question..."
            disabled={isLoading}
              className="w-full px-4 py-3 pr-10 bg-white/80 backdrop-blur-sm border border-blue-200/50 rounded-xl 
                focus:outline-none focus:ring-2 focus:ring-blue-500/30 focus:border-blue-400
                disabled:opacity-50 disabled:cursor-not-allowed
                placeholder:text-gray-500 text-gray-800 font-medium
                shadow-lg transition-all duration-300
                hover:shadow-xl hover:bg-white/90 text-sm"
            />
            <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
              {inputValue.trim() && !isLoading && (
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
              )}
            </div>
          </div>
          <button
            type="submit"
            disabled={!inputValue.trim() || isLoading}
            className="px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-xl 
              hover:from-blue-700 hover:to-indigo-800 
              disabled:opacity-50 disabled:cursor-not-allowed 
              transition-all duration-300 shadow-lg hover:shadow-xl
              group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin relative z-10" />
            ) : (
              <Send className="w-4 h-4 relative z-10 transition-transform group-hover:scale-110" />
            )}
          </button>
        </div>
        </form>
    </div>
  );
} 