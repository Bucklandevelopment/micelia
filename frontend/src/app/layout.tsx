import type { Metadata } from 'next'
import { Providers } from './providers'
import './globals.css'

export const metadata: Metadata = {
  title: 'Micelia — Orquestador del ecosistema',
  description: 'Micelia: orquestador central del ecosistema UTOP.IA',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="es" className="dark">
      <body className="min-h-screen bg-bg-primary text-text-primary font-body antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}
