// ==============================================================================
// SilverTech Chile - Edge Function: Triage Engine
// Archivo: supabase/functions/triage-engine/index.ts
// Runtime: Deno / Supabase Edge Functions
// ==============================================================================

import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

interface TriagePayload {
  elderly_id: string;
  event_type: "SOS_BLE_LONG_PRESS" | "SOS_BLE_SHORT_PRESS" | "SOS_SCREEN_TAP" | "FALL_DETECTED" | "MEDICATION_MISSED_TIMEOUT";
  telemetry: {
    battery_level?: number;
    rssi_dbm?: number;
    latitude?: number;
    longitude?: number;
    trigger_timestamp: string;
  };
}

interface EmergencyContact {
  id: string;
  full_name: string;
  relation: string;
  phone_e164: string;
  priority_order: number;
  receive_whatsapp: boolean;
  receive_phone_call: boolean;
  drop_in_authorized: boolean;
}

serve(async (req: Request) => {
  const startTime = Date.now();

  if (req.method !== "POST") {
    return new Response(JSON.stringify({ error: "Method not allowed. Use POST." }), {
      status: 405,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const twilioAccountSid = Deno.env.get("TWILIO_ACCOUNT_SID") ?? "";
    const twilioAuthToken = Deno.env.get("TWILIO_AUTH_TOKEN") ?? "";
    const twilioCallerNumber = Deno.env.get("TWILIO_CALLER_NUMBER") ?? "+56911112222";
    const metaWhatsappToken = Deno.env.get("META_WHATSAPP_TOKEN") ?? "";
    const metaPhoneId = Deno.env.get("META_PHONE_NUMBER_ID") ?? "";

    const supabase = createClient(supabaseUrl, supabaseServiceKey);
    const body: TriagePayload = await req.json();

    const { elderly_id, event_type, telemetry } = body;

    if (!elderly_id || !event_type) {
      return new Response(JSON.stringify({ error: "Missing required parameters: elderly_id, event_type" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 1. Obtener perfil del adulto mayor
    const { data: profile, error: profileError } = await supabase
      .from("elderly_profiles")
      .select("id, full_name, rut, address, comuna, region, medical_notes")
      .eq("id", elderly_id)
      .single();

    if (profileError || !profile) {
      return new Response(JSON.stringify({ error: "Elderly profile not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      });
    }

    // 2. Obtener contactos de emergencia ordenados por prioridad
    const { data: contacts, error: contactsError } = await supabase
      .from("emergency_contacts")
      .select("*")
      .eq("elderly_id", elderly_id)
      .order("priority_order", { ascending: true });

    const emergencyContacts: EmergencyContact[] = contacts || [];

    // 3. Reglas de Triage
    let triageLevel: "CRITICAL_MEDICAL_131" | "POLICE_SECURITY_133" | "FAMILY_ASSISTANCE_T2";

    switch (event_type) {
      case "SOS_BLE_LONG_PRESS":
      case "SOS_SCREEN_TAP":
      case "FALL_DETECTED":
        // Presión sostenida de botón o caída -> Urgencia vital / médica
        triageLevel = "CRITICAL_MEDICAL_131";
        break;
      case "SOS_BLE_SHORT_PRESS":
        // Presión corta -> Asistencia general / chequeo
        triageLevel = "FAMILY_ASSISTANCE_T2";
        break;
      case "MEDICATION_MISSED_TIMEOUT":
      default:
        triageLevel = "FAMILY_ASSISTANCE_T2";
        break;
    }

    const dispatchLogs: Array<{ action: string; target: string; status: string; timestamp: string; detail?: string }> = [];

    // 4. Crear evento en emergency_events
    const { data: eventRecord, error: eventError } = await supabase
      .from("emergency_events")
      .insert({
        elderly_id,
        event_type,
        triage_level: triageLevel,
        status: "NOTIFYING_FAMILY",
        telemetry_payload: telemetry,
        dispatch_logs: [],
      })
      .select("id")
      .single();

    const eventId = eventRecord?.id;

    // 5. Notificación por WhatsApp Cloud API (Contactos prioridad 1 y 2)
    const priorityContacts = emergencyContacts.slice(0, 2);
    for (const contact of priorityContacts) {
      if (contact.receive_whatsapp) {
        const diseases = Array.isArray(profile.medical_notes?.chronic_diseases) 
          ? profile.medical_notes.chronic_diseases.join(", ") 
          : "Sin registro específico";

        const textMessage = `🚨 *ALERTA SILVERTECH SOS*\n\n` +
          `Adulto Mayor: *${profile.full_name}*\n` +
          `Evento: *${event_type}* (${triageLevel})\n` +
          `Dirección: *${profile.address}, ${profile.comuna}*\n` +
          `Ficha Médica: ${diseases}\n\n` +
          `Por favor confirma recepción o ingresa a la consola para coordinar asistencia.`;

        // Llamada a Meta Graph API si los tokens están configurados
        if (metaWhatsappToken && metaPhoneId) {
          try {
            const waRes = await fetch(`https://graph.facebook.com/v19.0/${metaPhoneId}/messages`, {
              method: "POST",
              headers: {
                "Authorization": `Bearer ${metaWhatsappToken}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                messaging_product: "whatsapp",
                to: contact.phone_e164.replace("+", ""),
                type: "text",
                text: { body: textMessage },
              }),
            });
            dispatchLogs.push({
              action: "WHATSAPP_CLOUD_API",
              target: contact.phone_e164,
              status: waRes.ok ? "DELIVERED" : "FAILED",
              timestamp: new Date().toISOString(),
            });
          } catch (err: any) {
            dispatchLogs.push({
              action: "WHATSAPP_CLOUD_API",
              target: contact.phone_e164,
              status: "ERROR",
              timestamp: new Date().toISOString(),
              detail: err.message,
            });
          }
        } else {
          // Log en modo simulación
          dispatchLogs.push({
            action: "WHATSAPP_SIMULATED",
            target: contact.phone_e164,
            status: "SIMULATED_SUCCESS",
            timestamp: new Date().toISOString(),
            detail: textMessage,
          });
        }
      }
    }

    // 6. Despacho de Llamada Telefónica Automatizada (Twilio Voice) al Contacto Prioridad 1
    const primaryContact = emergencyContacts[0];
    if (primaryContact && primaryContact.receive_phone_call && triageLevel === "CRITICAL_MEDICAL_131") {
      const twimlVoiceMessage = `<Response><Say voice="Polly.Lupe" language="es-CL">Atención. Alerta de emergencia de SilverTech. ${profile.full_name} ha presionado el botón de pánico en su domicilio en ${profile.comuna}. Por favor contacte de inmediato.</Say></Response>`;

      if (twilioAccountSid && twilioAuthToken) {
        try {
          const authString = btoa(`${twilioAccountSid}:${twilioAuthToken}`);
          const params = new URLSearchParams();
          params.append("To", primaryContact.phone_e164);
          params.append("From", twilioCallerNumber);
          params.append("Twiml", twimlVoiceMessage);

          const callRes = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${twilioAccountSid}/Calls.json`, {
            method: "POST",
            headers: {
              "Authorization": `Basic ${authString}`,
              "Content-Type": "application/x-www-form-urlencoded",
            },
            body: params.toString(),
          });

          dispatchLogs.push({
            action: "TWILIO_VOICE_CALL",
            target: primaryContact.phone_e164,
            status: callRes.ok ? "QUEUED" : "FAILED",
            timestamp: new Date().toISOString(),
          });
        } catch (err: any) {
          dispatchLogs.push({
            action: "TWILIO_VOICE_CALL",
            target: primaryContact.phone_e164,
            status: "ERROR",
            timestamp: new Date().toISOString(),
            detail: err.message,
          });
        }
      } else {
        dispatchLogs.push({
          action: "TWILIO_VOICE_SIMULATED",
          target: primaryContact.phone_e164,
          status: "SIMULATED_SUCCESS",
          timestamp: new Date().toISOString(),
          detail: twimlVoiceMessage,
        });
      }
    }

    // 7. Actualizar el log de despacho en PostgreSQL
    if (eventId) {
      await supabase
        .from("emergency_events")
        .update({ dispatch_logs: dispatchLogs })
        .eq("id", eventId);
    }

    const executionMs = Date.now() - startTime;

    return new Response(
      JSON.stringify({
        success: true,
        event_id: eventId,
        triage_level: triageLevel,
        execution_time_ms: executionMs,
        dispatches_executed: dispatchLogs.length,
        dispatch_logs: dispatchLogs,
      }),
      {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }
    );
  } catch (error: any) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
