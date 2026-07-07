# Estrategia de licencia Micelia — anti-centralización por diseño

> **Versión**: v1
> **Estado**: borrador para aprobación del Nodo 1
> **Cierra**: marcador V6 de `docs/PROPUESTA_MARC_VIDAL.md`
> **Fecha**: 2026-05-24 · **Owner**: Jessicache (Nodo 1)

---

## 0. Resumen ejecutivo

Una sola licencia no protege contra Big Tech. La protección real es una **defensa en profundidad** combinando cinco capas: licencia de código, marca registrada, gobernanza del copyright, contrato de contribución (CLA) y protocolo de federación abierto. Cada capa tapa una vía de captura que las demás no cubren.

**Recomendación canónica para Micelia v0.1**:

| Capa | Decisión | Defiende contra |
|---|---|---|
| 1. Licencia del orquestador (`app/`) | **AGPLv3** | Hosting parasitario tipo AWS-Elastic — cualquier SaaS basado en Micelia debe liberar mejoras |
| 2. Licencia de módulos nuevos (windowed) | **FSL-1.1-ALv2** (Functional Source License → Apache 2.0 tras 2 años) | Captura comercial inmediata sin ventana competitiva justa |
| 3. Protocolo de federación entre nodos | **Apache 2.0** | Walled gardens — cualquiera puede implementar un cliente compatible |
| 4. Marca "Micelia" | **Trademark** EUIPO + USPTO | Forks comerciales que reutilicen el nombre |
| 5. Copyright holder + CLA | **Cooperativa/Fundación Micelia** con CLA cooperativo | Captura del proyecto vía adquisición de la entidad mantenedora |

La razón por la que NO recomendamos SSPL como capa primaria está en §5.

---

## 1. El problema concreto: ¿de qué nos defendemos?

Antes de elegir herramientas, listamos amenazas reales. Una licencia es defensa solo si tapa al menos una de estas:

| # | Amenaza | Ejemplo histórico | Vector |
|---|---|---|---|
| A1 | **Hosting parasitario**: una BigCloud (AWS/GCP/Azure) lanza "Managed Micelia" sin contribuir mejoras al upstream | AWS Elasticsearch Service (2015) | SaaS de terceros sobre código abierto |
| A2 | **Fork comercial con extracción de marca**: alguien forkea Micelia, le llama "Micelia Pro" y captura mercado | Múltiples casos con MongoDB, MySQL | Trademark abandonado |
| A3 | **Captura por adquisición**: una corporación compra la entidad mantenedora y relicencia el código a propietario | Travis CI (Idera), Atom (Microsoft) | Copyright concentrado en una entidad capturable |
| A4 | **Captura por contribuidores**: un contribuidor mayoritario fuerza un cambio de licencia futura | Audacity (Muse Group, 2021) | CLA permisivo sin cláusulas cooperativas |
| A5 | **Walled garden**: un fork crea un protocolo incompatible para fragmentar la red | Mastodon vs Threads (federación parcial) | Protocolo no estandarizado |
| A6 | **Tecnofeudalismo IA**: el código es libre pero los modelos/datos no lo son, el nodo queda atado al proveedor del modelo | OpenAI fine-tunes propietarios | Dependencias propietarias no licenciadas |

Las cinco capas de la recomendación se mapean directamente a estas amenazas:

| Amenaza | Capa que la tapa |
|---|---|
| A1 Hosting parasitario | Capa 1 (AGPLv3) + Capa 2 (FSL windowed) |
| A2 Fork con extracción de marca | Capa 4 (trademark) |
| A3 Captura por adquisición | Capa 5 (foundation copyright) |
| A4 Captura por contribuidores | Capa 5 (CLA cooperativo) |
| A5 Walled garden | Capa 3 (protocolo Apache 2.0) |
| A6 Tecnofeudalismo IA | Política operativa (no licencia): obligar a usar modelos open-weight |

---

## 2. Licencias de código consideradas

Análisis comparativo de las opciones modernas:

### 2.1 AGPLv3 — Affero GPL

