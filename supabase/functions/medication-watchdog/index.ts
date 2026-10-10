// ==============================================================================
// SilverTech Chile - Edge Function: Medication Watchdog
// Archivo: supabase/functions/medication-watchdog/index.ts
// Runtime: Deno / Supabase Edge Functions
// ==============================================================================

import { serve } from "https://deno.land/std@0.177.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2.39.0";

serve(async (req: Request) => {
  try {
    const supabaseUrl = Deno.env.get("SUPABASE_URL") ?? "";
    const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
    const metaWhatsappToken = Deno.env.get("META_WHATSAPP_TOKEN") ?? "";
    const metaPhoneId = Deno.env.get("META_PHONE_NUMBER_ID") ?? "";

    const supabase = createClient(supabaseUrl, supabaseServiceKey);

    // Obtener los logs pendientes del día
    const todayStr = new Date().toISOString().split("T")[0];
    const { data: pendingLogs, error: logsError } = await supabase
      .from("medication_logs")
      .select(`
        id,
        scheduled_time,
        status,
        elderly_id,
        schedule_id,
        elderly_profiles:elderly_id (
          full_name,
          comuna
        ),
        medication_schedules:schedule_id (
          medication_name,
          dosage_instructions
        )
      `)
      .eq("scheduled_date", todayStr)
      .eq("status", "PENDING");

    if (logsError) {
      throw logsError;
    }

    const escalatedItems = [];
    const now = new Date();
    const currentHours = now.getHours();
    const currentMinutes = now.getMinutes();
    const currentTimeInMinutes = currentHours * 60 + currentMinutes;

    for (const log of (pendingLogs || [])) {
      const [schedH, schedM] = log.scheduled_time.split(":").map(Number);
      const schedTimeInMinutes = schedH * 60 + schedM;
      const elapsedMinutes = currentTimeInMinutes - schedTimeInMinutes;

      // Si han pasado más de 30 minutos sin confirmar la toma
      if (elapsedMinutes >= 30) {
        // 1. Obtener contacto prioritario del adulto mayor
        const { data: contacts } = await supabase
          .from("emergency_contacts")
          .select("full_name, phone_e164")
          .eq("elderly_id", log.elderly_id)
          .eq("priority_order", 1)
          .single();

        const contactPhone = contacts?.phone_e164;
        const elderlyName = (log.elderly_profiles as any)?.full_name || "Adulto Mayor";
        const medName = (log.medication_schedules as any)?.medication_name || "Medicamento prescrito";

        const alertMessage = `⚠️ *ALERTA DE MEDICACIÓN NO CONFIRMADA*\n\n` +
          `Hola ${contacts?.full_name || "Familiar"},\n` +
          `*${elderlyName}* tenía programada la toma de *${medName}* a las *${log.scheduled_time} hrs* y han transcurrido más de 30 minutos sin confirmación en la tablet.\n\n` +
          `Te sugerimos llamar o verificar su estado.`;

        if (contactPhone && metaWhatsappToken && metaPhoneId) {
          await fetch(`https://graph.facebook.com/v19.0/${metaPhoneId}/messages`, {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${metaWhatsappToken}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              messaging_product: "whatsapp",
              to: contactPhone.replace("+", ""),
              type: "text",
              text: { body: alertMessage },
            }),
          });
        }

        // 2. Registrar evento en emergency_events y actualizar log
        await supabase
          .from("medication_logs")
          .update({
            status: "ESCALATED",
            escalated_to_family_at: new Date().toISOString(),
          })
          .eq("id", log.id);

        await supabase
          .from("emergency_events")
          .insert({
            elderly_id: log.elderly_id,
            event_type: "MEDICATION_MISSED_TIMEOUT",
            triage_level: "FAMILY_ASSISTANCE_T2",
            status: "NOTIFYING_FAMILY",
            telemetry_payload: { elapsed_minutes: elapsedMinutes, schedule_id: log.schedule_id },
            dispatch_logs: [{ action: "WHATSAPP_MEDICATION_ALERT", target: contactPhone, timestamp: new Date().toISOString() }],
          });

        escalatedItems.push({
          log_id: log.id,
          elderly_name: elderlyName,
          medication: medName,
          elapsed_minutes: elapsedMinutes,
        });
      }
    }

    return new Response(JSON.stringify({ success: true, escalated_count: escalatedItems.length, items: escalatedItems }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (err: any) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
});
