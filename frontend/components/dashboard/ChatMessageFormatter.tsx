import React from 'react';
import { Check, AlertCircle, ChevronRight, Pill, FileText, BarChart, Beaker } from 'lucide-react';

interface ChatMessageFormatterProps {
  content: string;
}

export function ChatMessageFormatter({ content }: ChatMessageFormatterProps) {
  // Check if content mentions FDA documents
  const hasFDAReference = content.toLowerCase().includes('fda') || 
                         content.includes('according to') ||
                         content.includes('per the') ||
                         content.includes('official document');
  
  const formatContent = (text: string) => {
    // Split by paragraphs
    const paragraphs = text.split('\n\n');
    
    return paragraphs.map((paragraph, pIndex) => {
      // Check if it's a header (starts with # or bold text with **)
      if (paragraph.startsWith('**') && paragraph.endsWith('**')) {
        const headerText = paragraph.replace(/\*\*/g, '');
        return (
          <h3 key={pIndex} className="text-lg font-semibold text-gray-900 mt-4 mb-2 flex items-center gap-2">
            <div className="h-1 w-6 bg-blue-500 rounded-full" />
            {headerText}
          </h3>
        );
      }
      
      // Check if it's a list
      if (paragraph.includes('\n- ') || paragraph.includes('\n• ') || paragraph.includes('\n* ')) {
        const lines = paragraph.split('\n').filter(line => line.trim());
        return (
          <ul key={pIndex} className="space-y-2 my-3">
            {lines.map((line, lIndex) => {
              const bulletMatch = line.match(/^[-•*]\s+(.+)/);
              if (bulletMatch) {
                const listItem = bulletMatch[1];
                // Check for sub-bullets (indented items)
                const isSubBullet = line.startsWith('  ');
                
                return (
                  <li 
                    key={lIndex} 
                    className={`flex items-start gap-2 ${isSubBullet ? 'ml-6' : ''}`}
                  >
                    <ChevronRight className={`h-4 w-4 mt-0.5 flex-shrink-0 ${isSubBullet ? 'text-gray-400' : 'text-blue-500'}`} />
                    <span className="text-gray-700 leading-relaxed">
                      {formatInlineText(listItem)}
                    </span>
                  </li>
                );
              }
              return null;
            })}
          </ul>
        );
      }
      
      // Check if it's a numbered list
      if (paragraph.match(/^\d+\.\s/m)) {
        const lines = paragraph.split('\n').filter(line => line.trim());
        return (
          <ol key={pIndex} className="space-y-2 my-3">
            {lines.map((line, lIndex) => {
              const numberMatch = line.match(/^(\d+)\.\s+(.+)/);
              if (numberMatch) {
                const [_, number, text] = numberMatch;
                return (
                  <li key={lIndex} className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-medium">
                      {number}
                    </span>
                    <span className="text-gray-700 leading-relaxed">
                      {formatInlineText(text)}
                    </span>
                  </li>
                );
              }
              return null;
            })}
          </ol>
        );
      }
      
      // Regular paragraph
      return (
        <p key={pIndex} className="text-gray-700 leading-relaxed my-3">
          {formatInlineText(paragraph)}
        </p>
      );
    });
  };
  
  const formatInlineText = (text: string): React.ReactNode => {
    // Handle bold text
    const parts = text.split(/(\*\*[^*]+\*\*)/g);
    
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        const boldText = part.slice(2, -2);
        return <strong key={index} className="font-semibold text-gray-900">{boldText}</strong>;
      }
      
      // Handle inline code
      const codeParts = part.split(/(`[^`]+`)/g);
      return codeParts.map((codePart, codeIndex) => {
        if (codePart.startsWith('`') && codePart.endsWith('`')) {
          const code = codePart.slice(1, -1);
          return (
            <code key={`${index}-${codeIndex}`} className="px-1.5 py-0.5 bg-gray-100 text-gray-800 rounded text-sm font-mono">
              {code}
            </code>
          );
        }
        return codePart;
      });
    });
  };
  
  // Add special formatting for common medical/pharmaceutical terms
  const enhanceContent = (content: string): string => {
    // Add icons for certain keywords
    let enhanced = content;
    
    // Remove FDA Document citations
    enhanced = enhanced.replace(/\s*\(FDA Document\)/gi, '');
    enhanced = enhanced.replace(/\s*\[FDA Document\]/gi, '');
    enhanced = enhanced.replace(/\s*- FDA Document/gi, '');
    enhanced = enhanced.replace(/\s*–\s*FDA Document/gi, '');
    enhanced = enhanced.replace(/\s*\(Source: FDA Document\)/gi, '');
    enhanced = enhanced.replace(/\s*\[Source: FDA Document\]/gi, '');
    
    // Common section headers
    enhanced = enhanced.replace(/^(Indication[s]?|Usage[s]?):?$/gim, '**Indications and Usage**');
    enhanced = enhanced.replace(/^(Dosage|Dosing|Administration):?$/gim, '**Dosage and Administration**');
    enhanced = enhanced.replace(/^(Warning[s]?|Precaution[s]?):?$/gim, '**Warnings and Precautions**');
    enhanced = enhanced.replace(/^(Adverse|Side Effect[s]?):?$/gim, '**Adverse Reactions**');
    enhanced = enhanced.replace(/^(Interaction[s]?|Drug Interaction[s]?):?$/gim, '**Drug Interactions**');
    enhanced = enhanced.replace(/^(Contraindication[s]?):?$/gim, '**Contraindications**');
    enhanced = enhanced.replace(/^(Clinical|Study|Studies|Trial[s]?):?$/gim, '**Clinical Studies**');
    
    return enhanced;
  };
  
  const enhancedContent = enhanceContent(content);
  
  return (
    <div className="chat-message-content overflow-x-auto max-w-full">
      {formatContent(enhancedContent)}
      {hasFDAReference && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <div className="flex items-start gap-2">
            <FileText className="h-3 w-3 text-gray-400 mt-0.5" />
            <p className="text-xs text-gray-500 italic">
              This information is based on official FDA documentation. Always consult healthcare professionals for medical advice.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}