**Qué hace**: copyleft fuerte que se extiende a servicios de red. Si alguien ofrece Micelia como servicio (SaaS, hosted), debe liberar el código completo del servicio bajo AGPLv3 también.

**Pro**:
- Aprobada por la FSF y la OSI → categoría "open source" sin asterisco
- Defiende contra A1 (hosting parasitario) por diseño
- Compatible con la mayoría de ecosistemas Python
- Carrera comprobada: Nextcloud, MongoDB (antes de SSPL), GitLab Community Edition

**Contra**:
- Muchas empresas tienen políticas explícitas contra usar AGPL (Google la prohíbe internamente) → reduce adopción enterprise
- Para Micelia, esto es **una característica, no un bug**: queremos que el código no acabe absorbido dentro de Google

**Veredicto**: **SÍ para Capa 1**. Es la base copyleft de servicio del orquestador.

### 2.2 SSPL — Server Side Public License (MongoDB, Elastic)

**Qué hace**: extensión hiper-agresiva de AGPL. Si ofreces el software como servicio, debes liberar TODA la stack que lo hace funcionar (orquestación, monitorización, balanceadores, etc.).

**Pro**:
- Defensa máxima contra hosting parasitario
- Probada en juicios (no hay litigios perdidos)

**Contra**:
- **Rechazada por OSI y Debian como "no open source"** — esto importa: ningún distribuidor Linux incluirá Micelia, ningún proyecto que requiera deps OSI puede usarlo
- Aleja a contribuidores ideológicos (los que más nos interesan)
- La narrativa cooperativa de Micelia se rompe si la licencia es vista como "más restrictiva que open source"
- MongoDB perdió goodwill significativo tras el cambio en 2018

**Veredicto**: **NO**. SSPL es ingeniería defensiva sólida pero rompe la coherencia narrativa cooperativa. Lo que SSPL aporta extra (proteger toda la stack del SaaS), Micelia no lo necesita porque el orquestador es el único punto crítico — y AGPL ya lo cubre.

### 2.3 BSL — Business Source License (HashiCorp, MariaDB)

**Qué hace**: source-available durante una ventana (típicamente 4 años) con restricciones de uso comercial competitivo. Después se convierte a open source clásico (normalmente Apache 2.0).

**Pro**:
- Ventana de ventaja competitiva real para el proyecto madre
- Conversión futura garantiza commitment open source
- Adoptada por proyectos serios (HashiCorp Vault/Terraform fueron BSL hasta 2024)

**Contra**:
- Durante la ventana NO es open source → mismo problema reputacional que SSPL
- Define "uso competitivo" de forma ambigua → litigio potencial
- 4 años es demasiado para módulos pequeños

**Veredicto**: **NO como capa primaria**. La variante FSL (sección siguiente) resuelve los problemas de BSL.

### 2.4 FSL — Functional Source License (Sentry, 2023)

**Qué hace**: variante moderna de BSL con ventana de **2 años** (más razonable) y conversión automática a Apache 2.0 o MIT al final. Diseñada por el equipo legal de Sentry para resolver problemas reales de BSL.

**Pro**:
- Ventana competitiva justa (2 años en lugar de 4)
- Conversión a Apache 2.0 (FSL-1.1-ALv2) o MIT (FSL-1.1-MIT) clara
- Definición de "uso competitivo" más limpia que BSL
- Apoyo de Sentry (proyecto serio, no startup hype)
- Permite uso interno corporativo sin restricciones (la restricción es "no rehospedes como servicio compitiendo conmigo")

**Contra**:
- Aún no probada en juicio (es reciente)
- Como BSL, durante 2 años no es estrictamente open source

**Veredicto**: **SÍ para Capa 2 (módulos nuevos)**. Aplicarla a módulos que entren al proyecto desde hoy, con conversión a Apache 2.0 (no MIT — más coherente con la capa de protocolo).

### 2.5 ELv2 — Elastic License v2

**Qué hace**: similar a SSPL pero permite uso interno y consultoría, prohíbe hosting competitivo y prohíbe modificar mecanismos de licencia.

