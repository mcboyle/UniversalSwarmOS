import './globals.css';
import type { Metadata, Viewport } from 'next';
import React from 'react';
import { Toaster } from 'sonner';

export const metadata: Metadata = {
  title: 'Heterogeneous Swarm Architecture Dashboard',
  description:
    'Operations cockpit for autonomous multi-model fleet telemetry, CI/CD shard matrix, API rate limit headroom, and interactive swarm control.',
  icons: {
    icon: '/favicon.ico',
  },
};

export const viewport: Viewport = {
  themeColor: '#09090b',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" style={{ colorScheme: 'dark' }}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="bg-zinc-950 text-zinc-100 antialiased min-h-screen selection:bg-zinc-800 selection:text-zinc-200 flex flex-col">
        {children}
        <Toaster theme="dark" position="top-right" />
      </body>
    </html>
  );
}
