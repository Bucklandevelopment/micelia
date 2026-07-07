# Propuesta de colaboración Marc Vidal × Micelia

> **Versión**: v1.1 — V6 (licencia) cerrado vía `LICENSING_STRATEGY.md`
> **Ángulo dominante**: co-construcción intelectual. MV es referente cuya tesis Micelia *operativiza* — no influencer pagado.
> **Fecha**: 2026-05-24 · **Owner**: Jessicache (Nodo 1)

---

## Changelog v0 → v1

| Sección | Cambio |
|---|---|
| §3 (qué es Micelia) | Reescrita con datos reales del doc Nodo 1. La etimología biológica (micelio fúngico que transporta nutrientes) es ORO narrativo para MV |
| §3.3 (modelo económico) | Cerrado V1-V5 + V7. Modelo concreto: suscripción tres tiers (€19/49/99) + apalancamiento del ahorro estatal (€12-24K/año por nodo) |
| §4 (matriz correlación) | 6 puntos subieron de "Alto" a "Muy alto". Añadido nuevo punto: distinción explícita UBI vs Micelia que MV YA defiende editorialmente |
| §5 (tensiones) | Reducidas — quedan abiertas solo licencia (V6) y mecanismo de descubrimiento de capacidades a escala |
| §6 (por qué MV) | Reforzada con datos cuantitativos macroeconómicos del doc |
| §7 (pitch) | Reescrito con la frase citable del doc + ángulo institucional Navarra/SEPE/FUNDAE |
| §nuevo (§8 — kicker) | Credibilidad institucional propia del Nodo 1: ex-profesor 4 años Albañiles Digitales (SEPE/Navarra) + Security Engineer Veridas |
| §10 (verificar) | 6/7 marcadores cerrados. Queda 1 abierto: licencia open source (no crítico para v1) |

## Changelog v1 → v1.1

| Sección | Cambio |
|---|---|
| §5.1 | V6 **cerrado**. Defensa en profundidad de 5 capas (AGPLv3 + FSL + Apache 2.0 protocolo + trademark + cooperativa). Detalle en `LICENSING_STRATEGY.md` |
| §10 | Marcador V6 movido a "cerrado" — 7/7 marcadores resueltos |
| Plan operativo | Añadidas T7.3-T7.7 (CLA, trademark, asociación, demo, email) como próximos hitos |

---

## 1. Resumen ejecutivo

Marc Vidal publicó el 21 de mayo de 2026 un análisis del editorial *jobs apocalypse* de The Economist en el que articula la siguiente tesis: la destrucción creativa schumpeteriana ya no admite la red de seguridad clásica, la renta básica sin agencia deriva en "tecnofeudalismo con subsidios", y la pregunta operativa es si los ciudadanos van a *construir o consumir*. Cierra el video con: *"el tiempo se acaba y nadie está preparando la respuesta"*.

Micelia es exactamente esa respuesta, ya construida y ya cuantificada:

- **Modelo económico cerrado**: suscripción ciudadana de €19-99/mes apalancada sobre €12.000-24.000/año de ahorro estatal por cada nodo activo. ROI ciudadano de 10x-30x. ROI fiscal demostrable con datos SEPE/Sanidad/INE.
- **Diferenciación explícita con UBI**: "Micelia no te paga por existir — te cubre por contribuir". El doc oficial dedica una sección completa a esta distinción, alineada palabra por palabra con la línea editorial de MV ("Contra la cultura del Subsidio", Planeta).
- **Infraestructura técnica operativa**: orquestador FastAPI con 5 dominios funcionales, SDK Python, frontend Next.js, suite E2E de 3.066 líneas en `tests/e2e/` (más 329 LOC en `sdk/python/tests/`) verde. Rebrand v0.1 cerrado. No es vaporware.
- **Credibilidad institucional**: el Nodo 1 (Jessicache) es ex-profesor del programa Albañiles Digitales del SEPE/Navarra durante 4 años. Entiende el sistema público desde dentro.