**Veredicto**: **NO**. ELv2 está diseñada específicamente para Elastic Stack (un caso comercial muy concreto). Para Micelia, FSL es más limpia y mejor diseñada legalmente.

### 2.6 PolyForm — familia de licencias source-available

**Qué hace**: PolyForm es una iniciativa que estandariza licencias source-available con permisos variables (Free, Noncommercial, Shield, Strict, Small Business, Perimeter).

**Pro**: catálogo bien estructurado, plain English, redactado por abogados especializados (Heather Meeker).

**Contra**: las variantes "Free" se aproximan a MIT (no protege) y las restrictivas son menos famosas que BSL/FSL.

**Veredicto**: **NO como capa primaria**. PolyForm Perimeter podría considerarse para un módulo enterprise específico si en el futuro hay servicios comerciales, pero no encaja como licencia del core.

### 2.7 Licencias cooperativas y éticas

Variantes ideológicas a considerar:

- **Peer Production License (PPL)**: basada en CC BY-NC-SA, permite uso comercial SOLO a cooperativas y trabajadores autónomos. Encaja narrativamente con Micelia.
- **Cooperative Software License (CSL)**: similar PPL pero específica de software.
- **Anti-Capitalist Software License (ACSL)**: prohíbe uso por entidades capitalistas con ≥10 empleados.
- **Hippocratic License**: prohíbe usos que violen DDHH.

**Veredicto**: **NO como licencia primaria** (ninguna está aprobada por OSI, tienen problemas de enforcement legal, alejan a contribuidores que no comparten la ideología), **PERO** considerar **referenciar PPL como guía ética declarativa** en un archivo `ETHICAL_USE.md` separado (no legalmente vinculante pero narrativamente coherente).

---

## 3. Capa 3: protocolo de federación abierto (anti walled-garden)

La amenaza A5 (walled garden) NO la resuelve la licencia del código. Si Micelia es un orquestador centralizado y alguien lo forkea con protocolo incompatible, la red se fragmenta.

**Decisión**: definir un **Micelia Federation Protocol (MFP)** como spec separada del código, publicada bajo **Apache 2.0**. Esto permite que:

- Cualquiera implemente un nodo compatible (en cualquier lenguaje, con cualquier licencia)
- Diferentes implementaciones puedan federar entre sí
- El protocolo evolucione vía proceso público (RFC-style)
- Big Tech NO pueda crear "su" Micelia incompatible — si quieren federar, deben implementar el protocolo

**Referencia operativa**: el equivalente a ActivityPub para el Fediverso (Mastodon, Pixelfed, Lemmy todos federan vía ActivityPub aunque cada implementación es distinta). Apache 2.0 es la licencia estándar para specs de protocolo.

**Cuándo definirlo**: la spec MFP v0.1 puede esperar hasta que haya un segundo nodo no-jessicache. Es trabajo de **T8.x**, no de v0.1. Pero **mencionarlo en la propuesta a MV** como roadmap es importante.

---

## 4. Capa 4: trademark "Micelia"

Sin marca registrada, A2 (fork con extracción de marca) es trivial: cualquiera lanza "Micelia.io" o "Micelia Pro" y captura mercado.

**Acción**:

| Acción | Coste estimado | Plazo |
|---|---|---|
| Registro EUIPO (Unión Europea) — clase 9 (software) + clase 42 (servicios IT) + clase 41 (educación) | €850-1.200 | 4-6 meses |
| Registro USPTO (EEUU) | $700-1.500 | 8-14 meses |
| Registro WIPO (extensión internacional) | Variable | 12-18 meses |
| Vigilancia + oposiciones (anual) | €500-1.500 | continuo |

**Política de uso de la marca** (a publicar en `docs/TRADEMARK_POLICY.md`):
- Uso descriptivo permitido ("compatible con Micelia", "extensión para Micelia")
- Uso confuso prohibido ("Micelia Pro", "Micelia Enterprise") sin licencia de marca
- Forks deben renombrarse (no pueden llamarse "Micelia"). El código sigue libre bajo AGPL/FSL, la marca no.

