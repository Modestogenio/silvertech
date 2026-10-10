-- ==============================================================================
-- SilverTech Chile: Esquema de Base de Datos y Motor de Triage Gerontológico
-- Migración: 20261010000000_init_silvertech_schema.sql
-- ==============================================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 1. Tabla: Perfiles de Adultos Mayores (elderly_profiles)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.elderly_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    rut VARCHAR(12) NOT NULL UNIQUE, -- Formato chileno: 12.345.678-9 o 12345678-9
    full_name TEXT NOT NULL,
    birth_date DATE,
    address TEXT NOT NULL,
    comuna TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'Región Metropolitana',
    phone_local TEXT,
    medical_notes JSONB NOT NULL DEFAULT '{
        "allergies": [],
        "chronic_diseases": [],
        "blood_type": "Desconocido",
        "has_pacemaker": false,
        "mobility_limitations": []
    }'::jsonb,
    ble_device_mac VARCHAR(17), -- Dirección MAC del botón SOS BLE asignado
    tablet_device_token TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_elderly_rut ON public.elderly_profiles(rut);
CREATE INDEX IF NOT EXISTS idx_elderly_ble_mac ON public.elderly_profiles(ble_device_mac);

-- ------------------------------------------------------------------------------
-- 2. Tabla: Contactos de Emergencia Jerárquicos (emergency_contacts)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.emergency_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elderly_id UUID NOT NULL REFERENCES public.elderly_profiles(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    relation TEXT NOT NULL, -- Ej: "Hijo mayor", "Hija", "Vecina cuidadora"
    phone_e164 VARCHAR(15) NOT NULL, -- Formato E.164: +569XXXXXXXX
    priority_order SMALLINT NOT NULL CHECK (priority_order BETWEEN 1 AND 5),
    receive_whatsapp BOOLEAN NOT NULL DEFAULT TRUE,
    receive_phone_call BOOLEAN NOT NULL DEFAULT TRUE,
    drop_in_authorized BOOLEAN NOT NULL DEFAULT FALSE, -- Autorizado para auto-respuesta de video
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(elderly_id, priority_order)
);

CREATE INDEX IF NOT EXISTS idx_contacts_elderly_priority ON public.emergency_contacts(elderly_id, priority_order);

-- ------------------------------------------------------------------------------
-- 3. Tabla: Horarios y Fármacos (medication_schedules)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.medication_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elderly_id UUID NOT NULL REFERENCES public.elderly_profiles(id) ON DELETE CASCADE,
    medication_name TEXT NOT NULL,
    dosage_instructions TEXT NOT NULL, -- Ej: "1 comprimido con agua después de desayuno"
    scheduled_time TIME NOT NULL, -- Hora local Chile (HH:MM:SS)
    days_of_week SMALLINT[] NOT NULL DEFAULT '{1,2,3,4,5,6,7}', -- 1=Lunes, 7=Domingo
    pill_image_url TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_medication_elderly_time ON public.medication_schedules(elderly_id, scheduled_time);

-- ------------------------------------------------------------------------------
-- 4. Tabla: Registro Diario de Tomas de Medicamentos (medication_logs)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.medication_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schedule_id UUID NOT NULL REFERENCES public.medication_schedules(id) ON DELETE CASCADE,
    elderly_id UUID NOT NULL REFERENCES public.elderly_profiles(id) ON DELETE CASCADE,
    scheduled_date DATE NOT NULL DEFAULT CURRENT_DATE,
    scheduled_time TIME NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('PENDING', 'TAKEN', 'MISSED', 'ESCALATED')) DEFAULT 'PENDING',
    confirmed_at TIMESTAMPTZ,
    confirmation_method VARCHAR(20) CHECK (confirmation_method IN ('SCREEN_TOUCH', 'BLE_BUTTON', 'MANUAL_CAREGIVER')),
    escalated_to_family_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    UNIQUE(schedule_id, scheduled_date)
);

CREATE INDEX IF NOT EXISTS idx_med_logs_date_status ON public.medication_logs(scheduled_date, status);

-- ------------------------------------------------------------------------------
-- 5. Tabla: Registro de Eventos de Emergencia y Triage (emergency_events)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.emergency_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    elderly_id UUID NOT NULL REFERENCES public.elderly_profiles(id) ON DELETE CASCADE,
    event_type VARCHAR(30) NOT NULL CHECK (event_type IN (
        'SOS_BLE_LONG_PRESS',
        'SOS_BLE_SHORT_PRESS',
        'SOS_SCREEN_TAP',
        'FALL_DETECTED',
        'MEDICATION_MISSED_TIMEOUT',
        'DEVICE_OFFLINE_ALARM'
    )),
    triage_level VARCHAR(30) NOT NULL CHECK (triage_level IN (
        'CRITICAL_MEDICAL_131', -- Requiere SAMU / Despacho médico de urgencia
        'POLICE_SECURITY_133',  -- Requiere Carabineros / Seguridad
        'FAMILY_ASSISTANCE_T2'  -- Asistencia familiar no crítica
    )),
    status VARCHAR(30) NOT NULL CHECK (status IN (
        'TRIGGERED',
        'NOTIFYING_FAMILY',
        'FAMILY_ACKNOWLEDGED',
        'EMERGENCY_DESPATCH_REQUESTED',
        'RESOLVED',
        'FALSE_ALARM'
    )) DEFAULT 'TRIGGERED',
    telemetry_payload JSONB NOT NULL DEFAULT '{}'::jsonb, -- Contiene batería del botón, RSSI BLE, coordenadas
    dispatch_logs JSONB NOT NULL DEFAULT '[]'::jsonb,      -- Auditoría de llamadas y mensajes emitidos
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_emergency_status ON public.emergency_events(status, triage_level);
CREATE INDEX IF NOT EXISTS idx_emergency_elderly ON public.emergency_events(elderly_id, created_at DESC);

-- ------------------------------------------------------------------------------
-- 6. Tabla: Macros de Televisión / Domótica Infrarroja (tv_infrared_macros)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tv_infrared_macros (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    elderly_id UUID NOT NULL REFERENCES public.elderly_profiles(id) ON DELETE CASCADE,
    macro_name TEXT NOT NULL, -- Ej: "NOTICIAS_CHILE_13", "APAGAR_TV", "VOLUMEN_UP"
    button_label TEXT NOT NULL, -- Ej: "Ver Noticias", "Apagar TV"
    display_order SMALLINT NOT NULL DEFAULT 1,
    ir_command_sequence JSONB NOT NULL, -- Array ordenado de comandos con delays
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- ------------------------------------------------------------------------------
-- 7. Funciones de Auditoría y Triggers
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_elderly_updated_at ON public.elderly_profiles;
CREATE TRIGGER set_elderly_updated_at
BEFORE UPDATE ON public.elderly_profiles
FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- Comentarios explicativos de integridad
COMMENT ON TABLE public.emergency_events IS 'Historial inmutable de eventos críticos de pánico y decisiones del motor de triage';
COMMENT ON COLUMN public.emergency_events.triage_level IS 'Nivel de triage asignado automáticamente: CRITICAL_MEDICAL_131, POLICE_SECURITY_133, FAMILY_ASSISTANCE_T2';
