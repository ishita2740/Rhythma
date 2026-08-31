import { Analytics } from '@vercel/analytics/next'
import type { Metadata } from 'next'
import { Geist, Geist_Mono } from 'next/font/google'
import './globals.css'

const geistSans = Geist({ variable: '--font-geist-sans', subsets: ['latin'] })
const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  metadataBase: new URL('https://rhythma-navy.vercel.app'),
  title: 'Rhythma — AI for Every Phase of Her Health',
  description:
    'Rhythma is a multilingual, offline-first, AI-powered menstrual and women’s health companion built for India. Track your cycle, understand your patterns, and get health guidance in your language — privacy-first.',
  keywords: [
    'Rhythma',
    'menstrual health',
    'period tracker',
    'women’s health',
    'cycle tracking',
    'PCOS',
    'PCOD',
    'AI health assistant',
    'India',
    'multilingual',
    'offline-first',
  ],
  generator: 'v0.app',
  icons: {
    icon: '/favicon.ico',
    apple: '/favicon.ico',
  },
  openGraph: {
    title: 'Rhythma — AI for Every Phase of Her Health',
    description:
      'A multilingual, offline-first, AI-powered menstrual and women’s health companion built for India. Track your cycle, understand your patterns, and get guidance in your language.',
    url: 'https://rhythma-navy.vercel.app',
    siteName: 'Rhythma',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Rhythma — AI for Every Phase of Her Health',
    description:
      'A multilingual, offline-first, AI-powered menstrual and women’s health companion built for India.',
    site: '@rhythmaAI',
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="font-sans antialiased">
        {children}
        {process.env.NODE_ENV === 'production' && <Analytics />}
      </body>
    </html>
  )
}