Este es el modelo de Mozilla (Firefox tiene trademark, Iceweasel/Debian existió por años) y de Mastodon (la marca está protegida, las implementaciones compatibles no pueden llamarse "Mastodon").

---

## 5. Capa 5: copyright holder y CLA cooperativo

La amenaza A3 (captura por adquisición) ocurre cuando una sola entidad (persona física o empresa) tiene el copyright agregado del proyecto. Si esa entidad es comprable, el proyecto es comprable.

**Solución estructural**:

### 5.1 Entidad mantenedora del copyright

Tres opciones realistas:

| Opción | Coste setup | Pro | Contra |
|---|---|---|---|
| **Cooperativa de trabajo asociado** (España) | €3.000-6.000 | Coherente narrativamente con Micelia. Modelo democrático real | Setup legal pesado. Requiere 3+ socios. Régimen fiscal específico |
| **Asociación sin ánimo de lucro** (España, art. 22 CE) | €100-500 | Setup mínimo. Permite donaciones. Estructura ligera | Gobernanza menos democrática que cooperativa |
| **Fundación** (España, mínimo €30K dotación) | €30.000+ | Máxima protección legal. Patrimonio inalienable | Coste prohibitivo en v0.1. Considerar para v2+ |

**Recomendación v0.1**: **Asociación** ("Asociación Micelia para la Soberanía Computacional Cooperativa" o nombre similar) como copyright holder. Migrar a **Cooperativa** en v0.2 cuando haya 3+ nodos contribuidores activos. Considerar **Fundación** en v1.0 si el modelo demuestra tracción.

### 5.2 CLA (Contributor License Agreement)

El CLA es el contrato que cada contribuidor firma al hacer su primer PR. Define quién tiene los derechos sobre la contribución.

**Recomendación: CLA cooperativo derivado del DCO + Apache CLA**, con dos cláusulas adicionales específicas:

1. **Cláusula de no-relicenciamiento sin voto cooperativo**: cualquier cambio futuro de licencia requiere voto mayoritario de los nodos activos (definidos como contribuyentes en los últimos 12 meses), no decisión unilateral de la asociación.

2. **Cláusula de reversión por captura**: si la entidad mantenedora es adquirida o cambia de gobernanza fuera del marco cooperativo, los derechos de copyright revierten automáticamente a una entidad sucesora elegida por los nodos contribuyentes.

Estas dos cláusulas son inusuales pero defensibles legalmente (similar a los "poison pill provisions" corporativos pero al revés: en lugar de proteger management, protegen comunidad).

**Plantilla base sugerida**: el CLA de Software Conservancy adaptado con las cláusulas anteriores.

---

## 6. Capa adicional: política de modelos IA open-weight

Una observación crítica que ninguna licencia de código resuelve por sí sola (A6 tecnofeudalismo IA):

> Si Micelia es AGPLv3 pero depende exclusivamente de GPT-4 / Claude / Gemini (modelos cerrados), el nodo NO es soberano. Solo cambia el feudo: ya no es Microsoft, es OpenAI.

**Política operativa** (a publicar como `docs/AI_SOVEREIGNTY_POLICY.md`):

1. El orquestador **DEBE** funcionar con modelos open-weight (Llama, Mistral, Qwen, etc.) sin pérdida de funcionalidad core
2. Modelos propietarios (Claude, GPT) son **opcionales** y degradan gracefully si no están disponibles
3. **Ningún módulo del core puede depender exclusivamente** de un proveedor de modelo propietario
4. Los datos de entrenamiento generados por nodos contribuyentes son propiedad colectiva (CC-BY-SA), no transferibles a entrenadores de modelos propietarios

Esto no es ideología: es coherencia con la tesis Micelia. Si el nodo cuenta con cobertura básica por contribuir al progreso colectivo, pero el "progreso" termina en weights de OpenAI, el modelo socioeconómico se rompe.

---

## 7. Recomendación final consolidada

Estructura de archivos a publicar en el repo:

