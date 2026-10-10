# SilverTech Chile 🇨🇱
**Sistema de Teleasistencia, Seguridad Proactiva y Domótica Simplificada para la Tercera Edad**

SilverTech es un ecosistema tecnológico diseñado para adultos mayores con alta fricción tecnológica o limitaciones físicas, enfocado en resolver emergencias vitales, adherencia a tratamientos médicos y simplificación de la vida diaria (control de TV por infrarrojos), con soporte y tranquilidad garantizada para sus familiares.

---

## 📁 Estructura del Proyecto

```text
silvertech/
├── supabase/
│   ├── migrations/
│   │   └── 20261010000000_init_silvertech_schema.sql  # DDL PostgreSQL (perfiles, emergencias, fármacos, domótica)
│   └── functions/
│       ├── triage-engine/                             # Edge Function: Clasificación de alertas y despacho WhatsApp/SIP
│       │   └── index.ts
│       └── medication-watchdog/                       # Edge Function: Monitor de tomas y escalamiento tras 30 min
│           └── index.ts
├── simulator/
│   ├── triage_engine.py                               # Motor de reglas y lógica de negocio en Python
│   ├── test_triage_engine.py                          # Suite de tests unitarios automatizados
│   └── simulate_triage.py                             # Consola interactiva y benchmark de eventos SOS
├── .env.example                                       # Plantilla de credenciales y variables de entorno
└── README.md                                          # Este documento
```

---

## 🚀 Inicio Rápido (Fase 1: Laboratorio y Pruebas)

### 1. Ejecutar las Pruebas Unitarias
Para verificar que las reglas de triage clasifican correctamente las emergencias de acuerdo a la normativa chilena:

```bash
cd simulator
python -m unittest test_triage_engine.py
```

### 2. Ejecutar la Consola Interactiva
Permite simular eventos reales de botón SOS, caídas y recordatorios de medicación:

```bash
cd simulator
python simulate_triage.py
```

### 3. Ejecutar el Benchmark de Latencia
Evalúa el tiempo de procesamiento de 1,000 eventos continuos:

```bash
cd simulator
python simulate_triage.py --benchmark
```

*Resultado promedio obtenido:* **~0.012 milisegundos** por evento (cumplimiento SLA < 2,000 ms garantizado).

---

## 🗄️ Despliegue en Supabase

1. Crea un proyecto en [Supabase](https://supabase.com/).
2. Copia y ejecuta el contenido de `supabase/migrations/20261010000000_init_silvertech_schema.sql` en el **SQL Editor** de tu panel de Supabase.
3. Despliega las Edge Functions con el CLI de Supabase:
   ```bash
   supabase functions deploy triage-engine --no-verify-jwt
   supabase functions deploy medication-watchdog --no-verify-jwt
   ```
4. Configura las variables de entorno en el panel de Supabase utilizando los valores de referencia de `.env.example`.

---

## 🛣️ Próximos Pasos (Fase 2)
- Desarrollo del Kiosk Android en Flutter (`silvertech-kiosk`):
  - Interfaz de 4 botones gigantes accesible (WCAG 2.2 AAA).
  - Servicio de escaneo Bluetooth Low Energy (BLE) en primer plano para el botón colgante.
  - Síntesis de voz (TTS) local y modo de pantalla fija (`LockTaskMode`).
