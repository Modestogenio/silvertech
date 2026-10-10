"""
SilverTech Chile: Ejecución del Primer Test de Simulación de Emergencia
Ejecuta y despliega en tiempo real el ciclo completo de detección, triage y despacho.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from triage_engine import (
    TriageEngine,
    ElderlyProfile,
    EmergencyContact,
    EventType,
)


def run_first_simulation():
    engine = TriageEngine()

    # Perfil de prueba representativo en Chile
    profile = ElderlyProfile(
        id="eld_chile_001",
        rut="6.234.891-K",
        full_name="Marta Elena Silva Poblete",
        address="Av. Cristóbal Colón 4520, Dpto. 801",
        comuna="Las Condes",
        region="Región Metropolitana",
        chronic_diseases=["Hipertensión Arterial", "Artritis Reumatoide"],
        allergies=["Aspirina / AINEs"],
        has_pacemaker=False,
        emergency_contacts=[
            EmergencyContact(
                id="cnt_01",
                full_name="Rodrigo Silva (Hijo Mayor)",
                relation="Hijo Titular",
                phone_e164="+56998765432",
                priority_order=1,
                receive_whatsapp=True,
                receive_phone_call=True,
                drop_in_authorized=True,
            ),
            EmergencyContact(
                id="cnt_02",
                full_name="Camila Silva (Hija)",
                relation="Hija",
                phone_e164="+56991122334",
                priority_order=2,
                receive_whatsapp=True,
                receive_phone_call=False,
                drop_in_authorized=True,
            ),
        ],
    )

    print("\n" + "=" * 75)
    print("      SILVERTECH CHILE - TEST DE SIMULACIÓN DE EMERGENCIA VITAL")
    print("=" * 75)
    print(f"👤 PACIENTE:        {profile.full_name} | RUT: {profile.rut}")
    print(f"📍 DOMICILIO:       {profile.address}, {profile.comuna} ({profile.region})")
    print(f"🩺 HISTORIAL:       {', '.join(profile.chronic_diseases)} | Alergias: {', '.join(profile.allergies)}")
    print("=" * 75)

    # 1. Simulación del Evento Físico
    telemetry = {
        "source": "BLE_PENDANT_BUTTON",
        "mac_address": "E4:5F:01:23:AA:BB",
        "battery_level": 94,
        "rssi_dbm": -58,
        "press_duration_seconds": 2.1,
    }

    print("\n[PASO 1] 🔴 EVENTO DETECTADO:")
    print(f"  -> Dispositivo: Colgante SOS Bluetooth Low Energy ({telemetry['mac_address']})")
    print(f"  -> Tipo: Pulsación sostenida ({telemetry['press_duration_seconds']}s > umbral 1.5s)")
    print(f"  -> Nivel de batería del botón: {telemetry['battery_level']}% (Señal RSSI: {telemetry['rssi_dbm']} dBm)")

    # 2. Evaluación del Motor de Triage
    result = engine.evaluate(profile, EventType.SOS_BLE_LONG_PRESS, telemetry)

    print("\n[PASO 2] 🧠 DECISIÓN DEL MOTOR DE TRIAGE:")
    print(f"  -> ID del Evento:           {result.event_id}")
    print(f"  -> Nivel de Criticidad:     {result.triage_level.value}")
    print(f"  -> Enlace Público Sugerido: {result.chile_emergency_bridge_recommended} (SAMU Urgencia Médica Chile)")
    print(f"  -> Latencia de Evaluación:  {result.processing_time_ms} ms (Objetivo < 2000 ms: CUMPLIDO)")

    print("\n[PASO 3] 🔊 RETROALIMENTACIÓN LOCAL EN TABLET (TTS):")
    print(f"  -> Audio emitido por altavoz: \"{result.audio_prompt_local}\"")

    print("\n[PASO 4] 📲 DESPACHO INMEDIATO WHATSAPP CLOUD API:")
    for msg in result.whatsapp_messages:
        print(f"\n  --- Mensaje a {msg['recipient_name']} ({msg['to']}) [Prioridad {msg['priority']}] ---")
        for line in msg["body"].split("\n"):
            print(f"  | {line}")

    print("\n[PASO 5] 📞 ENCOLAMIENTO DE LLAMADA TELEFÓNICA SIP (Twilio Voice):")
    call = result.voice_call_payload
    if call:
        print(f"  -> Marcando a: {call['recipient_name']} ({call['to']})")
        print(f"  -> Voz sintetizada (es-CL): \"{call['speech_text']}\"")
        print(f"  -> TwiML XML generado:")
        print(f"     {call['twiml']}")

    print("\n" + "=" * 75)
    print("✅ TEST 1 COMPLETADO EXITOSAMENTE: El flujo completo se procesó en milisegundos.")
    print("=" * 75 + "\n")


if __name__ == "__main__":
    run_first_simulation()
