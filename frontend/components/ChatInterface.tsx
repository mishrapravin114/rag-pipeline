"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { Send, Bot, User, Sparkles, Clock, Loader2, Type, FileText, Bold, Italic, List } from "lucide-react"
import type { ChatMessage } from "../services/api"
import { apiService } from '../services/api'
import ReactMarkdown from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize from 'rehype-sanitize'
import { defaultSchema } from 'rehype-sanitize'
import { SourceDocuments } from '@/components/chat/SourceDocuments'
import { EnhancedSourceDocuments } from '@/components/chat/EnhancedSourceDocuments'

interface ChatInterfaceProps {
  messages: ChatMessage[]
  onSendMessage: (message: string) => void
  loading?: boolean
  placeholder?: string
  title?: string
  selectedEntity?: {
    id: string
    entity_name: string
    indication: string
    manufacturer: string
  } | null
}

// Custom sanitize schema that allows inline styles
const customSanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    '*': [...(defaultSchema.attributes?.['*'] || []), 'style', 'className'],
    div: [...(defaultSchema.attributes?.div || []), 'style'],
    h1: [...(defaultSchema.attributes?.h1 || []), 'style'],
    h2: [...(defaultSchema.attributes?.h2 || []), 'style'],
    h3: [...(defaultSchema.attributes?.h3 || []), 'style'],
    p: [...(defaultSchema.attributes?.p || []), 'style'],
    strong: [...(defaultSchema.attributes?.strong || []), 'style'],
    table: [...(defaultSchema.attributes?.table || []), 'style'],
    th: [...(defaultSchema.attributes?.th || []), 'style'],
    td: [...(defaultSchema.attributes?.td || []), 'style'],
    ul: [...(defaultSchema.attributes?.ul || []), 'style'],
    li: [...(defaultSchema.attributes?.li || []), 'style'],
    span: [...(defaultSchema.attributes?.span || []), 'style']
  }
}

// Simple function to format user messages (keep basic formatting for user messages)
const formatUserMessage = (content: string) => {
  return content
    .split('\n')
    .map((line, index) => (
      <span key={index} style={{ display: 'block', marginBottom: '0.25rem' }}>
        {line}
      </span>
    ));
};

