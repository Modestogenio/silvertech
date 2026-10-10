"""
Tests automatizados para el Motor de Triage de SilverTech Chile.
Ejecución: python -m unittest test_triage_engine.py
"""

import unittest
from triage_engine import (
    TriageEngine,
    ElderlyProfile,
    EmergencyContact,
    EventType,
    TriageLevel,
)


class TestSilverTechTriageEngine(unittest.TestCase):
    def setUp(self):
        self.engine = TriageEngine()
        self.mock_contact_1 = EmergencyContact(
            id="c1",
            full_name="Carlos Soto (Hijo)",
            relation="Hijo Mayor",
            phone_e164="+56991234567",
            priority_order=1,
            receive_whatsapp=True,
            receive_phone_call=True,
            drop_in_authorized=True,
        )
        self.mock_contact_2 = EmergencyContact(
            id="c2",
            full_name="Valentina Soto (Hija)",
            relation="Hija",
            phone_e164="+56998765432",
            priority_order=2,
            receive_whatsapp=True,
            receive_phone_call=False,
            drop_in_authorized=True,
        )
        self.mock_profile = ElderlyProfile(
            id="eld_001",
            rut="5.432.109-8",
            full_name="Don Juan Soto Morales",
            address="Av. Las Condes 1234, Depto 402",
            comuna="Las Condes",
            chronic_diseases=["Hipertensión Arterial", "Diabetes Tipo 2"],
            allergies=["Penicilina"],
            has_pacemaker=True,
            emergency_contacts=[self.mock_contact_1, self.mock_contact_2],
        )

    def test_sos_long_press_triggers_critical_triage(self):
        result = self.engine.evaluate(
            self.mock_profile,
            EventType.SOS_BLE_LONG_PRESS,
            {"battery_level": 92, "rssi_dbm": -64},
        )

        self.assertEqual(result.triage_level, TriageLevel.CRITICAL_MEDICAL_131)
        self.assertEqual(result.chile_emergency_bridge_recommended, "131")
        self.assertIsNotNone(result.voice_call_payload)
        self.assertEqual(result.voice_call_payload["to"], "+56991234567")
        self.assertIn("Don Juan Soto Morales", result.voice_call_payload["speech_text"])
        self.assertIn("Las Condes", result.voice_call_payload["speech_text"])

        # Verificar mensajes a los dos contactos
        self.assertEqual(len(result.whatsapp_messages), 2)
        self.assertIn("CRITICAL_MEDICAL_131", result.whatsapp_messages[0]["body"])
        self.assertIn("Portador de Marcapasos", result.whatsapp_messages[0]["body"])
        self.assertIn("Hipertensión Arterial", result.whatsapp_messages[0]["body"])

        # Latencia menor a 50ms
        self.assertLess(result.processing_time_ms, 50.0)

    def test_sos_short_press_triggers_family_assistance_only(self):
        result = self.engine.evaluate(
            self.mock_profile,
            EventType.SOS_BLE_SHORT_PRESS,
            {"battery_level": 92},
        )

        self.assertEqual(result.triage_level, TriageLevel.FAMILY_ASSISTANCE_T2)
        self.assertIsNone(result.chile_emergency_bridge_recommended)
        self.assertIsNone(result.voice_call_payload) # No llama por teléfono en asistencia simple
        self.assertEqual(len(result.whatsapp_messages), 2)
        self.assertIn("FAMILY_ASSISTANCE_T2", result.whatsapp_messages[0]["body"])

    def test_fall_detection_escalates_to_medical(self):
        result = self.engine.evaluate(
            self.mock_profile,
            EventType.FALL_DETECTED,
            {"accelerometer_g_peak": 3.8},
        )

        self.assertEqual(result.triage_level, TriageLevel.CRITICAL_MEDICAL_131)
        self.assertEqual(result.chile_emergency_bridge_recommended, "131")
        self.assertIsNotNone(result.voice_call_payload)

    def test_medication_timeout_triggers_family_escalation(self):
        result = self.engine.evaluate(
            self.mock_profile,
            EventType.MEDICATION_TIMEOUT,
            {"schedule_name": "Losartán 50mg", "delay_min": 35},
        )

        self.assertEqual(result.triage_level, TriageLevel.FAMILY_ASSISTANCE_T2)
        self.assertIsNone(result.voice_call_payload)
        self.assertGreaterEqual(len(result.whatsapp_messages), 1)


if __name__ == "__main__":
    unittest.main()
