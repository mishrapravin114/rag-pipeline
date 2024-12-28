import { format } from 'date-fns';

interface ExportMessage {
  role: string;
  content: string;
  timestamp: Date;
  source_documents?: any[];
}

export const generatePDFContent = (
  messages: ExportMessage[],
  collectionName?: string,
  drugNames?: string[]
): string => {
  // Generate HTML content for PDF
  const title = collectionName 
    ? `Chat about ${collectionName}` 
    : drugNames?.length 
      ? `FDA Drug Analysis: ${drugNames.join(', ')}`
      : 'FDA Drug Assistant Chat';
  
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    @page {
      size: A4;
      margin: 20mm;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.6;
      color: #333;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
    }
    
    .header {
      text-align: center;
      margin-bottom: 40px;
      padding-bottom: 20px;
      border-bottom: 2px solid #e5e7eb;
    }
    
    .header h1 {
      color: #1e40af;
      margin-bottom: 10px;
      font-size: 24px;
    }
    
    .header .metadata {
      color: #6b7280;
      font-size: 14px;
    }
    
    .message {
      margin-bottom: 25px;
      page-break-inside: avoid;
    }
    
    .message.user {
      text-align: right;
    }
    
    .message.assistant {
      text-align: left;
    }
    
    .message-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
      font-size: 14px;
      color: #6b7280;
    }
    
    .message.user .message-header {
      justify-content: flex-end;
    }
    
    .message-content {
      padding: 12px 16px;
      border-radius: 8px;
      display: inline-block;
      max-width: 80%;
    }
    
    .message.user .message-content {
      background-color: #3b82f6;
      color: white;
      text-align: left;
    }
    
    .message.assistant .message-content {
      background-color: #f3f4f6;
      color: #1f2937;
      border: 1px solid #e5e7eb;
    }
    
    .sources {
      margin-top: 10px;
      padding-top: 10px;
      border-top: 1px solid #e5e7eb;
      font-size: 12px;
      color: #6b7280;
    }
    
    .sources-title {
      font-weight: 600;
      margin-bottom: 5px;
    }
    
    .source-item {
      margin-left: 15px;
      margin-bottom: 3px;
    }
    
    .footer {
      margin-top: 40px;
      padding-top: 20px;
      border-top: 2px solid #e5e7eb;
      text-align: center;
      font-size: 12px;
      color: #9ca3af;
    }
    
    @media print {
      body {
        padding: 0;
      }
      
      .message {
        page-break-inside: avoid;
      }
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>${title}</h1>
    <div class="metadata">
      <div>Generated on ${format(new Date(), 'MMMM d, yyyy \'at\' h:mm a')}</div>
      <div>${messages.length} messages</div>
    </div>
  </div>
  
  <div class="messages">
    ${messages.map(msg => `
      <div class="message ${msg.role}">
        <div class="message-header">
          <span class="role">${msg.role === 'user' ? 'You' : 'Assistant'}</span>
          <span class="timestamp">${format(msg.timestamp, 'MMM d, h:mm a')}</span>
        </div>
        <div class="message-content">
          ${escapeHtml(msg.content)}
          ${msg.source_documents && msg.source_documents.length > 0 ? `
            <div class="sources">
              <div class="sources-title">Sources:</div>
              ${msg.source_documents.map(doc => `
                <div class="source-item">• ${doc.metadata?.source || 'Unknown source'}</div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      </div>
    `).join('')}
  </div>
  
  <div class="footer">
    <p>This conversation was exported from FDA Drug Assistant</p>
    <p>© ${new Date().getFullYear()} FDA RAG Pipeline. All rights reserved.</p>
  </div>
</body>
</html>
  `;
  
  return htmlContent;
};

export const downloadPDF = async (
  messages: ExportMessage[],
  collectionName?: string,
  drugNames?: string[]
) => {
  const htmlContent = generatePDFContent(messages, collectionName, drugNames);
  
  // Create a blob with the HTML content
  const blob = new Blob([htmlContent], { type: 'text/html' });
  
  // Create a temporary iframe to render and print
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.top = '-10000px';
  iframe.style.left = '-10000px';
  iframe.style.width = '210mm';
  iframe.style.height = '297mm';
  document.body.appendChild(iframe);
  
  // Load the HTML content
  const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document;
  if (iframeDoc) {
    iframeDoc.open();
    iframeDoc.write(htmlContent);
    iframeDoc.close();
    
    // Wait for content to load
    setTimeout(() => {
      // Trigger print dialog (user can save as PDF)
      iframe.contentWindow?.print();
      
      // Clean up after a delay
      setTimeout(() => {
        document.body.removeChild(iframe);
      }, 1000);
    }, 500);
  }
};

export const downloadHTML = (
  messages: ExportMessage[],
  collectionName?: string,
  drugNames?: string[]
) => {
  const htmlContent = generatePDFContent(messages, collectionName, drugNames);
  const blob = new Blob([htmlContent], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `chat-export-${format(new Date(), 'yyyy-MM-dd-HHmmss')}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// Helper function to escape HTML
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}