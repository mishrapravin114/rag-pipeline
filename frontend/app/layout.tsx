import type { Metadata } from 'next'
import './globals.css'
import { AppLayout } from '@/components/Navigation/AppLayout'
import { Toaster } from 'sonner'

export const metadata: Metadata = {
  title: 'FDA Entity Information System | RAG Dashboard',
  description: 'Advanced FDA entity information search and analysis platform with AI-powered insights',
  generator: 'FDA RAG System',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body suppressHydrationWarning>
        <AppLayout>{children}</AppLayout>
        <Toaster 
          position="top-right"
          toastOptions={{
            duration: 3000,
            style: {
              background: '#363636',
              color: '#fff',
            },
            success: {
              style: {
                background: '#10b981',
              },
            },
            error: {
              style: {
                background: '#ef4444',
              },
            },
          }}
        />
      </body>
    </html>
  )
}