// Enhanced function to preprocess assistant messages for better markdown rendering
const preprocessMarkdown = (content: string) => {
  if (!content) return content;
  
  // Fix common markdown issues that might slip through backend processing
  let processed = content;
  
  // Ensure proper spacing in headers
  processed = processed.replace(/^(#{1,6})([^#\s])/gm, '$1 $2');
  
  // More comprehensive approach: find headers followed by asterisk-separated items
  // and convert them to proper bullet lists
  const processHeaderWithBullets = (match: string, header: string, content: string) => {
    const items = content
      .split('*')
      .map(item => item.trim())
      .filter(item => item.length > 0);
    
    if (items.length === 0) return header;
    
    return header.trim() + '\n' + items.map(item => `- ${item}`).join('\n');
  };
  
  // Pattern to match header followed by asterisk-separated content
  // This handles both newline-separated and inline content
  processed = processed.replace(
    /(#{1,6}\s+[^*#]+?)\s*\*\s*([^#]+?)(?=\s#{1,6}|\n\s*#{1,6}|\n\s*\n|\n\s*$|$)/gm,
    processHeaderWithBullets
  );
  
  // Fix bullet points with various symbols
  processed = processed.replace(/^•\s*/gm, '- ');
  processed = processed.replace(/^\*\s+/gm, '- ');
  
  // Fix malformed bold text (** text** → **text**)
  processed = processed.replace(/\*\* ([^*]+?)\*\*/g, '**$1**');
  
  // Fix broken list items that are on separate lines
  processed = processed.replace(/(\w)\n•\n(\w)/g, '$1\n- $2');
  
  // Clean up multiple consecutive line breaks
  processed = processed.replace(/\n{3,}/g, '\n\n');
  
  return processed;
};

// Fallback component for when markdown fails to render properly
const MarkdownFallback = ({ content }: { content: string }) => {
  const lines = content.split('\n');
  
  return (
    <div className="markdown-fallback">
      {lines.map((line, index) => {
        // Basic header detection
        if (line.startsWith('## ')) {
          return <h2 key={index} className="text-lg font-bold mt-3 mb-2 text-gray-800">{line.replace('## ', '')}</h2>;
        }
        if (line.startsWith('# ')) {
          return <h1 key={index} className="text-xl font-bold mt-4 mb-2 text-gray-800">{line.replace('# ', '')}</h1>;
        }
        
        // Basic list detection
        if (line.startsWith('- ') || line.startsWith('* ')) {
          return <li key={index} className="mb-1 ml-6">{line.replace(/^[*-] /, '')}</li>;
        }
        
        // Basic bold text
        const boldText = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        return (
          <p key={index} className="mb-2 leading-relaxed" dangerouslySetInnerHTML={{ __html: boldText }} />
        );
      })}
    </div>
  );
};

// Enhanced content rendering component with HTML and markdown support
const RobustMarkdown = ({ content, contentType }: { content: string; contentType?: string }) => {
  const [renderError, setRenderError] = useState(false);
  
  // Reset error state when content changes
  useEffect(() => {
    setRenderError(false);
  }, [content]);
  
  if (renderError) {
    return <MarkdownFallback content={content} />;
  }
  
  // If content is HTML (from LLM conversion), render it directly
  if (contentType === 'html') {
    try {
      return (
        <div 
          className="html-content"
          dangerouslySetInnerHTML={{ __html: content }}
        />
      );
    } catch (error) {
      console.warn('HTML rendering failed, falling back to markdown:', error);
      // Fall through to markdown rendering
    }
  }
  
  // Default to markdown rendering
  try {
    return (
      <ReactMarkdown
        rehypePlugins={[rehypeRaw, [rehypeSanitize, customSanitizeSchema]]}
        skipHtml={false}
        onError={() => setRenderError(true)}
        components={{
          table: ({node, ...props}) => (
            <table className="table-auto border-collapse border-2 border-blue-200 rounded-lg my-4 w-full shadow-lg overflow-hidden" {...props} />
          ),
          th: ({node, ...props}) => (
            <th className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-4 py-3 border border-blue-500 text-left font-semibold text-sm uppercase tracking-wide" {...props} />
          ),
          td: ({node, ...props}) => (
            <td className="px-4 py-3 border border-blue-200 bg-white hover:bg-blue-50 transition-colors duration-200" {...props} />
          ),
          code: ({node, ...props}) => (
            <code className="bg-gray-100 px-1 rounded text-sm" {...props} />
          ),
          pre: ({node, ...props}) => (
            <pre className="bg-gray-100 p-3 rounded-md overflow-x-auto my-2 text-sm" {...props} />
          ),
          img: ({node, ...props}) => (
            <img className="rounded-md my-2 max-w-full h-auto shadow-sm" {...props} />
          ),
          ul: ({node, ...props}) => (
            <ul className="list-disc ml-6 my-3 space-y-2 text-gray-700" {...props} />
          ),
          ol: ({node, ...props}) => (
            <ol className="list-decimal ml-6 my-3 space-y-2 text-gray-700" {...props} />
          ),
          li: ({node, ...props}) => (
            <li className="mb-2 leading-relaxed hover:text-blue-700 transition-colors duration-200" {...props} />
          ),
          h1: ({node, ...props}) => <h1 className="text-2xl font-bold mt-6 mb-3 text-blue-800 border-b-2 border-blue-200 pb-2" {...props} />,
          h2: ({node, ...props}) => <h2 className="text-xl font-bold mt-5 mb-3 text-blue-700 border-l-4 border-blue-500 pl-3" {...props} />,
          h3: ({node, ...props}) => <h3 className="text-lg font-semibold mt-4 mb-2 text-blue-600" {...props} />,
          p: ({node, ...props}) => <p className="mb-3 leading-relaxed text-gray-700" {...props} />,
          strong: ({node, ...props}) => <strong className="font-semibold text-blue-900 bg-blue-50 px-1 rounded" {...props} />,
          em: ({node, ...props}) => <em className="italic text-gray-700" {...props} />,
        }}
      >
        {preprocessMarkdown(content)}
      </ReactMarkdown>
    );
  } catch (error) {
    console.warn('Markdown rendering failed, falling back to basic rendering:', error);
    return <MarkdownFallback content={content} />;
  }
};

export function ChatInterface({
  messages,
  onSendMessage,
  loading = false,
  placeholder = "Ask about this entity...",
  title = "AI Assistant",
  selectedEntity,
}: ChatInterfaceProps) {
  const [input, setInput] = useState("")
  const [isRichTextMode, setIsRichTextMode] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userInput = input
    setInput("")

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      content: userInput,
      role: "user",
      timestamp: new Date(),
      contentType: "markdown"
    }
    
    onSendMessage(userInput)

    try {
      // Use unified chat endpoint for better fallback support
      const requestPayload = { 
        message: userInput,
        session_id: localStorage.getItem('session_id') || undefined,
        user_id: undefined // Will be set by backend from auth
      };
      
      const response = await apiService.sendUnifiedChatMessage(requestPayload);

      // Transform unified response to ChatMessage format
      const assistantMessage: ChatMessage = {
        id: response.id,
        content: response.content,
        role: "assistant",
        timestamp: new Date(response.timestamp),
        contentType: "html", // Unified endpoint returns HTML
        sourceInfo: response.source_info,
        searchResults: response.search_results,
        usedDocuments: response.used_documents
      }

      // Pass the assistant message to parent component
      onSendMessage(assistantMessage.content)
      
    } catch (error) {
      console.error("Error sending chat message:", error)
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        content: "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
        role: "assistant", 
        timestamp: new Date(),
        contentType: "markdown",
        sourceInfo: {
          type: "error",
          source: "System"
        }
      }
      
      onSendMessage(errorMessage.content)
    }
  }

  return (
    <div className="flex flex-col h-full bg-gradient-to-br from-white via-blue-50/30 to-indigo-50/50 rounded-2xl shadow-xl border border-blue-100/50 backdrop-blur-xl">
      <div className="flex items-center gap-3 p-6 border-b border-blue-100/50 bg-gradient-to-r from-blue-600/5 to-indigo-600/5">
        <div className="relative">
          <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
            <Bot className="w-6 h-6 text-white" />
          </div>
          <div className="absolute -top-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white animate-pulse"></div>
        </div>
        <div className="flex-1">
          <h3 className="font-bold text-xl bg-gradient-to-r from-blue-800 to-indigo-700 bg-clip-text text-transparent">
            {title}
          </h3>
          <p className="text-sm text-blue-600/70 font-medium">Powered by AI • Ready to help</p>
        </div>
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-blue-100/50 rounded-full">
          <Sparkles className="w-4 h-4 text-blue-600" />
          <span className="text-xs font-semibold text-blue-700">Smart Assistant</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6 space-y-6 scrollbar-thin scrollbar-thumb-blue-200 scrollbar-track-transparent">
        {messages.length === 0 ? (
          <div className="text-center py-12 animate-fade-in">
            <div className="relative mb-6">
              <div className="w-20 h-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl mx-auto flex items-center justify-center shadow-xl">
                <Bot className="w-10 h-10 text-white" />
              </div>
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-3xl mx-auto w-20 h-20 animate-ping opacity-20"></div>
            </div>
            <h4 className="text-xl font-bold text-gray-800 mb-2">Start a Conversation</h4>
            <p className="text-gray-600 mb-6 max-w-sm mx-auto leading-relaxed">
              I'm here to help you with entity information, safety profiles, dosing, and more.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-md mx-auto">
              <div className="p-3 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border border-blue-100">
                <p className="text-sm font-medium text-blue-800">Entity Information</p>
                <p className="text-xs text-blue-600">Indications & usage</p>
              </div>
              <div className="p-3 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border border-indigo-100">
                <p className="text-sm font-medium text-indigo-800">Safety Profiles</p>
                <p className="text-xs text-indigo-600">Side effects & warnings</p>
              </div>
            </div>
          </div>
        ) : (
          messages.map((message, index) => (
            <div 
              key={message.id} 
              className={`flex gap-3 animate-slide-in ${message.role === "user" ? "justify-end" : "justify-start"}`}
              style={{ animationDelay: `${index * 0.1}s` }}
            >
              {message.role === "assistant" && (
                <div className="relative flex-shrink-0">
                  <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                    <Bot className="w-5 h-5 text-white" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-green-400 rounded-full border-2 border-white"></div>
                </div>
              )}
              
              <div className={`group max-w-xs lg:max-w-md ${message.role === "user" ? "order-first" : ""}`}>
                <div
                  className={`px-5 py-3 rounded-2xl shadow-lg backdrop-blur-sm transition-all duration-300 hover:shadow-xl ${
                    message.role === "user" 
                      ? "bg-gradient-to-br from-blue-600 to-indigo-700 text-white ml-auto" 
                      : "bg-white/80 text-gray-800 border border-blue-100/50"
                }`}
                >
                  {message.role === "assistant" ? (
                    <div className="text-sm leading-relaxed font-medium message-content">
                      {/* Use cited_content if available, fallback to regular content */}
                      <RobustMarkdown 
                        content={message.cited_content || message.content} 
                        contentType={message.contentType} 
                      />
                      
                      
                      {/* Source Information - Show for assistant messages unless no relevant info */}
                      {message.role === "assistant" && 
                       !message.content.toLowerCase().includes("no relevant information found") &&
                       !message.content.toLowerCase().includes("couldn't find any relevant information") && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <div className="flex items-center gap-2 text-xs text-gray-600">
                            <div className={`w-2 h-2 rounded-full ${
                              message.sourceInfo?.type === 'document_based' && message.usedDocuments 
                                ? 'bg-green-500' 
                                : message.sourceInfo?.type === 'llm_based' 
                                  ? 'bg-blue-500' 
                                  : 'bg-yellow-500'
                            }`}></div>
                            <span className="font-medium">
                              Source: {message.sourceInfo?.source || 'Knowledge Base'}
                            </span>
                            {message.sourceInfo?.model && (
                              <span className="text-gray-500">
                                • Model: {message.sourceInfo.model}
                              </span>
                            )}
                            {message.sourceInfo?.documents_used && (
                              <span className="text-gray-500">
                                • {message.sourceInfo.documents_used} docs
                              </span>
                            )}
                          </div>
                          {message.sourceInfo?.description && (
                            <div className="text-xs text-gray-500 mt-1">
                              {message.sourceInfo.description}
                            </div>
                          )}
                        </div>
                      )}
                      
                      {/* Search Results */}
                      {message.searchResults && message.searchResults.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-gray-100">
                          <details className="text-xs">
                            <summary className="cursor-pointer text-gray-600 hover:text-gray-800 font-medium">
                              View Sources ({message.searchResults.length})
                            </summary>
                            <div className="mt-2 space-y-2">
                              {message.searchResults.map((result, idx) => (
                                <div key={idx} className="bg-gray-50 p-2 rounded text-xs">
                                  <div className="font-medium text-gray-800">{result.entity_name}</div>
                                  <div className="text-gray-600">{result.file_name}</div>
                                  <div className="text-gray-500">Relevance: {result.relevance_score}%</div>
                                </div>
                              ))}
                            </div>
                          </details>
                        </div>
                      )}
                      
                      {/* Source Documents from SOTA RAG */}
                      {message.source_documents && message.source_documents.length > 0 && (
                        <EnhancedSourceDocuments documents={message.source_documents} className="mt-3" />
                      )}
                    </div>
                  ) : (
                    <div className="text-sm leading-relaxed font-medium">
                      {formatUserMessage(message.content)}
                    </div>
                  )}
                  <style jsx global>{`
                    .message-content table {
                      width: 100%;
                      border-collapse: collapse;
                      margin: 1rem 0;
                      border-radius: 0.5rem;
                      overflow: hidden;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                      font-size: 0.9em;
                    }
                    .message-content th {
                      background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                      color: white;
                      text-align: left;
                      padding: 0.875rem 1rem;
                      font-weight: 600;
                      font-size: 0.875rem;
                      text-transform: uppercase;
                      letter-spacing: 0.025em;
                      border: none;
                    }
                    .message-content td {
                      padding: 0.875rem 1rem;
                      border-bottom: 1px solid #e5e7eb;
                      vertical-align: top;
                      line-height: 1.5;
                    }
                    .message-content tr:nth-child(even) {
                      background-color: #f8fafc;
                    }
                    .message-content tr:hover {
                      background-color: #f1f5f9;
                      transition: background-color 0.2s ease;
                    }
                    .message-content tbody tr:last-child td {
                      border-bottom: none;
                    }
                    .message-content pre {
                      background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
                      padding: 1.25rem;
                      border-radius: 0.75rem;
                      overflow-x: auto;
                      margin: 1rem 0;
                      font-size: 0.875em;
                      line-height: 1.6;
                      border: 1px solid #e2e8f0;
                      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    }
                    .message-content code {
                      font-family: 'SF Mono', 'Monaco', 'Cascadia Code', 'Roboto Mono', monospace;
                      font-size: 0.875em;
                      background-color: #e2e8f0;
                      padding: 0.125rem 0.375rem;
                      border-radius: 0.25rem;
                      color: #374151;
                      font-weight: 500;
                    }
                    .message-content pre code {
                      background-color: transparent;
                      padding: 0;
                      border-radius: 0;
                      color: inherit;
                    }
                    .message-content img {
                      max-width: 100%;
                      height: auto;
                      border-radius: 0.75rem;
                      margin: 1rem 0;
                      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                      border: 1px solid #e2e8f0;
                    }
                    .message-content ul, .message-content ol {
                      margin: 0.75rem 0;
                      padding-left: 1.5rem;
                      line-height: 1.6;
                    }
                    .message-content li {
                      margin-bottom: 0.5rem;
                      position: relative;
                    }
                    .message-content ul li::marker {
                      color: #3b82f6;
                      font-weight: 600;
                    }
                    .message-content ol li::marker {
                      color: #3b82f6;
                      font-weight: 600;
                    }
                    .message-content li > p {
                      margin: 0;
                    }
                    .message-content ul ul, .message-content ol ol, .message-content ul ol, .message-content ol ul {
                      margin: 0.25rem 0;
                      padding-left: 1.25rem;
                    }
                    .message-content blockquote {
                      border-left: 4px solid #3b82f6;
                      padding-left: 1rem;
                      margin: 1rem 0;
                      color: #6b7280;
                      font-style: italic;
                      background-color: #f8fafc;
                      padding: 0.75rem 1rem;
                      border-radius: 0 0.5rem 0.5rem 0;
                    }
                    .message-content hr {
                      border: none;
                      height: 2px;
                      background: linear-gradient(90deg, transparent, #3b82f6, transparent);
                      margin: 1.5rem 0;
                    }
                    .html-content h1, .html-content h2, .html-content h3, .html-content h4, .html-content h5, .html-content h6 {
                      font-weight: 600;
                      margin: 1rem 0 0.5rem 0;
                      color: #374151;
                    }
                    .html-content h1 { font-size: 1.25rem; }
                    .html-content h2 { font-size: 1.125rem; }
                    .html-content h3 { font-size: 1rem; }
                    .html-content h4, .html-content h5, .html-content h6 { font-size: 0.875rem; }
                    .html-content ul, .html-content ol {
                      margin: 0.75rem 0;
                      padding-left: 1.5rem;
                      line-height: 1.6;
                    }
                    .html-content li {
                      margin-bottom: 0.5rem;
                    }
                    .html-content ul li {
                      list-style-type: disc;
                    }
                    .html-content ol li {
                      list-style-type: decimal;
                    }
                    .html-content p {
                      margin-bottom: 0.5rem;
                      line-height: 1.6;
                    }
                    .html-content strong {
                      font-weight: 600;
                      color: #374151;
                    }
                    .html-content em {
                      font-style: italic;
                      color: #6b7280;
                    }
                    .html-content table {
                      width: 100%;
                      border-collapse: collapse;
                      margin: 1rem 0;
                      border-radius: 0.5rem;
                      overflow: hidden;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }
                    .html-content th {
                      background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
                      color: white;
                      text-align: left;
                      padding: 0.875rem 1rem;
                      font-weight: 600;
                      font-size: 0.875rem;
                      text-transform: uppercase;
                      letter-spacing: 0.025em;
                    }
                    .html-content td {
                      padding: 0.875rem 1rem;
                      border-bottom: 1px solid #e5e7eb;
                      vertical-align: top;
                      line-height: 1.5;
                    }
                    .html-content tr:nth-child(even) {
                      background-color: #f8fafc;
                    }
                    .html-content tr:hover {
                      background-color: #f1f5f9;
                      transition: background-color 0.2s ease;
                    }
                  `}</style>
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
                      {new Date(message.timestamp).toLocaleTimeString([], { 
                        hour: '2-digit', 
                        minute: '2-digit' 
                      })}
                    </p>
                  </div>
                </div>
              </div>
              
              {message.role === "user" && (
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center shadow-lg">
                    <User className="w-5 h-5 text-white" />
                  </div>
                </div>
              )}
            </div>
          ))
        )}
        
        {loading && (
          <div className="flex gap-3 justify-start animate-slide-in">
            <div className="relative flex-shrink-0">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl animate-pulse opacity-30"></div>
            </div>
            <div className="bg-white/80 backdrop-blur-sm px-5 py-3 rounded-2xl shadow-lg border border-blue-100/50">
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
                <span className="text-sm text-gray-600 font-medium ml-2">AI is thinking...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="p-6 border-t border-blue-100/50 bg-gradient-to-r from-blue-50/30 to-indigo-50/30">
        {/* Rich Text Toolbar */}
        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-blue-100/30">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setIsRichTextMode(!isRichTextMode)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                isRichTextMode 
                  ? 'bg-blue-100 text-blue-700 border border-blue-200' 
                  : 'bg-gray-100 text-gray-600 hover:text-gray-800'
              }`}
            >
              {isRichTextMode ? <FileText className="w-3 h-3" /> : <Type className="w-3 h-3" />}
              {isRichTextMode ? 'Rich Text' : 'Plain Text'}
            </button>
          </div>
          
          {isRichTextMode && (
            <div className="flex items-center gap-1 ml-2 pl-2 border-l border-blue-200/50">
              <button
                type="button"
                onClick={() => {
                  const textarea = document.querySelector('textarea') as HTMLTextAreaElement;
                  if (textarea) {
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    const selectedText = input.substring(start, end);
                    const newText = input.substring(0, start) + `**${selectedText}**` + input.substring(end);
                    setInput(newText);
                  }
                }}
                className="p-1.5 rounded hover:bg-blue-100 text-gray-600 hover:text-blue-700 transition-colors"
                title="Bold"
              >
                <Bold className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={() => {
                  const textarea = document.querySelector('textarea') as HTMLTextAreaElement;
                  if (textarea) {
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    const selectedText = input.substring(start, end);
                    const newText = input.substring(0, start) + `*${selectedText}*` + input.substring(end);
                    setInput(newText);
                  }
                }}
                className="p-1.5 rounded hover:bg-blue-100 text-gray-600 hover:text-blue-700 transition-colors"
                title="Italic"
              >
                <Italic className="w-3 h-3" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setInput(input + '\n- ');
                }}
                className="p-1.5 rounded hover:bg-blue-100 text-gray-600 hover:text-blue-700 transition-colors"
                title="Bullet List"
              >
                <List className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>

        <div className="flex gap-3 items-end">
          <div className="flex-1 relative">
            {isRichTextMode ? (
              <div className="relative">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      handleSubmit(e as any);
                    }
                  }}
                  placeholder={`${placeholder} (Rich text mode - use **bold**, *italic*, and - for lists)`}
                  disabled={loading}
                  rows={input.split('\n').length < 4 ? Math.max(2, input.split('\n').length) : 4}
                  className="w-full px-5 py-4 pr-12 bg-white/80 backdrop-blur-sm border border-blue-200/50 rounded-2xl 
                    focus:outline-none focus:ring-3 focus:ring-blue-500/30 focus:border-blue-400
                    disabled:opacity-50 disabled:cursor-not-allowed
                    placeholder:text-gray-500 text-gray-800 font-medium
                    shadow-lg transition-all duration-300
                    hover:shadow-xl hover:bg-white/90 resize-none"
                />
                <div className="absolute right-4 bottom-4">
                  {input.trim() && !loading && (
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  )}
                </div>
                {input && (
                  <div className="mt-2 p-3 bg-blue-50/50 border border-blue-100 rounded-xl">
                    <div className="text-xs text-gray-600 mb-2 font-medium">Preview:</div>
                    <div className="text-sm">
                      <RobustMarkdown content={input} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="relative">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={placeholder}
                  disabled={loading}
                  className="w-full px-5 py-4 pr-12 bg-white/80 backdrop-blur-sm border border-blue-200/50 rounded-2xl 
                    focus:outline-none focus:ring-3 focus:ring-blue-500/30 focus:border-blue-400
                    disabled:opacity-50 disabled:cursor-not-allowed
                    placeholder:text-gray-500 text-gray-800 font-medium
                    shadow-lg transition-all duration-300
                    hover:shadow-xl hover:bg-white/90"
                />
                <div className="absolute right-4 top-1/2 transform -translate-y-1/2">
                  {input.trim() && !loading && (
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                  )}
                </div>
              </div>
            )}
          </div>
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-6 py-4 bg-gradient-to-r from-blue-600 to-indigo-700 text-white rounded-2xl 
              hover:from-blue-700 hover:to-indigo-800 
              disabled:opacity-50 disabled:cursor-not-allowed 
              transition-all duration-300 shadow-lg hover:shadow-xl
              group relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>
            <Send className="w-5 h-5 relative z-10 transition-transform group-hover:scale-110" />
          </button>
        </div>
        
        <div className="flex items-center justify-between mt-3 px-1">
          <p className="text-xs text-gray-500 font-medium">
            {isRichTextMode 
              ? "Rich text enabled • Use **bold**, *italic*, - lists • Press Ctrl+Enter to send" 
              : "Press Enter to send • Toggle rich text for formatting • Ask about entity indications, safety, or dosing"
            }
          </p>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 bg-green-400 rounded-full"></div>
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div>
              <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full"></div>
            </div>
            <span className="font-medium">Secure & Private</span>
          </div>
        </div>
      </form>
    </div>
  )
}
