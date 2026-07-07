/** @type {import('next').NextConfig} */
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true'

const nextConfig = {
  reactStrictMode: true,

  // Proxy API requests to Micelia backend.
  //
  // IMPORTANT: cuando NEXT_PUBLIC_USE_MOCK=true (modo MSW), NO añadimos
  // rewrite. Si lo añadiéramos, Next.js proxearía /api/v1/* server-side al
  // backend real antes de que la request llegara al browser, y MSW (que vive
  // en el browser) nunca tendría oportunidad de interceptar. Sin rewrite, las
  // requests son client-side y MSW las captura como debe.
  async rewrites() {
    if (USE_MOCK) {
      console.log('[next.config] NEXT_PUBLIC_USE_MOCK=true → rewrites desactivados, MSW intercepta en el browser')
      return []
    }
    return [
      {
        source: '/api/v1/:path*',
        destination: `${process.env.MICELIA_URL || process.env.IDM_CORE_API_URL || 'http://localhost:8888'}/api/v1/:path*`,
      },
    ]
  },

  // External links configuration
  async redirects() {
    return [
      {
        source: '/metrics/grafana',
        destination: 'http://localhost:3000',
        permanent: false,
        basePath: false,
      },
      {
        source: '/metrics/prometheus',
        destination: 'http://localhost:9090',
        permanent: false,
        basePath: false,
      },
    ]
  },
}

module.exports = nextConfig
