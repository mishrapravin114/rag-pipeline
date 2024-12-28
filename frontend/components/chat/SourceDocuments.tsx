"use client"

import React from 'react'
import { ChevronDown, FileText, Hash, Download } from 'lucide-react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import type { SourceDocument } from '@/services/api'

interface SourceDocumentsProps {
  documents: SourceDocument[]
  className?: string
}

export function SourceDocuments({ documents, className = "" }: SourceDocumentsProps) {
  if (!documents || documents.length === 0) {
    return null
  }

  // Group documents by source file
  const groupedDocs = documents.reduce((acc, doc) => {
    const fileName = doc.file_name || doc.source
    if (!acc[fileName]) {
      acc[fileName] = []
    }
    acc[fileName].push(doc)
    return acc
  }, {} as Record<string, SourceDocument[]>)

  return (
    <div className={`mt-4 ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        <FileText className="h-4 w-4 text-gray-500" />
        <h3 className="text-sm font-medium text-gray-700">Sources ({documents.length})</h3>
      </div>

      <Accordion type="single" collapsible className="w-full">
        <AccordionItem value="sources" className="border rounded-lg">
          <AccordionTrigger className="px-4 py-2 hover:no-underline">
            <div className="flex items-center justify-between w-full pr-2">
              <span className="text-sm font-medium">View source documents</span>
              <Badge variant="secondary" className="ml-2">
                {Object.keys(groupedDocs).length} files
              </Badge>
            </div>
          </AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <div className="space-y-3">
              {Object.entries(groupedDocs).map(([fileName, docs]) => (
                <Card key={fileName} className="p-3">
                  <div className="space-y-2">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-2">
                        <FileText className="h-4 w-4 text-blue-500 flex-shrink-0" />
                        {/* Make filename clickable if file_url is available */}
                        {docs[0]?.metadata?.file_url ? (
                          <a
                            href={docs[0].metadata.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                          >
                            {fileName}
                            <Download className="h-3 w-3" />
                          </a>
                        ) : (
                          <h4 className="text-sm font-medium text-gray-900">{fileName}</h4>
                        )}
                      </div>
                      <Badge variant="outline" className="text-xs">
                        {docs.length} chunk{docs.length > 1 ? 's' : ''}
                      </Badge>
                    </div>

                    {/* Show relevance score if available */}
                    {docs[0].relevance_score !== undefined && (
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-500">Relevance:</span>
                        <Progress 
                          value={docs[0].relevance_score * 100} 
                          className="h-1.5 w-20"
                        />
                        <span className="text-xs text-gray-600">
                          {(docs[0].relevance_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    )}

                    {/* Show document chunks */}
                    <div className="space-y-2">
                      {docs.map((doc, idx) => (
                        <div key={doc.id || idx} className="pl-6">
                          <div className="flex items-start gap-2">
                            <Hash className="h-3 w-3 text-gray-400 mt-0.5 flex-shrink-0" />
                            <div className="flex-1">
                              {doc.chunk_id && (
                                <span className="text-xs text-gray-500 font-mono">
                                  {doc.chunk_id}
                                </span>
                              )}
                              <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                                {doc.page_content_preview}
                              </p>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  )
}