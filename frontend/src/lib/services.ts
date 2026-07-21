/**
 * Catálogo de servicios del ecosistema UTOP.IA orquestado por Micelia.
 *
 * El panel de Micelia no proxeaba ni enlazaba los frontends de los dominios: el
 * gateway solo hace reverse-proxy de los *backends* bajo `/api/v1/gateway/*`. Este
 * catálogo alimenta la página `/servicios`, que da acceso directo a cada frontend y
 * muestra la salud viva de los dominios que el registry del gateway monitoriza
 * (`GET /api/v1/health/services` → claves `health|research|education|security`).
 *
 * Las URLs de frontend se leen de variables `NEXT_PUBLIC_*_URL` con default al mapa
 * de puertos nativo local. FUENTE DE VERDAD del mapa: `scripts/ecosystem-ports.json`
 * (DP-12); si cambias un puerto default aquí, cámbialo también en el JSON —
 * `test_ecosystem_ports_manifest_codex.py` lo verifica en `make verify`. Mañana estas
 * URLs pueden apuntar a los subdominios de idmmortality.com sin tocar código. NOTA: en
 * Next.js solo se inlinean los accesos LITERALES a `process.env.NEXT_PUBLIC_*`; por eso
 * cada uno se escribe explícito y no con clave dinámica.
 */

/** Forma de cada entrada de `GET /api/v1/health/services` (registry del gateway). */
export interface RegistryServiceStatus {
  name: string
  url: string
  enabled: boolean
  healthy: boolean
  latency_ms: number | null
  error: string | null
  version: string | null
}

export interface ServiceCatalogEntry {
  /** Identificador estable para React keys. */
  id: string
  nombre: string
  descripcion: string
  /** Clave en `/health/services` para la salud viva, o null si no está en el registry. */
  registryKey: 'health' | 'research' | 'education' | 'security' | null
  /** URL del frontend (o de la doc/API para servicios sin SPA). */
  frontendUrl: string
  /** false → el servicio no tiene SPA web (se enlaza a su API/doc). */
  tieneWebUI: boolean
  /** Texto del botón de acceso. */
  enlaceLabel: string
  /**
   * true → el dominio acepta SSO de Micelia (C119): al abrirlo, el hub le pasa el access
   * token en el fragmento de la URL (`#sso_token=…`) para que el usuario llegue ya logueado.
   * Solo para dominios cuyo backend valida el JWT de Micelia (hoy: biohack).
   */
  sso?: boolean
}

export const serviceCatalog: ServiceCatalogEntry[] = [
  {
    id: 'biohack',
    nombre: 'Biohack',
    descripcion: 'Salud y longevidad — HealthKit, ECG, nutrición, predicciones ML.',
    registryKey: 'health',
    frontendUrl: process.env.NEXT_PUBLIC_BIOHACK_URL || 'http://localhost:5173',
    tieneWebUI: true,
    enlaceLabel: 'Abrir panel',
    sso: true,
  },
  {
    id: 'canela',
    nombre: 'Canela Molida',
    descripcion: 'Investigación y RAG — ingesta de papers, síntesis, búsqueda semántica.',
    registryKey: 'research',
    frontendUrl: process.env.NEXT_PUBLIC_CANELA_URL || 'http://localhost:8501',
    tieneWebUI: true,
    enlaceLabel: 'Abrir Streamlit',
  },
  {
    id: 'ideacursi',
    nombre: 'Ideacursi',
    descripcion: 'Educación — cursos, lecciones, quizzes y logros.',
    registryKey: 'education',
    frontendUrl: process.env.NEXT_PUBLIC_IDEACURSI_URL || 'http://localhost:6060',
    tieneWebUI: true,
    enlaceLabel: 'Abrir panel',
  },
  {
    id: 'cybertools',
    nombre: 'Cybertools',
    descripcion: 'Seguridad — SCANet, análisis WiFi/OSINT. Sin SPA: se accede a su API.',
    registryKey: 'security',
    frontendUrl: process.env.NEXT_PUBLIC_CYBERTOOLS_URL || 'http://localhost:8000/docs',
    tieneWebUI: false,
    enlaceLabel: 'Ver API docs',
  },
  {
    id: 'codking',
    nombre: 'CodKing',
    descripcion: 'IA de seguridad — visualizer del framework RLM. Sin sonda de salud en el registry.',
    registryKey: null,
    frontendUrl: process.env.NEXT_PUBLIC_CODKING_URL || 'http://localhost:3009',
    tieneWebUI: true,
    enlaceLabel: 'Abrir visualizer',
  },
  {
    id: 'automation',
    nombre: 'Auto-mat-ion',
    descripcion: 'Testing y validación — demo web de sensores. Sin sonda de salud en el registry.',
    registryKey: null,
    frontendUrl: process.env.NEXT_PUBLIC_AUTOMATION_URL || 'http://localhost:8891',
    tieneWebUI: true,
    enlaceLabel: 'Abrir demo',
  },
]
