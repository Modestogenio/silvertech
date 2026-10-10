"""
SilverTech Chile: Motor de Triage y Despacho Automatizado
Módulo Central de Lógica de Negocio y Clasificación de Emergencias.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Optional, Any
import time


class EventType(str, Enum):
    SOS_BLE_LONG_PRESS = "SOS_BLE_LONG_PRESS"     # Botón físico presionado > 1.5s
    SOS_BLE_SHORT_PRESS = "SOS_BLE_SHORT_PRESS"   # Botón físico pulsación rápida
    SOS_SCREEN_TAP = "SOS_SCREEN_TAP"             # Botón rojo gigante en la pantalla
    FALL_DETECTED = "FALL_DETECTED"               # Acelerómetro de colgante o tablet
    MEDICATION_TIMEOUT = "MEDICATION_MISSED_TIMEOUT" # Pastilla no tomada tras 30 min


class TriageLevel(str, Enum):
    CRITICAL_MEDICAL_131 = "CRITICAL_MEDICAL_131"  # Despacho SAMU / Urgencia Vital
    POLICE_SECURITY_133 = "POLICE_SECURITY_133"    # Carabineros / Seguridad Comunal
    FAMILY_ASSISTANCE_T2 = "FAMILY_ASSISTANCE_T2"  # Asistencia Familiar no crítica


@dataclass
class EmergencyContact:
    id: str
    full_name: str
    relation: str
    phone_e164: str  # Ej: +56912345678
    priority_order: int
    receive_whatsapp: bool = True
    receive_phone_call: bool = True
    drop_in_authorized: bool = False


@dataclass
class ElderlyProfile:
    id: str
    rut: str
    full_name: str
    address: str
    comuna: str
    region: str = "Región Metropolitana"
    chronic_diseases: List[str] = field(default_factory=list)
    allergies: List[str] = field(default_factory=list)
    has_pacemaker: bool = False
    emergency_contacts: List[EmergencyContact] = field(default_factory=list)


@dataclass
class TriageResult:
    event_id: str
    elderly_id: str
    event_type: EventType
    triage_level: TriageLevel
    audio_prompt_local: str
    whatsapp_messages: List[Dict[str, Any]]
    voice_call_payload: Optional[Dict[str, Any]]
    chile_emergency_bridge_recommended: Optional[str]
    processing_time_ms: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TriageEngine:
    """Motor de toma de decisiones para teleasistencia gerontológica en Chile."""

    def evaluate(
        self,
        profile: ElderlyProfile,
        event_type: EventType,
        telemetry: Optional[Dict[str, Any]] = None,
    ) -> TriageResult:
        start_time = time.perf_counter()
        event_id = f"evt_{int(time.time() * 1000)}"
        telemetry = telemetry or {}

        # 1. Reglas de Clasificación de Triage
        if event_type in (EventType.SOS_BLE_LONG_PRESS, EventType.SOS_SCREEN_TAP, EventType.FALL_DETECTED):
            triage_level = TriageLevel.CRITICAL_MEDICAL_131
            emergency_bridge = "131" # SAMU Chile
            local_audio = (
                f"Alerta de emergencia activada. Estamos notificando de inmediato a tus familiares "
                f"y preparando enlace con servicios de urgencia médica en {profile.comuna}."
            )
        elif event_type == EventType.SOS_BLE_SHORT_PRESS:
            triage_level = TriageLevel.FAMILY_ASSISTANCE_T2
            emergency_bridge = None
            local_audio = "Aviso de asistencia enviado a tus familiares."
        else: # MEDICATION_TIMEOUT
            triage_level = TriageLevel.FAMILY_ASSISTANCE_T2
            emergency_bridge = None
            local_audio = "Recordatorio de medicamento escalado al cuidador."

        # 2. Generación de Mensajería WhatsApp Cloud API
        sorted_contacts = sorted(profile.emergency_contacts, key=lambda c: c.priority_order)
        whatsapp_messages = []

        diseases_str = ", ".join(profile.chronic_diseases) if profile.chronic_diseases else "Sin antecedentes"
        pacemaker_str = " | ⚠️ Portador de Marcapasos" if profile.has_pacemaker else ""

        for contact in sorted_contacts[:2]: # Prioridad 1 y 2
            if contact.receive_whatsapp:
                wa_body = (
                    f"🚨 *ALERTA SOS SILVERTECH*\n\n"
                    f"Adulto Mayor: *{profile.full_name}* (RUT: {profile.rut})\n"
                    f"Tipo de Evento: *{event_type.value}*\n"
                    f"Nivel de Triage: *{triage_level.value}*\n"
                    f"Dirección: *{profile.address}, {profile.comuna}*\n"
                    f"Ficha Médica: {diseases_str}{pacemaker_str}\n\n"
                    f"📍 Batería Botón: {telemetry.get('battery_level', 'N/A')}%\n"
                    f"Por favor responde a este mensaje o ingresa a la consola para atender la situación."
                )
                whatsapp_messages.append({
                    "to": contact.phone_e164,
                    "recipient_name": contact.full_name,
                    "priority": contact.priority_order,
                    "body": wa_body,
                })

        # 3. Generación de Llamada de Voz (Twilio / SIP)
        voice_payload = None
        primary_contact = sorted_contacts[0] if sorted_contacts else None
        if primary_contact and primary_contact.receive_phone_call and triage_level == TriageLevel.CRITICAL_MEDICAL_131:
            twiml_text = (
                f"Atención urgente de SilverTech. {profile.full_name} ha presionado el botón de pánico "
                f"en su domicilio ubicado en {profile.address}, comuna de {profile.comuna}. "
                f"Presione 1 para conectar con la vivienda o 2 para llamar a la ambulancia."
            )
            voice_payload = {
                "to": primary_contact.phone_e164,
                "recipient_name": primary_contact.full_name,
                "caller_id": "+56940000000",
                "twiml": f"<Response><Say voice='Polly.Lupe' language='es-CL'>{twiml_text}</Say></Response>",
                "speech_text": twiml_text,
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        return TriageResult(
            event_id=event_id,
            elderly_id=profile.id,
            event_type=event_type,
            triage_level=triage_level,
            audio_prompt_local=local_audio,
            whatsapp_messages=whatsapp_messages,
            voice_call_payload=voice_payload,
            chile_emergency_bridge_recommended=emergency_bridge,
            processing_time_ms=round(elapsed_ms, 3),
        )
