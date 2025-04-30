// Minor update
import { Loader2 } from 'lucide-react';

export default function ChatLoading() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
      <div className="text-center">
        <div className="bg-white rounded-full p-4 shadow-lg mb-4">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        </div>
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Loading Chat</h3>
        <p className="text-gray-600">Preparing your FDA entity information assistant...</p>
      </div>
    </div>
  );
}