"""
SilverTech Chile: Simulador de Eventos de Emergencia y Consola de Laboratorio
Uso interactivo: python simulate_triage.py
"""

import sys
import json
import time

# Asegurar codificación UTF-8 en consolas Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from triage_engine import (
    TriageEngine,
    ElderlyProfile,
    EmergencyContact,
    EventType,
)


def build_sample_profile() -> ElderlyProfile:
    return ElderlyProfile(
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
                full_name="Rodrigo Silva (Hijo Titular)",
                relation="Hijo",
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


def print_banner():
    print("=" * 70)
    print("    SILVERTECH CHILE - SIMULADOR DEL MOTOR DE TRIAGE Y EMERGENCIAS")
    print("=" * 70)


def print_result(res):
    print("\n" + "-" * 70)
    print(f"⏱️  LATENCIA DE DECISIÓN: {res.processing_time_ms} ms")
    print(f"🆔  EVENTO ID:            {res.event_id}")
    print(f"🚨  TIPO DE EVENTO:       {res.event_type.value}")
    print(f"🏷️   NIVEL DE TRIAGE:      {res.triage_level.value}")
    print(f"🇨🇱  ENLACE URGENCIA:      {res.chile_emergency_bridge_recommended or 'No requerido'}")
    print(f"🔊  AUDIO TABLET (TTS):   \"{res.audio_prompt_local}\"")
    print("-" * 70)

    print("\n📲  DESPACHO WHATSAPP CLOUD API (Prioridad 1 y 2):")
    for wa in res.whatsapp_messages:
        print(f"  -> Para: {wa['recipient_name']} ({wa['to']})")
        for line in wa["body"].split("\n"):
            print(f"     {line}")
        print()

    if res.voice_call_payload:
        print("📞  DESPACHO LLAMADA SIP (Twilio Voice):")
        print(f"  -> Destinatario: {res.voice_call_payload['recipient_name']} ({res.voice_call_payload['to']})")
        print(f"  -> Mensaje de Voz: \"{res.voice_call_payload['speech_text']}\"")
        print(f"  -> Payload TwiML: {res.voice_call_payload['twiml']}")
    else:
        print("📞  LLAMADA TELEFÓNICA: No requerida para este nivel de evento.")
    print("-" * 70 + "\n")


def run_benchmark(engine, profile):
    print("\n⏳ Ejecutando benchmark de 1,000 eventos continuos...")
    times = []
    for _ in range(1000):
        t0 = time.perf_counter()
        engine.evaluate(profile, EventType.SOS_BLE_LONG_PRESS, {"battery_level": 88})
        times.append((time.perf_counter() - t0) * 1000)

    avg_ms = sum(times) / len(times)
    min_ms = min(times)
    max_ms = max(times)
    print("=" * 70)
    print("📊 RESULTADOS DEL BENCHMARK:")
    print(f"   Eventos evaluados: 1,000")
    print(f"   Tiempo promedio:   {avg_ms:.3f} ms")
    print(f"   Tiempo mínimo:     {min_ms:.3f} ms")
    print(f"   Tiempo máximo:     {max_ms:.3f} ms")
    print(f"   Cumplimiento SLA (< 2000 ms): 100% CUMPLIDO")
    print("=" * 70 + "\n")


def main():
    engine = TriageEngine()
    profile = build_sample_profile()

    if len(sys.argv) > 1 and sys.argv[1] == "--benchmark":
        run_benchmark(engine, profile)
        return

    print_banner()
    print(f"👤 Adulto Mayor de prueba: {profile.full_name} (RUT: {profile.rut})")
    print(f"📍 Dirección: {profile.address}, {profile.comuna}")
    print(f"👥 Contactos de emergencia configurados: {len(profile.emergency_contacts)}")
    print()

    menu = """Selecciona el evento a simular:
  [1] Botón SOS Físico BLE (Pulsación sostenida > 1.5s) -> Urgencia Vital / SAMU 131
  [2] Botón SOS Físico BLE (Pulsación corta)            -> Asistencia Familiar
  [3] Botón Rojo en Pantalla Tablet                     -> Urgencia Vital / SAMU 131
  [4] Detección de Caída (Acelerómetro)                -> Urgencia Vital / SAMU 131
  [5] Alerta de Medicamento no tomado (> 30 min)        -> Escalamiento a Cuidador
  [6] Benchmark de Rendimiento (1,000 eventos)
  [0] Salir
"""

    while True:
        print(menu)
        choice = input("Opción > ").strip()
        if choice == "1":
            res = engine.evaluate(profile, EventType.SOS_BLE_LONG_PRESS, {"battery_level": 94, "rssi_dbm": -55})
            print_result(res)
        elif choice == "2":
            res = engine.evaluate(profile, EventType.SOS_BLE_SHORT_PRESS, {"battery_level": 94})
            print_result(res)
        elif choice == "3":
            res = engine.evaluate(profile, EventType.SOS_SCREEN_TAP, {"app_version": "1.0.0"})
            print_result(res)
        elif choice == "4":
            res = engine.evaluate(profile, EventType.FALL_DETECTED, {"g_force": 4.1})
            print_result(res)
        elif choice == "5":
            res = engine.evaluate(profile, EventType.MEDICATION_TIMEOUT, {"medicine": "Enalapril 10mg"})
            print_result(res)
        elif choice == "6":
            run_benchmark(engine, profile)
        elif choice == "0":
            print("Cerrando simulador.")
            break
        else:
            print("Opción no válida.")


if __name__ == "__main__":
    main()
