-- =============================================================================
-- IDM-CORE: Inicialización de Base de Datos
-- =============================================================================
-- Este script se ejecuta automáticamente al iniciar PostgreSQL por primera vez
-- via docker-entrypoint-initdb.d

-- Crear bases de datos para cada servicio
CREATE DATABASE biohack;
CREATE DATABASE ideacursi;
CREATE DATABASE canela;

-- Conceder privilegios al usuario idm sobre las bases de datos satélite
GRANT ALL PRIVILEGES ON DATABASE biohack TO idm;
GRANT ALL PRIVILEGES ON DATABASE ideacursi TO idm;
GRANT ALL PRIVILEGES ON DATABASE canela TO idm;

-- Habilitar extensiones en bases de datos satélite
\c biohack;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO idm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO idm;

\c ideacursi;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO idm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO idm;

\c canela;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO idm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO idm;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO idm;

-- Volver a idm_core para crear las tablas del Event Store
\c idm_core;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- TABLA: idm_events (Event Store)
-- =============================================================================
-- Nota: SQLAlchemy también puede crear esta tabla, pero la definimos aquí
-- para tener índices optimizados desde el inicio

CREATE TABLE IF NOT EXISTS idm_events (
    -- Identificación
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id UUID,
    causation_id UUID,

    -- Temporal
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    occurred_at TIMESTAMPTZ,
    processed_at TIMESTAMPTZ,

    -- Clasificación
    category VARCHAR(50) NOT NULL,
    subcategory VARCHAR(50),
    source VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,

    -- Actor
    user_id UUID,
    device_id VARCHAR(100),
    session_id UUID,

    -- Contenido
    payload JSONB DEFAULT '{}',
    event_metadata JSONB DEFAULT '{}',

    -- Cómputo
    compute_provider VARCHAR(50),
    compute_model VARCHAR(100),
    compute_latency_ms FLOAT,
    compute_cost_usd FLOAT,
    energy_cost_kwh FLOAT,

    -- Versionado
    version INTEGER DEFAULT 1,
    schema_version VARCHAR(20) DEFAULT '1.0.0',
    tags JSONB DEFAULT '[]'
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS ix_events_timestamp ON idm_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_events_category ON idm_events(category);
CREATE INDEX IF NOT EXISTS ix_events_source ON idm_events(source);
CREATE INDEX IF NOT EXISTS ix_events_event_type ON idm_events(event_type);
CREATE INDEX IF NOT EXISTS ix_events_user_id ON idm_events(user_id);
CREATE INDEX IF NOT EXISTS ix_events_correlation_id ON idm_events(correlation_id);

-- Índices compuestos
CREATE INDEX IF NOT EXISTS ix_events_user_category_time
    ON idm_events(user_id, category, timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_events_source_type
    ON idm_events(source, event_type);
CREATE INDEX IF NOT EXISTS ix_events_correlation_time
    ON idm_events(correlation_id, timestamp);

-- Índices GIN para búsqueda en JSONB
CREATE INDEX IF NOT EXISTS ix_events_payload_gin
    ON idm_events USING GIN (payload);
CREATE INDEX IF NOT EXISTS ix_events_tags_gin
    ON idm_events USING GIN (tags);

-- =============================================================================
-- TABLA: service_status (Service Registry)
-- =============================================================================

CREATE TABLE IF NOT EXISTS service_status (
    service_name VARCHAR(50) PRIMARY KEY,
    url VARCHAR(255) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    healthy BOOLEAN DEFAULT false,
    last_check TIMESTAMPTZ,
    latency_ms FLOAT,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insertar servicios conocidos
INSERT INTO service_status (service_name, url, enabled) VALUES
    ('health', 'http://biohack-app:8080', true),
    ('research', 'http://canela-molida:3690', true),
    ('education', 'http://ideacursi-backend:5050', true),
    ('security', 'http://cybertools:8000', true)
ON CONFLICT (service_name) DO NOTHING;

-- =============================================================================
-- TABLA: energy_readings (Historial de Energía)
-- =============================================================================

CREATE TABLE IF NOT EXISTS energy_readings (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    battery_level INTEGER,
    is_charging BOOLEAN,
    power_source VARCHAR(50),
    time_remaining_minutes INTEGER,
    solar_watts FLOAT,
    energy_state VARCHAR(20),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_energy_timestamp
    ON energy_readings(timestamp DESC);

-- =============================================================================
-- TABLA: compute_usage (Uso de Cómputo)
-- =============================================================================

CREATE TABLE IF NOT EXISTS compute_usage (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100),
    operation VARCHAR(50),
    tokens_input INTEGER,
    tokens_output INTEGER,
    latency_ms FLOAT,
    cost_usd FLOAT,
    energy_kwh FLOAT,
    success BOOLEAN DEFAULT true,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ix_compute_timestamp
    ON compute_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS ix_compute_provider
    ON compute_usage(provider);

-- =============================================================================
-- FUNCIONES
-- =============================================================================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger para service_status
DROP TRIGGER IF EXISTS update_service_status_updated_at ON service_status;
CREATE TRIGGER update_service_status_updated_at
    BEFORE UPDATE ON service_status
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VISTAS
-- =============================================================================

-- Vista de eventos recientes por categoría
CREATE OR REPLACE VIEW recent_events_by_category AS
SELECT
    category,
    COUNT(*) as event_count,
    MAX(timestamp) as last_event,
    array_agg(DISTINCT source) as sources
FROM idm_events
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY category
ORDER BY event_count DESC;

-- Vista de uso de cómputo por día
CREATE OR REPLACE VIEW daily_compute_usage AS
SELECT
    DATE(timestamp) as date,
    provider,
    COUNT(*) as requests,
    SUM(tokens_input + COALESCE(tokens_output, 0)) as total_tokens,
    AVG(latency_ms) as avg_latency,
    SUM(COALESCE(cost_usd, 0)) as total_cost
FROM compute_usage
GROUP BY DATE(timestamp), provider
ORDER BY date DESC, provider;

-- =============================================================================
-- PERMISOS
-- =============================================================================

-- Dar permisos al usuario idm sobre todas las tablas
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO idm;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO idm;

-- =============================================================================
-- DATOS INICIALES
-- =============================================================================

-- Evento de sistema: inicialización
INSERT INTO idm_events (
    category, source, action, event_type, payload
) VALUES (
    'system', 'micelia', 'create', 'system.initialized',
    '{"message": "Micelia database initialized", "version": "1.0.0"}'::jsonb
);

-- Mensaje de confirmación
DO $$
BEGIN
    RAISE NOTICE '===========================================';
    RAISE NOTICE 'Micelia: Base de datos inicializada';
    RAISE NOTICE 'Tablas creadas: idm_events, service_status,';
    RAISE NOTICE '               energy_readings, compute_usage';
    RAISE NOTICE '===========================================';
END $$;