```
micelia/
├── LICENSE              # AGPLv3 (capa 1: orquestador)
├── LICENSE.fsl          # FSL-1.1-ALv2 (capa 2: módulos nuevos)
├── NOTICE               # Atribución y resumen multi-licencia
├── docs/
│   ├── LICENSING_STRATEGY.md       # Este documento
│   ├── TRADEMARK_POLICY.md         # Política de uso de la marca
│   ├── CLA.md                      # CLA cooperativo
│   ├── ETHICAL_USE.md              # Declaración ética (no vinculante, narrativa)
│   ├── AI_SOVEREIGNTY_POLICY.md    # Política modelos open-weight
│   └── FEDERATION_PROTOCOL.md      # Spec MFP (futuro T8.x)
└── COPYRIGHT
    └── (lista de copyright holders agregados — apunta a la entidad cooperativa)
```

### Mapeo final por componente

| Componente del repo | Licencia |
|---|---|
| `app/` (orquestador FastAPI) | **AGPLv3** |
| `sdk/python/` (SDK para nodos) | **Apache 2.0** (para máxima adopción del SDK) |
| `frontend/` (Next.js dashboard) | **AGPLv3** |
| Módulos nuevos a partir de hoy | **FSL-1.1-ALv2** (→ Apache 2.0 a los 2 años) |
| Documentación (`docs/`) | **CC BY-SA 4.0** |
| Datos sintéticos (`tests/e2e/fixtures/data.py`) | **CC0** (dominio público) |
| Spec del protocolo de federación (futuro) | **Apache 2.0** |
| Marca "Micelia" | **Trademark registrado** (no licenciable de uso comercial sin acuerdo) |

### Posicionamiento narrativo

Frase canónica para README y para el pitch a MV:

> *"Micelia es open source en el sentido que importa: nadie puede capturarlo. El código está bajo AGPL para que ningún hyperscaler pueda venderlo como servicio sin contribuir. La marca está registrada para que ningún fork extractivo pueda usurpar el nombre. El copyright vive en una cooperativa para que ninguna adquisición pueda relicenciarlo. Los modelos IA son open-weight para que ningún proveedor pueda convertirnos en su feudo. Esto no es 'open source con asterisco' — es ingeniería de soberanía."*

Esta frase resuelve textualmente la pregunta que MV haría en la reunión: *"¿qué impide que OpenAI o Meta forkee Micelia y lo absorba?"*. La respuesta es: cinco capas independientes, cada una bloqueando una vía de captura distinta.

---

## 8. Plan de implementación (acciones concretas)

| Acción | Plazo | Coste | Bloqueante para |
|---|---|---|---|
| Añadir `LICENSE` (AGPLv3) al repo + headers en `app/` | 1 día | €0 | Aceptación primer PR externo |
| Añadir `LICENSE.fsl` (FSL-1.1-ALv2) y mark módulos nuevos | 1 día | €0 | Próxima feature |
| Redactar `docs/CLA.md` (derivar de Apache CLA + cláusulas cooperativas) | 1 semana | €0-500 (revisión legal opcional) | Aceptación contribuciones externas |
| Constituir Asociación "Micelia para la Soberanía Computacional Cooperativa" (España) | 4-6 semanas | €100-500 | Captura copyright |
| Registrar marca EUIPO clases 9, 41, 42 | 4-6 meses | €850-1.200 | Pitch público y MV |
| Registrar marca USPTO | 8-14 meses | $700-1.500 | Expansión internacional |
| Publicar `docs/TRADEMARK_POLICY.md` | 1 día | €0 | Junto con marca |
| Publicar `docs/AI_SOVEREIGNTY_POLICY.md` | 2 días | €0 | Pitch a MV (refuerza tesis) |
| Auditoría de dependencias actuales (¿hay deps GPL incompatibles con AGPL?) | 3 días | €0 | Antes de publicar bajo AGPL |
| Migrar README con sección "Sobre la licencia" | 1 día | €0 | Junto con publicación |

