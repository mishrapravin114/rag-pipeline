"use client";

import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { toast } from 'sonner';
import { apiService } from '@/services/api';
import { copyToClipboard as copyText } from '@/utils/clipboard';
import {
  Copy,
  Link2,
  Lock,
  Clock,
  Loader2,
  Check,
  Share2,
  Eye,
  EyeOff
} from 'lucide-react';

interface ShareChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  messages: any[];
  sessionId: string;
  collectionName?: string;
}

export function ShareChatModal({
  isOpen,
  onClose,
  messages,
  sessionId,
  collectionName
}: ShareChatModalProps) {
  const [title, setTitle] = useState(collectionName ? `Chat about ${collectionName}` : 'Shared Chat');
  const [expirationHours, setExpirationHours] = useState('168'); // 7 days default
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [usePassword, setUsePassword] = useState(false);
  const [isSharing, setIsSharing] = useState(false);
  const [shareUrl, setShareUrl] = useState('');
  const [isShared, setIsShared] = useState(false);
  
  const handleShare = async () => {
    try {
      setIsSharing(true);
      
      // Prepare messages with all necessary fields
      const preparedMessages = messages.map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: msg.timestamp,
        contentType: msg.contentType || (msg.role === 'assistant' ? 'html' : 'text'),
        source_documents: msg.source_documents || [],
        cited_content: msg.cited_content,
        source_info: msg.source_info
      }));
      
      const response = await apiService.createShareLink({
        session_id: sessionId,
        messages: preparedMessages,
        title,
        expiration_hours: parseInt(expirationHours),
        password: usePassword ? password : undefined
      });
      
      setShareUrl(response.share_url);
      setIsShared(true);
      toast.success('Share link created successfully!');
    } catch (error) {
      console.error('Error creating share link:', error);
      toast.error('Failed to create share link');
    } finally {
      setIsSharing(false);
    }
  };
  
  const copyToClipboard = async () => {
    const success = await copyText(shareUrl);
    if (success) {
      toast.success('Link copied to clipboard');
    } else {
      toast.error('Failed to copy to clipboard');
    }
  };
  
  const resetModal = () => {
    setIsShared(false);
    setShareUrl('');
    setPassword('');
    setUsePassword(false);
  };
  
  const handleClose = () => {
    resetModal();
    onClose();
  };
  
  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Share2 className="h-5 w-5" />
            Share Conversation
          </DialogTitle>
          <DialogDescription>
            Create a shareable link for this conversation
          </DialogDescription>
        </DialogHeader>
        
        {!isShared ? (
          <div className="space-y-4">
            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter a title for the shared chat"
              />
            </div>
            
            {/* Expiration */}
            <div className="space-y-2">
              <Label htmlFor="expiration" className="flex items-center gap-2">
                <Clock className="h-4 w-4" />
                Link expires after
              </Label>
              <Select value={expirationHours} onValueChange={setExpirationHours}>
                <SelectTrigger id="expiration">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="24">1 day</SelectItem>
                  <SelectItem value="72">3 days</SelectItem>
                  <SelectItem value="168">7 days</SelectItem>
                  <SelectItem value="720">30 days</SelectItem>
                  <SelectItem value="8760">1 year</SelectItem>
                </SelectContent>
              </Select>
            </div>
            
            {/* Password Protection */}
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="password-protect"
                  checked={usePassword}
                  onCheckedChange={(checked) => setUsePassword(!!checked)}
                />
                <Label
                  htmlFor="password-protect"
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <Lock className="h-4 w-4" />
                  Password protect this link
                </Label>
              </div>
              
              {usePassword && (
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter password"
                    className="pr-10"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-0 top-0 h-full px-3 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              )}
            </div>
            
            {/* Info */}
            <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded-lg">
              <p className="font-medium mb-1">Share details:</p>
              <ul className="list-disc list-inside space-y-1 text-xs">
                <li>All {messages.length} messages in this conversation</li>
                <li>Read-only access (viewers cannot reply)</li>
                <li>Source documents and references included</li>
                <li>Link expires after {expirationHours === '24' ? '1 day' : expirationHours === '72' ? '3 days' : expirationHours === '168' ? '7 days' : expirationHours === '720' ? '30 days' : '1 year'}</li>
              </ul>
            </div>
            
            {/* Actions */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={handleClose}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                onClick={handleShare}
                disabled={isSharing || (usePassword && !password)}
                className="flex-1 bg-blue-600 hover:bg-blue-700"
              >
                {isSharing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Link2 className="h-4 w-4 mr-2" />
                    Create Link
                  </>
                )}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Success State */}
            <div className="flex items-center justify-center py-4">
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center">
                <Check className="h-8 w-8 text-green-600" />
              </div>
            </div>
            
            <div className="text-center">
              <h3 className="text-lg font-medium mb-2">Link Created!</h3>
              <p className="text-sm text-gray-600">
                Your conversation has been shared successfully
              </p>
            </div>
            
            {/* Share URL */}
            <div className="space-y-2">
              <Label>Share link</Label>
              <div className="flex gap-2">
                <Input
                  value={shareUrl}
                  readOnly
                  className="font-mono text-sm"
                />
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyToClipboard}
                  className="px-3"
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
            </div>
            
            {usePassword && (
              <div className="text-sm text-amber-600 bg-amber-50 p-3 rounded-lg flex items-start gap-2">
                <Lock className="h-4 w-4 mt-0.5 flex-shrink-0" />
                <p>
                  This link is password protected. Share the password separately with intended viewers.
                </p>
              </div>
            )}
            
            {/* Actions */}
            <div className="flex gap-3">
              <Button
                variant="outline"
                onClick={resetModal}
                className="flex-1"
              >
                Create Another
              </Button>
              <Button
                onClick={handleClose}
                className="flex-1"
              >
                Done
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}