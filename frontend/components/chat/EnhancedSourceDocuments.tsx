"use client"

import React from 'react'
import { ChevronDown, FileText, Hash, Download, Quote, BookOpen } from 'lucide-react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { SourceDocument, EnhancedSourceDocument } from '@/services/api'

interface EnhancedSourceDocumentsProps {
  documents: (SourceDocument | EnhancedSourceDocument)[]
  className?: string
}

// Type guard to check if document is enhanced
function isEnhancedDocument(doc: SourceDocument | EnhancedSourceDocument): doc is EnhancedSourceDocument {
  return 'citation_number' in doc && 'snippet' in doc
}

export function EnhancedSourceDocuments({ documents, className = "" }: EnhancedSourceDocumentsProps) {
  if (!documents || documents.length === 0) {
    return null
  }

  // Separate enhanced and regular documents, filtering out null/undefined
  const enhancedDocs = documents.filter(doc => doc && isEnhancedDocument(doc))
  const regularDocs = documents.filter(doc => doc && !isEnhancedDocument(doc))

  // Sort enhanced docs by citation number
  const sortedEnhancedDocs = [...enhancedDocs].sort((a, b) => a.citation_number - b.citation_number)

  return (
    <div className={`mt-4 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <FileText className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-700">
          Sources
        </h3>
      </div>

      <Accordion type="single" collapsible className="w-full">
        <AccordionItem value="sources" className="border rounded-lg">
          <AccordionTrigger className="px-4 py-2 hover:no-underline">
            <div className="flex items-center justify-between w-full pr-2">
              <span className="text-sm font-medium">View source documents</span>
              <div className="flex items-center gap-2">
                {enhancedDocs.length > 0 ? (
                  <Badge variant="default" className="bg-blue-600">
                    {enhancedDocs.length} citations
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    {documents.length} sources
                  </Badge>
                )}
              </div>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <div className="space-y-3">
              {/* Enhanced Documents with Citations */}
              {sortedEnhancedDocs.length > 0 && (
                <div className="mb-4">
                  <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <Quote className="h-4 w-4" />
                    Cited Sources
                  </h4>
                  <div className="space-y-2">
                    {sortedEnhancedDocs.filter(doc => doc && doc.id).map((doc) => (
                      <Card key={`enhanced-${doc.id}`} className="p-3 border-blue-200 bg-blue-50/30">
                        <div className="space-y-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-start gap-2 flex-1">
                              <div className="flex items-center justify-center w-6 h-6 bg-blue-600 text-white text-xs font-bold rounded-full flex-shrink-0">
                                {doc.citation_number}
                              </div>
                              <div className="flex-1">
                                <h5 className="text-sm font-medium text-gray-900">
                                  <a 
                                    href={doc?.metadata?.file_url || '#'}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="hover:text-blue-600 hover:underline cursor-pointer"
                                    onClick={(e) => {
                                      if (!doc?.metadata?.file_url) {
                                        e.preventDefault();
                                      }
                                    }}
                                  >
                                    {(doc?.filename || 'Unknown').replace('Unknown - ', '')}
                                  </a>
                                </h5>
                                {doc?.drug_name && !doc.drug_name.includes('Unknown') && (
                                  <p className="text-xs text-gray-600 mt-0.5">
                                    Drug: {doc.drug_name}
                                  </p>
                                )}
                              </div>
                            </div>
                            {doc.relevance_score !== undefined && doc.relevance_score > 0 && (
                              <div className="flex items-center gap-1">
                                <Progress 
                                  value={doc.relevance_score * 100} 
                                  className="h-1.5 w-16"
                                />
                                <span className="text-xs text-gray-600">
                                  {Math.round(doc.relevance_score * 100)}%
                                </span>
                              </div>
                            )}
                          </div>
                          
                          {/* Citation Snippet */}
                          <div className="bg-white/80 rounded p-2 border border-blue-100">
                            <p className="text-xs text-gray-700 italic">
                              "{doc?.metadata?.original_content || doc?.snippet || ''}"
                            </p>
                            {doc.page_number && (
                              <p className="text-xs text-gray-500 mt-1">
                                Page {doc.page_number}
                              </p>
                            )}
                          </div>
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* Regular Documents */}
              {regularDocs.length > 0 && (
                <div>
                  <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                    <BookOpen className="h-4 w-4" />
                    Additional Sources
                  </h4>
                  <div className="space-y-2">
                    {regularDocs.filter(doc => doc).map((doc, idx) => (
                      <Card key={`regular-${doc.id || idx}`} className="p-3">
                        <div className="space-y-2">
                          <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                              <FileText className="h-4 w-4 text-gray-500 flex-shrink-0" />
                              <h4 className="text-sm font-medium text-gray-900">
                                {doc.file_name || doc.source}
                              </h4>
                            </div>
                            {doc.relevance_score !== undefined && doc.relevance_score > 0 && (
                              <Badge variant="outline" className="text-xs">
                                {Math.round(doc.relevance_score * 100)}%
                              </Badge>
                            )}
                          </div>
                          
                          {doc.page_content_preview && (
                            <p className="text-xs text-gray-600 line-clamp-2">
                              {doc.page_content_preview}
                            </p>
                          )}
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              )}

              {/* No documents fallback */}
              {documents.length === 0 && (
                <div className="text-center py-4 text-sm text-gray-500">
                  No source documents available
                </div>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}