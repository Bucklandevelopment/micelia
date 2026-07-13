import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

const PUBLIC_PATHS = ['/login', '/register']

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow public paths and static assets
  if (PUBLIC_PATHS.some(p => pathname.startsWith(p))) {
    return NextResponse.next()
  }

  // Allow API proxy routes (handled by next.config rewrites)
  if (pathname.startsWith('/api')) {
    return NextResponse.next()
  }

  // Check for auth cookie
  const token = request.cookies.get('vital_auth')?.value
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return NextResponse.next()
}

export const config = {
  // Excluir assets estáticos y, crucialmente, el service worker de MSW.
  // Sin la exclusión de mockServiceWorker.js, el middleware redirige el
  // worker a /login (no hay cookie auth) y el browser no puede seguir
  // redirects al cargar un service worker → MSW nunca se registra → modo
  // mock no funciona.
  matcher: ['/((?!_next/static|_next/image|favicon.ico|mockServiceWorker.js).*)'],
}