**Camino crítico hasta el pitch a MV** (sección 7 del doc PROPUESTA_MARC_VIDAL):

1. Día 1-2: añadir LICENSE + LICENSE.fsl + sección README
2. Día 3-5: redactar CLA + ETHICAL_USE + AI_SOVEREIGNTY
3. Semana 2: iniciar registro EUIPO (no esperar a tenerlo concedido para el pitch — basta con "solicitado")
4. Semana 2: iniciar trámites Asociación
5. Semana 3: pitch a MV con licencia ya en repo + marca solicitada + estructura cooperativa en formación

---

## 9. Decisiones explícitamente RECHAZADAS y por qué

| Opción | Por qué NO |
|---|---|
| **MIT/Apache puros** | Permite a Big Tech capturar sin contribuir (A1) |
| **GPLv3 puro (no Affero)** | No cubre el caso SaaS — un hyperscaler podría ofrecer Micelia como servicio sin liberar mejoras |
| **SSPL** | Rechazada por OSI; rompe narrativa cooperativa; lo que aporta extra sobre AGPL no es necesario para Micelia |
| **BSL clásica (4 años)** | Ventana demasiado larga; FSL la mejora |
| **Comercial closed-source puro** | Incompatible con la tesis del doc Nodo 1 (sistema cooperativo, no propietario) |
| **Dual licensing AGPL + comercial** | Modelo MongoDB pre-SSPL — requiere copyright concentrado en una entidad, vulnerable a A3 |
| **Anti-Capitalist Software License (ACSL)** | Excluye contribuidores valiosos (incluidos individuos en empresas grandes que aportarían). Estética sin enforcement |

---

## 10. Riesgos y mitigaciones de esta estrategia

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| AGPLv3 reduce adopción enterprise | Alta | Medio | **Intencional**: queremos que Micelia se adopte cooperativamente, no en silos enterprise |
| FSL es nueva y no probada legalmente | Media | Bajo | El soporte de Sentry da legitimidad; si surge problema, revertir a AGPL es trivial |
| Coste registro marca + asociación (~€1.500 + €500) | Baja | Bajo | Coste razonable para v0.1; recuperable vía membresías/donaciones |
| Foundation lenta de constituir bloquea contribuciones | Media | Bajo | Mientras se constituye, copyright temporal del Nodo 1 con compromiso público de transferencia a la entidad |
| Trademark se rechaza por similitud con marcas existentes | Baja | Medio | Búsqueda previa en EUIPO/USPTO antes del registro |
| Algún contribuidor potencial rechaza CLA cooperativo | Media | Bajo | El CLA estándar de Software Conservancy es ampliamente aceptado; las dos cláusulas extra son razonables |

---

## 11. Fuentes y referencias

- [Affero General Public License v3 (AGPLv3)](https://www.gnu.org/licenses/agpl-3.0.html) — FSF
- [Functional Source License (FSL)](https://fsl.software/) — Sentry, 2023
- [Server Side Public License (SSPL)](https://www.mongodb.com/legal/licensing/server-side-public-license) — MongoDB
- [Business Source License 1.1](https://mariadb.com/bsl11/) — MariaDB
- [Elastic License v2](https://www.elastic.co/licensing/elastic-license)
- [PolyForm Project licenses](https://polyformproject.org/)
- [Open Source Initiative — Licenses](https://opensource.org/licenses/)
- [Software Freedom Conservancy — Sample CLAs](https://sfconservancy.org/projects/policies/)
- [Heather Meeker — Open (Source) for Business](https://www.amazon.com/Open-Source-Business-Practical-Licensing/dp/1544083009) (referencia de redacción de licencias)
- [The Apache Way — Governance](https://apache.org/theapacheway/)
- [Mastodon trademark policy](https://joinmastodon.org/trademark)
- [Mozilla trademark policy](https://www.mozilla.org/en-US/foundation/trademarks/policy/)
- [Peer Production License (PPL)](https://wiki.p2pfoundation.net/Peer_Production_License)
- [Anti-Capitalist Software License (ACSL)](https://anticapitalist.software/)