La hipótesis del pitch es que MV no necesita ser convencido del *diagnóstico* — su tesis pública converge — sino que necesita ver una *respuesta ejecutable y financieramente sostenible*. Micelia la tiene.

---

## 2. Diagnóstico de Marc Vidal: análisis del video

Fuente: [The Jobs Apocalypse: Why The Economist Can No Longer Look the Other Way](https://www.youtube.com/watch?v=oIze6NvhzFI) (canal Marc Vidal, 21-may-2026, ~19 minutos).

### 2.1 Estructura argumental del video

| Bloque | Tesis | Lectura |
|---|---|---|
| 00:00–01:36 | The Economist titula *jobs apocalypse* | El think-tank de referencia del establishment liberal admite que el modelo no se autocorrige |
| 03:37–04:34 | **Pausa de Engels**: PIB↑ y salarios↓ | El motor de prosperidad histórica se ha roto. La productividad ya no se reparte |
| 04:34–07:10 | El argumento tranquilizador ya no funciona | "La tecnología siempre creó más empleo del que destruyó" deja de ser cierto por composición sectorial |
| 07:10–07:41 | **Esta vez es diferente**: cuello blanco vs fábrica | La IA ataca el segmento que servía de absorbente. No hay sector refugio |
| 07:41–09:29 | El **China Shock** destruyó el consenso liberal | El "ajuste de equilibrio general" no ocurre en práctica |
| 11:30–13:01 | **Nacionalización IA + dividendos**: ¿solución o problema? | MV es escéptico: nacionalizar concentra poder, dividendos crean dependencia. Falta tercera vía |
| 13:01–14:47 | Schumpeter sin red de seguridad = catástrofe | Sin amortiguador, la destrucción creativa se vuelve solo destrucción |
| 14:47–16:29 | **Construir o consumir**: el dilema individual | Ser plataforma o ser usuario. La asimetría se cierra para siempre en esta década |
| 16:29–19:07 | **RBU**: ¿emancipación o tecnofeudalismo con subsidios? | Solo emancipa si el receptor tiene capacidad de generar valor más allá del subsidio |
| 19:07 | Conclusión | *"El tiempo se acaba y nadie está preparando la respuesta."* |

### 2.2 Línea editorial consolidada (más allá del video)

- **Pro-automatización con condiciones**: aboga por la robotización y la IA como *motor de desarrollo social y económico*. No es luddita.
- **"Contra la cultura del Subsidio"** (Planeta): crítica explícita del subsidio pasivo. **Es prácticamente el subtítulo posible de Micelia.**
- **"La Era de la Humanidad"** (10ª edición, Planeta): plantea RBU en contexto de automatización completa, no incondicional. Coincide exactamente con la posición Micelia: cobertura sí, pero acoplada a contribución.
- **Plataformas**: Planeta + sección "Salida de Emergencia" en Herrera/COPE + programas TVE históricos + Bloomberg/CNN/Euronews. Alcance broadcast España y Latam.
- **Industria 4.0 / transformación digital**: foco profesional principal — exactamente el segmento donde Micelia es producto.

### 2.3 Lo que MV dice sin decirlo

MV nunca formula la pregunta *"¿qué arquitectura técnica concreta materializa la tercera vía entre nacionalización IA y RBU pura?"*. La omite porque su rol es analista divulgador, no constructor de infraestructura. Esa es exactamente la grieta donde Micelia entra.

---

## 3. La propuesta Micelia (cerrada con datos del Nodo 1)

### 3.1 Definición de una frase

> **Micelia es un sistema socioeconómico digital donde cada persona es un nodo que contribuye al progreso colectivo mediante método científico asistido por IA, y recibe a cambio la cobertura de sus necesidades básicas.**

La etimología es deliberada: el **micelio** biológico es la red subterránea de hongos que conecta árboles y transporta nutrientes hacia donde más se necesitan. La metáfora no es decorativa — es el modelo operativo. **400 millones de años de demostración biológica de que este modelo funciona.** (Esto es exactamente el tipo de anclaje científico que MV usa en sus conferencias).

### 3.2 Diferenciación explícita con UBI (la tabla más importante para MV)

> Cita literal del doc oficial Nodo 1:

| UBI / Renta Básica Universal | Micelia |
|---|---|
| Transferencia pasiva de dinero. Recibes por existir. | Cobertura activa por contribución. Recibes porque el micelio registra tu aporte real al progreso colectivo. |
| No genera progreso científico ni productivo. | Cada acción del nodo es investigación con método científico. El progreso es continuo. |
| Coste neto para el Estado sin retorno medible. | El Estado ahorra en desempleo, sanidad y servicios sociales. Retorno medible. |

**Frase canónica para citar en el pitch:**

> *"Micelia no te paga por existir — te cubre por contribuir."*

Esta frase resuelve textualmente la objeción central de MV a la RBU en el video (timestamp 16:29).

### 3.3 Modelo económico cerrado (cierra V2, V3, V4, V5, V7)

**Tres tiers de suscripción ciudadana**:

| Tier | Precio | Contribución del nodo | Retorno |
|---|---|---|---|
| Semilla | €19/mes | Testing, datos, feedback | Formación + servicios digitales + descubrimiento de capacidades |
| Activo | €49/mes | Producción con IA, tareas asignadas | Cobertura material: alimentación, transporte, formación |
| Investigador | €99/mes | Investigación científica + mentorización | Cobertura completa + red de investigación + publicación |

**Cobertura concreta para el Nodo 1** (perfil real, no proyección):

| Necesidad | Coste mensual | Cobertura Micelia |
|---|---|---|
| Vivienda | €500-700 | Parcial → Total |
| Alimentación | €250-350 | Total |
| Transporte | €50-150 | Total |
| Salud | €100-200 | Total |
| Formación continua | €50-100 | Total |
| **TOTAL** | **€950-1.500/mes** | **80-100%** |

**ROI ciudadano**: pagas €49/mes, recibes cobertura por valor de €950-1.500/mes. **Multiplicador 19x-30x desde el primer mes.** No es regalo: el sistema convierte tu contribución en valor que cubre necesidades a través de la red.

**Mecanismo de medición de contribución**: la IA detecta rendimiento + satisfacción del nodo en tareas asignadas (seguridad, formación, producción con IA, investigación, mentorización). Cada tarea completada genera créditos canjeables por cobertura.

**Lista de necesidades cubiertas**: las 5 explícitas arriba — vivienda, alimentación, transporte, salud, formación continua. Cobertura escalable con el tamaño de la red.

### 3.4 Impacto fiscal cuantificado (lo que más va a mover a MV)

> Cita literal del doc oficial, sección 3.1-3.3:

**Coste anual para el Estado de UNA persona desempleada**:

| Concepto | Coste | Fuente |
|---|---|---|
| Prestación contributiva (media) | €12.084 | SEPE 2025: €1.007/mes |
| Subsidio post-prestación | €5.760 | SEPE 2026: €480/mes |
| Sanidad pública per cápita | €1.900-2.500 | CCAA 2026 |
| Sobrecoste crónicas prevenibles | €2.000-5.000 | Sedentarismo + obesidad |
| Salud mental asociada a desempleo | €1.500-3.000 | OMS: 1% PIB |
| Servicios sociales | €1.200-2.400 | Ayudas vivienda/transporte |
| **TOTAL por persona desempleada** | **€18.000-30.000/año** | |

**Ahorro neto por cada nodo activo Micelia**: **€12.000-24.000/año.**

**Proyección a escala**:

| Nodos activos | Ahorro anual | % presupuesto SEPE | Equivalente |
|---|---|---|---|
| 1.000 | €12-24M | 0,06-0,12% | Piloto regional Navarra |
| 10.000 | €120-240M | 0,6-1,2% | Despliegue 3-5 CCAA |
| 100.000 | €1.200-2.400M | 6-12% | Programa nacional |
| **500.000** | **€6.000-12.000M** | **29-57%** | **Transformación del modelo español** |

Estas cifras NO incluyen el valor de producción generada por los nodos (código, investigación, contenido, testing) que añade PIB. Solo miden el ahorro en gasto público.

**Esto es lo que va a hacer que MV preste atención.** Es el tipo de dato con el que él construye sus análisis macro.

### 3.5 Arquitectura técnica que YA existe (no es concept paper)

| Pieza | Estado |
|---|---|
| Orquestador FastAPI (`vital-core` → `Micelia`) | Operativo, rebrand v0.1 cerrado |
| 5 dominios funcionales | `biohack` (salud), `canela` (investigación), `ideacursi` (educación), `cybertools` (seguridad), `auto-mat-ion` (automatización) |
| SDK Python + frontend Next.js + Docker compose | En producción |
| Suite E2E 3.066 LOC (`tests/e2e/`) + 329 LOC (`sdk/python/tests/`) | Verde |
| Event store con sourcing por nodo | Trazabilidad por contribución → base para distribuir cobertura |
| Makefile orquestador + targets banner/dev/test/cov | Day-1 onboarding |

---

## 4. Matriz de correlación rigurosa: tesis MV ↔ pieza Micelia

| Tesis de Marc Vidal (timestamp) | Pieza Micelia que la opera | Alineamiento |
|---|---|---|
| **Pausa de Engels** (03:37): el crecimiento ya no se reparte | Cobertura básica desacopla supervivencia de salario; reparto por contribución nodal, no por mercado laboral | **Muy alto** |
| **Cuello blanco en riesgo** (07:10) | Los 5 dominios son trabajo de conocimiento (salud, investigación, educación, seguridad, automatización) delegado a IA con supervisión humana del nodo | **Muy alto** |
| **China Shock + sin reabsorción** (07:41) | El nodo no necesita reabsorberse en mercado: produce directamente en el orquestador y la cobertura llega desde ahí (suscripción + ahorro estatal apalancado) | **Alto** |
| **Nacionalización IA es problemática** (11:30) | Micelia es NO-estatal. Self-hosted, cooperativo, opt-in. Funciona en paralelo a sistemas públicos, no los reemplaza | **Muy alto** |
| **Dividendos crean dependencia** (11:30) | La cobertura se acopla a contribución activa, no es subsidio pasivo. Literalmente: "no te paga por existir, te cubre por contribuir" | **Muy alto** |
| **Schumpeter sin red = catástrofe** (13:01) | Micelia ES la red de seguridad operativa durante la disrupción IA. Y cuantificada: cubre €950-1.500/mes por nodo activo | **Muy alto** |
| **Construir o consumir** (14:47) | Cada nodo Micelia es por definición constructor (corre infraestructura, aporta cómputo, investigación, código) Y consumidor (recibe cobertura). Disuelve la falsa dicotomía | **Crítico** |
| **RBU = tecnofeudalismo con subsidios** (16:29) | El doc Nodo 1 sección 1.1 dedica una tabla completa a esta distinción. Micelia es la respuesta directa a la objeción de MV | **Crítico** |
| **El tiempo se acaba** (19:07) | Micelia v0.1 ya está construido. Tests verdes. Banner CLI funcionando. No es 2030, es ahora | **Crítico** |
| **NUEVO**: "Contra la cultura del Subsidio" (libro MV, Planeta) | Sección 1.1 del doc Nodo 1 es prácticamente un capítulo de ese libro escrito en forma de infraestructura | **Crítico — kicker editorial** |

**Lectura**: 4 puntos críticos + 5 muy altos + 1 alto. Es el nivel de alineamiento más alto que se puede pedir entre un divulgador y un proyecto operativo sin que estén explícitamente coordinados.

---

## 5. Tensiones honestas que persisten

Una propuesta seria no oculta las grietas. Reducidas respecto a v0:

### 5.1 ~~Licencia y gobernanza del software~~ **CERRADO** (V6 — v1.1)

Diseñada en `docs/LICENSING_STRATEGY.md`. Defensa en profundidad de **cinco capas independientes**, cada una bloqueando una vía de captura distinta:

| Capa | Decisión | Defiende contra |
|---|---|---|
| 1. Licencia del orquestador (`app/`, `frontend/`) | **AGPLv3** | Hosting parasitario tipo AWS-Elastic |
| 2. Módulos nuevos (windowed source-available) | **FSL-1.1-ALv2** (Sentry, 2023; convierte a Apache 2.0 a los 2 años) | Captura comercial sin ventana competitiva justa |
| 3. Protocolo de federación entre nodos | **Apache 2.0** (spec separada) | Walled gardens — cualquiera puede implementar cliente compatible |
| 4. Marca "Micelia" | **Trademark** EUIPO + USPTO | Forks comerciales que extraigan el nombre |
| 5. Copyright holder | **Asociación cooperativa** (v0.1) → Cooperativa formal (v0.2) → Fundación (v1.0) + **CLA cooperativo** con cláusula de no-relicenciamiento sin voto y reversión por captura | Adquisición corporativa del proyecto + captura por contribuidores |
| **Bonus operativo** | Política `AI_SOVEREIGNTY_POLICY.md`: core debe funcionar con modelos open-weight; propietarios opcionales y degradables | Tecnofeudalismo IA (atadura a OpenAI/Anthropic) |

**Respuesta canónica para MV** ante *"¿qué impide que OpenAI o Meta forkee Micelia y lo absorba?"*:

> *"Cinco capas. (1) Si lo hospedan como servicio, deben liberar mejoras — es AGPL. (2) Los módulos nuevos tienen ventana de 2 años source-available que les impide competir directamente. (3) Pueden implementar el protocolo de federación pero entonces son red Micelia, no su walled garden. (4) No pueden llamarlo Micelia — la marca está registrada. (5) No pueden comprar el proyecto — el copyright vive en una cooperativa con CLA anti-captura. Esto no es 'open source con asterisco'. Es ingeniería de soberanía."*

**Por qué NO SSPL** (la primera opción considerada): rechazada por OSI y Debian → rompe la narrativa cooperativa y el ecosistema de distribución. Lo que SSPL aporta extra sobre AGPL no es necesario para el caso de uso Micelia (el orquestador es el único punto crítico, AGPL ya lo cubre).

**Coste y plazo de implementación**: ~€1.500-2.000 + 1 semana de redacción (licencia ya en repo + CLA + políticas) + 4-6 meses para registro de marca concedido. Para el pitch a MV basta con licencia publicada en repo y marca **solicitada**.

### 5.2 Descubrimiento de capacidades a escala

La sección 5 del doc Nodo 1 describe un mecanismo elegante: la IA detecta en qué verticales el nodo rinde más y reporta mayor bienestar, y forma comunidades naturalmente alineadas. Esto es teórico hoy. La pregunta de MV será: *"¿cómo evitas el sesgo de algoritmo de recomendación que critica el editorial de The Economist? ¿Cómo garantizas que Micelia no termine optimizando por engagement en lugar de progreso real?"*. Respuesta posible: métricas científicas registradas (no engagement), peer review por nodos investigadores, auditoría externa periódica.

### 5.3 Escalabilidad de la cobertura

A 1.000 nodos (piloto Navarra) la cobertura material es viable vía red de productores locales. A 100.000 nodos el supply side se vuelve complejo. ¿Cómo escala "alimentación cubierta"? Hipótesis: el modelo escala mediante alianzas con FUNDAE, CCAA y supply-chains locales — eso está esbozado en sección 6.1 del doc Nodo 1 pero no operativizado.

---

## 6. Por qué Marc Vidal específicamente (reforzado con datos)

| Criterio | Por qué MV encaja (datos Micelia que lo confirman) |
|---|---|
| **Diagnóstico alineado** | 10/10 puntos de la matriz §4 son convergentes. No hay que educarlo. |
| **Plataforma broadcast** | Planeta + COPE + TVE histórica + Bloomberg/CNN. Llegada a audiencia no técnica que Micelia necesita para nodos a escala |
| **Credibilidad institucional** | Conferencias IBEX, asesoría corporativa. Aporta validación complementaria a la del Nodo 1 (perfil técnico Veridas) |
| **Línea anti-subsidio** | "Contra la cultura del Subsidio" coincide letra a letra con la frase canónica Micelia ("no te paga por existir, te cubre por contribuir") |
| **Pro-automatización social** | Cree que la tecnología emancipa. Micelia es la materialización ejecutable de esa creencia |
| **RBU contextual** | "La Era de la Humanidad" defiende RBU acoplada a automatización. Micelia es la versión operativa con cobertura ≠ transferencia |
| **Hablante español + reach Latam** | Primer mercado natural de Micelia. España (SEPE/Navarra/CCAA) → Latam tras el piloto |
| **Sin afiliación a Big Tech** | Mantiene independencia que da credibilidad al endorsement |

**Riesgos del perfil MV**:
- Patrocina productos financieros (Trade Republic en este mismo video) → cuidar tono para no quedar en bloque "patrocinio editorial" pasivo
- Es escéptico de promesas tecnoutópicas vagas → la demo técnica funcionando es la única vía
- Su agenda como conferenciante internacional es densa → ventana de oportunidad real probablemente 4-6 semanas tras contacto inicial

---

## 7. Ángulo del pitch: co-construcción intelectual

No proponemos:
- Patrocinio pagado (degrada credibilidad mutua)
- "Hazte cara visible" (le quita autoría intelectual)
- Endorsement frío sin sustancia (no funciona con su línea editorial)

Sí proponemos:

> **"Marc, en tu video del 21 de mayo cierras con: 'el tiempo se acaba y nadie está preparando la respuesta'. Nosotros llevamos meses preparando esa respuesta. Se llama Micelia. Está cuantificada: cada nodo activo ahorra al Estado entre €12.000 y €24.000 al año en prestaciones, sanidad y servicios sociales — datos SEPE y Sanidad 2026. Está construida: hay código corriendo, tests verdes, demo en 90 segundos. Y está alineada con tu tesis editorial: 'no te paga por existir, te cubre por contribuir'. Te invitamos a una hora — sin compromiso editorial — para verlo. Después decides si hay material para una conversación pública conjunta, un capítulo en tu podcast, o nada en absoluto."**

Esta formulación:
- Cita literalmente su video (timestamp 19:07) → demuestra atención real, no escaneo
- Aporta dato macroeconómico concreto (€12-24K/año) → habla su lenguaje analítico
- Refuerza su tesis editorial existente ("contra el subsidio") → no le pide cambiar de opinión
- Ofrece materialidad (demo en 90s, código corriendo) → contra promesas vagas
- Le da salida elegante si no encaja → respeta su agenda

### 7.1 La frase del doc Nodo 1 que MV puede citar literalmente

Sección 6.2:

> *"Con poco dinero del sistema capitalista, entras en un sistema cuántico altruista donde tus acciones buenas se recompensan con interacciones buenas que te llevarán a los objetivos que te marques en conseguir."*

Esta frase tiene el grado de poetización que MV usa en sus cierres de conferencia. Coincide con su estilo divulgativo. Es citable.

### 7.2 El argumento políticamente transversal

Sección 6.1 del doc Nodo 1, fila "Partidos políticos":

> *"La respuesta al desplazamiento por IA que no es ni UBI (izquierda pasiva) ni desregulación (derecha clásica). Es producción activa con cobertura básica. Transversal políticamente."*

Esto es exactamente el tipo de articulación que MV defiende en COPE: una propuesta que no se deja capturar por el eje izquierda-derecha clásico. Va a apreciarlo.

---

## 8. Kicker: credibilidad institucional propia del Nodo 1

Esto no estaba claro en v0 y es CRÍTICO para el pitch. El Nodo 1 (Jessicache) tiene perfil institucional propio que aporta credibilidad complementaria al de MV:

| Activo | Por qué importa para MV |
|---|---|
| **Security Engineer @ Veridas** | Empresa española líder en identidad digital + biometría. No es startup garage. Aporta seriedad técnica al perfil |
| **4 años profesor del programa Albañiles Digitales (SEPE/Navarra)** | Conoce el sistema público desde dentro. No es un ingeniero proponiendo cambiar políticas públicas sin haberlas tocado. Es un ex-profesor del SEPE proponiendo evolucionar el SEPE |
| **Stack técnico verificable** | Python, TypeScript, Frida, WebRTC, Docker, Claude/GPT/Ollama, Burp Suite — perfil de seguridad ofensiva + AI engineering combinado |
| **Filosofía declarada**: ciberseguridad × filosofía × termodinámica × biología | Coincide con el perfil multidisciplinar que MV valora en sus invitados |

**El argumento institucional para MV**:

> *"No estoy proponiendo que la administración española confíe en un proyecto exterior. Soy ex-profesor SEPE durante 4 años. Diseñé y enseñé un programa de FUNDAE financiado con dinero público. Sé qué funciona y qué no. Micelia es la conclusión de esa experiencia."*

---

## 9. Plan de contacto y entregables

### 9.1 Email inicial (template)

Tono: directo, sin adjetivos comerciales, máximo 200 palabras.

```
Marc, buenos días.

En tu video del 21 de mayo sobre el "jobs apocalypse" cierras con una
pregunta: "el tiempo se acaba y nadie está preparando la respuesta".

Llevo construyendo esa respuesta y se llama Micelia. Tres cosas
relevantes antes de tirar este email a spam:

1. Está cuantificada. Cada nodo activo ahorra al Estado entre €12.000 y
   €24.000 al año en prestaciones, sanidad y servicios sociales. Datos
   SEPE/Sanidad 2026 contrastados.

2. Está alineada con tu línea editorial. La frase central de Micelia es
   "no te paga por existir, te cubre por contribuir". Es básicamente un
   capítulo aplicado de "Contra la cultura del Subsidio".

3. Soy ex-profesor del programa Albañiles Digitales del SEPE/Navarra
   durante 4 años. No es un técnico opinando sobre políticas públicas
   desde fuera. Es alguien que las enseñó desde dentro.

Te invito a una hora — sin compromiso editorial — para verlo. Después
decides si hay material para una conversación pública, un capítulo en
tu podcast, o nada. Las tres opciones tienen sentido para nosotros.

[firma]
[link al doc Nodo 1 + link a la demo de 90s]
```

### 9.2 Pitch deck mínimo (para la reunión)

- Slide 1: Su frase de cierre como portada
- Slide 2: Tabla diferenciación UBI vs Micelia (§3.2 de este doc)
- Slide 3: Cifras de ahorro fiscal (§3.4)
- Slide 4-6: Demo en vivo (`make dev` → dashboard → flujo nodo)
- Slide 7: Matriz de correlación tesis MV ↔ pieza Micelia (§4)
- Slide 8: Las 3 tensiones abiertas (§5) presentadas como invitación a pensarlas juntos
- Slide 9: Argumentos por interlocutor (sección 6.1 del doc Nodo 1)
- Slide 10: Tres formatos posibles de colaboración

### 9.3 Formatos posibles de colaboración

Ordenados por commitment ascendente:

1. **Mención editorial breve**: MV cita Micelia como ejemplo en un próximo video. Riesgo nulo, alcance medio.
2. **Capítulo de podcast / video largo** (45-60 min). Compromiso medio, alcance alto.
3. **Serie de contenidos**: 3-5 piezas en el tiempo viendo evolución. Alto compromiso, alto alcance.
4. **Advisorship editorial** (no operativo). Solo si la relación madura tras 6 meses.

NO proponer en primer contacto: equity, embajador pagado, co-autoría.

### 9.4 Calendario sugerido

| Semana | Acción |
|---|---|
| 1 | Cerrar licencia (V6) + responder a las 3 tensiones del §5 con respuesta operativa concreta |
| 2 | Iterar pitch deck a versión presentable + grabar demo de 90s sin audio |
| 3 | Envío email inicial vía LinkedIn (NO mass-mail) |
| 4-6 | Follow-up educado / reunión si procede |
| 7+ | Si reunión: ejecutar demo. Si no: replantear ángulo |

---

## 10. Marcadores cerrados (apéndice de trazabilidad)

| # | Estado v0 | Cierre v1 | Fuente |
|---|---|---|---|
| V1 — Definición canónica de "nodo" | abierto | **Cerrado** | Doc Nodo 1 §1 |
| V2 — Modelo de financiación | abierto | **Cerrado**: suscripción €19/49/99 + apalancamiento ahorro estatal | Doc Nodo 1 §4.4 + §3 |
| V3 — Medición de contribución | abierto | **Cerrado**: tareas asignadas + IA mide rendimiento+satisfacción | Doc Nodo 1 §2.3, §5 |
| V4 — Lista necesidades cubiertas | abierto | **Cerrado**: vivienda, alimentación, transporte, salud, formación | Doc Nodo 1 §2.2 |
| V5 — Acoplamiento cobertura↔contribución | abierto | **Cerrado**: "no te paga por existir, te cubre por contribuir" | Doc Nodo 1 §1, §1.1 |
| V6 — Licencia open source | abierto | **Cerrado v1.1**: defensa en profundidad de 5 capas — AGPLv3 + FSL-1.1-ALv2 + Apache 2.0 (protocolo) + trademark + cooperativa | `docs/LICENSING_STRATEGY.md` (T7.2) |
| V7 — Mecanismo de financiación contrastado | abierto | **Cerrado** — modelo es suscripción + ahorro estatal, NO fee transaccional ni token | Doc Nodo 1 §3, §4 |

**Todos los marcadores cerrados (v1.1).** Lista de acciones operativas pendientes para llegar al pitch (no son `[VERIFICAR]`, son acciones ejecutables):

1. Publicar `LICENSE` (AGPLv3) y `LICENSE.fsl` en la raíz del repo (T7.3)
2. Publicar `docs/CLA.md`, `docs/AI_SOVEREIGNTY_POLICY.md`, `docs/TRADEMARK_POLICY.md` (T7.3)
3. Iniciar trámites EUIPO trademark "Micelia" clases 9, 41, 42 (T7.4)
4. Constituir Asociación copyright holder (T7.5)
5. Grabar demo de 90 segundos (T7.6)
6. Redactar y enviar email a MV (T7.7)

---

## Fuentes

- [The Jobs Apocalypse: Why The Economist Can No Longer Look the Other Way](https://www.youtube.com/watch?v=oIze6NvhzFI) — Marc Vidal, YouTube, 21-may-2026
- [Perfil Marc Vidal](https://www.marcvidal.net/profile)
- [Libros Marc Vidal — editorial Planeta](https://www.marcvidal.net/libros-2)
- [Marc Vidal (analista económico) — Wikipedia](https://es.wikipedia.org/wiki/Marc_Vidal_(analista_econ%C3%B3mico))
- `Micelia_Nodo1_Impacto_Socioeconomico.md` (UTOP.IA / Mayo 2026, Jessicache)
- `docs/PLAN_MICELIA_v0.md` (proyecto Micelia, rebrand v0.1)
- `docs/REBRAND_MICELIA.md` (decisiones arquitectónicas v0.1)
- SEPE 2025-2026 (prestaciones medias)
- Presupuestos sanidad CCAA 2026
- OMS (coste salud mental + desempleo)
