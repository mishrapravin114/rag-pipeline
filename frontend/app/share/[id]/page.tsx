"use client";

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import { apiService } from '@/services/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  Lock,
  Loader2,
  MessageCircle,
  Calendar,
  Eye,
  Share2,
  Copy,
  Bot,
  User,
  FileText,
  AlertCircle
} from 'lucide-react';
import { format } from 'date-fns';
import { getRelativeTime, getDateSeparatorText, shouldShowDateSeparator } from '@/utils/timeFormat';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';
import { EnhancedSourceDocuments } from '@/components/chat/EnhancedSourceDocuments';

export default function SharedChatPage() {
  const params = useParams();
  const shareId = params.id as string;
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [password, setPassword] = useState('');
  const [chatData, setChatData] = useState<any>(null);
  const [showPassword, setShowPassword] = useState(false);
  
  const loadSharedChat = async (pwd?: string) => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('Loading shared chat:', shareId, 'with password:', pwd ? 'provided' : 'not provided');
      const data = await apiService.getSharedChat(shareId, pwd);
      console.log('Shared chat data received:', data);
      console.log('First message:', data.messages?.[0]);
      setChatData(data);
      setPasswordRequired(false);
      
    } catch (error: any) {
      console.error('Error loading shared chat:', error);
      
      if (error.status === 401 || error.response?.status === 401 || error.message?.includes('password') || error.message?.includes('Password')) {
        console.log('Password required - showing password form');
        setPasswordRequired(true);
        if (pwd) {
          setError('Invalid password. Please try again.');
        } else {
          setError('This chat is password protected');
        }
      } else if (error.status === 404 || error.response?.status === 404) {
        setError('This shared chat link has expired or does not exist');
      } else {
        setError('Failed to load shared chat');
      }
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    loadSharedChat();
  }, [shareId]);
  
  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedPassword = password.trim();
    if (trimmedPassword) {
      console.log('Submitting password, length:', trimmedPassword.length);
      loadSharedChat(trimmedPassword);
    }
  };
  
  const copyLink = () => {
    navigator.clipboard.writeText(window.location.href);
    toast.success('Link copied to clipboard');
  };
  
  const startNewChat = () => {
    window.location.href = '/';
  };
  
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading shared conversation...</p>
        </div>
      </div>
    );
  }
  
  if (passwordRequired) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              Password Required
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handlePasswordSubmit} className="space-y-4">
              <p className="text-sm text-gray-600">
                This conversation is password protected. Please enter the password to view.
              </p>
              
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  className="pr-10"
                  autoFocus
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  <Eye className={cn("h-4 w-4", showPassword && "text-blue-600")} />
                </Button>
              </div>
              
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 px-3 py-2 rounded-md text-sm">
                  {error}
                </div>
              )}
              
              <Button type="submit" className="w-full" disabled={!password}>
                <Lock className="h-4 w-4 mr-2" />
                Unlock Conversation
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  if (error && !passwordRequired) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardContent className="text-center p-8">
            <AlertCircle className="h-12 w-12 text-red-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Unable to Load Chat</h3>
            <p className="text-gray-600 mb-6">{error}</p>
            <Button onClick={startNewChat} className="w-full">
              <MessageCircle className="h-4 w-4 mr-2" />
              Start a New Conversation
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }
  
  if (!chatData) return null;
  
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <Share2 className="h-5 w-5 text-blue-600" />
              </div>
              <div>
                <h1 className="text-lg font-semibold text-gray-900">
                  {chatData.title || 'Shared Conversation'}
                </h1>
                <div className="flex items-center gap-4 text-sm text-gray-600">
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" />
                    {format(new Date(chatData.created_at), 'MMM d, yyyy')}
                  </span>
                  <span className="flex items-center gap-1">
                    <Eye className="h-3 w-3" />
                    {chatData.view_count} views
                  </span>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={copyLink}>
                <Copy className="h-4 w-4 mr-2" />
                Copy Link
              </Button>
              <Button size="sm" onClick={startNewChat}>
                <MessageCircle className="h-4 w-4 mr-2" />
                Start Chat
              </Button>
            </div>
          </div>
        </div>
      </div>
      
      {/* Messages */}
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        <Card>
          <CardContent className="p-0">
            <ScrollArea className="h-[calc(100vh-250px)]">
              <div className="p-8 space-y-6">
                {chatData.messages.map((message: any, index: number) => {
                  const previousMessage = index > 0 ? chatData.messages[index - 1] : null;
                  const showDateSeparator = shouldShowDateSeparator(
                    new Date(message.timestamp),
                    previousMessage ? new Date(previousMessage.timestamp) : null
                  );
                  
                  return (
                    <div key={message.id || index}>
                      {showDateSeparator && (
                        <div className="flex items-center gap-3 my-4">
                          <div className="flex-1 h-px bg-gray-200" />
                          <span className="text-xs text-gray-500 font-medium px-2">
                            {getDateSeparatorText(new Date(message.timestamp))}
                          </span>
                          <div className="flex-1 h-px bg-gray-200" />
                        </div>
                      )}
                      
                      <div className={cn(
                        "flex gap-3",
                        message.role === 'user' ? 'justify-end' : 'justify-start'
                      )}>
                        {message.role === 'assistant' && (
                          <div className="flex-shrink-0">
                            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                              <Bot className="h-4 w-4 text-white" />
                            </div>
                          </div>
                        )}
                        
                        <div className={cn(
                          "max-w-[85%] rounded-lg p-4",
                          message.role === 'user'
                            ? 'bg-blue-600 text-white'
                            : 'bg-white border border-gray-200'
                        )}>
                          <div className={cn(
                            "text-sm",
                            message.role === 'user' ? 'text-white' : 'text-gray-800'
                          )}>
                            {message.role === 'assistant' && (message.contentType === 'html' || message.content?.includes('<div') || message.content?.includes('<p>')) ? (
                              <div 
                                className="prose prose-sm max-w-none [&_p]:text-gray-800 [&_div]:text-gray-800 [&_span]:text-gray-800 [&_li]:text-gray-800 [&_h1]:text-gray-900 [&_h2]:text-gray-900 [&_h3]:text-gray-900 [&_strong]:text-gray-900"
                                dangerouslySetInnerHTML={{ __html: message.content }}
                              />
                            ) : (
                              <div className="whitespace-pre-wrap">{message.content}</div>
                            )}
                          </div>
                          
                          {/* Source documents */}
                          {message.role === 'assistant' && message.source_documents && message.source_documents.length > 0 && (
                            <EnhancedSourceDocuments 
                              documents={message.source_documents} 
                              className="mt-3" 
                            />
                          )}
                          
                          <div className="mt-2 text-xs opacity-70">
                            {getRelativeTime(new Date(message.timestamp))}
                          </div>
                        </div>
                        
                        {message.role === 'user' && (
                          <div className="flex-shrink-0">
                            <div className="h-8 w-8 rounded-lg bg-gray-200 flex items-center justify-center">
                              <User className="h-4 w-4 text-gray-600" />
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
        
        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-sm text-gray-600 mb-4">
            This is a read-only view of a shared conversation
          </p>
          <Button onClick={startNewChat} size="lg">
            <MessageCircle className="h-5 w-5 mr-2" />
            Start Your Own Conversation
          </Button>
        </div>
      </div>
    </div>
  );
}