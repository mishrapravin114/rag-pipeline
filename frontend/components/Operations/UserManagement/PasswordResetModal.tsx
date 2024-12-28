import { X, Copy, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

interface PasswordResetModalProps {
  isOpen: boolean;
  onClose: () => void;
  username: string;
  temporaryPassword: string;
}

export function PasswordResetModal({ 
  isOpen, 
  onClose, 
  username, 
  temporaryPassword 
}: PasswordResetModalProps) {
  const [copied, setCopied] = useState(false);

  console.log('PasswordResetModal props:', { isOpen, username, temporaryPassword });

  if (!isOpen) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(temporaryPassword);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy password:', err);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <h2 className="text-xl font-semibold text-gray-900">Password Reset Successful</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-green-800 text-sm mb-3">
              Password has been reset successfully for user <strong>{username}</strong>.
            </p>
            <p className="text-green-700 text-sm">
              Please share the temporary password securely with the user.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700">Temporary Password</label>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-50 border border-gray-300 rounded-md px-4 py-2 font-mono text-sm">
                {temporaryPassword}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleCopy}
                className="flex items-center gap-2 border-blue-300 text-blue-600 hover:bg-blue-50 btn-professional-subtle"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-green-600" />
                    Copied
                  </>
                ) : (
                  <>
                    <Copy className="h-4 w-4" />
                    Copy
                  </>
                )}
              </Button>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
            <p className="text-amber-800 text-xs">
              <strong>Security Note:</strong> The user will be required to change this password on their next login.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="p-6 border-t bg-gray-50">
          <Button 
            onClick={onClose} 
            className="w-full bg-blue-600 hover:bg-blue-700 text-white btn-professional"
          >
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}