# START HERE — DAILY-OPS

> **Instrucciones para Claude Code. Lee esto primero, luego lee `CLAUDE.md` completo.**

## Tu misión
Construir **DAILY-OPS**: app web que unifica Revenue diario, Revenue semanal, Posición de efectivo y Auditoría diaria de ingresos para SCP Corcovado Wilderness Lodge (`COWLCR`). Bismark ya definió TODA la lógica. Tu trabajo es convertirla en software funcional, validado contra los Excel actuales.

## Contexto completo
**Lee `CLAUDE.md`** — contiene el spec técnico completo: modelo de datos, reglas de negocio (el motor), bugs a corregir, seed, orden de construcción y criterios de validación.

## Archivos de referencia disponibles
```
CLAUDE.md                          ← spec técnico completo (LEE PRIMERO)
PLANTEAMIENTO_DAILY_OPS.md         ← contexto largo y detalle fino (consulta)
BITACORA_INSUMOS_AUDITORIA.md      ← contrato de ingesta (qué archivo es qué)
auditoria.py                       ← reconciliación + parsers XML/POS (portar casi directo)
/goldens/                          ← Excels actuales como fixtures de validación:
   DAILY_REV_REP_AS_OF_DAY_31.xlsm         (Summary, Room Statistics)
   WEEKLY_REVENUE_REPORT_MASTER_FILE.xlsx  (Weekly / YTD)
   DAILY_CASH_POSITION_MASTER_FILE.xlsx    (Flash/Recon/Bank/Brand)
   + set de auditoría del 2026-06-09 (Integrity, Opera XMLs, POS, Trial)
```

## Reglas de oro
1. **Absorbe los Excel, no los reinventes:** cada vista debe reproducir su golden a **tolerancia $0.01**. Ese es el criterio de "done".
2. **Construye en orden** (CLAUDE.md §9), una etapa a la vez. Corre los tests después de cada módulo.
3. **No decidas reglas de negocio.** Si algo falta (ej. default del gate), déjalo configurable con default y marca `TODO(bismark:)`.
4. **No repliques los bugs del Excel** (CLAUDE.md §6): calendario semanal roto, fecha hardcodeada, fallback a "Sustainability Fee", fecha desde filename, consultas duplicadas.
5. `business_date` viene del batch, nunca del filename. UNMAPPED y ELSE = excepciones visibles, nunca descartes en silencio.
6. **Modelo por fase** (CLAUDE.md §0.1): `/model sonnet` para scaffold, frontend y CRUD; `/model opus` para ingesta, revenue, cash, auditoría, room stats y gate. Si un test golden falla o Sonnet se traba → escalá a Opus.
7. **Feedback en procesos largos** (CLAUDE.md §0.2): trabajá por checkpoints (uno por módulo); si una tarea pasa de ~5 min, antes del siguiente módulo re-leé el chat y aplicá de inmediato lo relevante (`NOTA(bismark:)` lo que no lo sea). Nunca ignores un mensaje en silencio.

## Cómo empezar (en orden)
```bash
# 0. Scaffold: repo + Postgres (daily_ops) + migraciones + seed + goldens
# 1. Ingesta Integrity  → stg_integrity_line   (test: conteo + sumas)
# 2. Revenue daily/weekly → validar Summary / Weekly
# 3. Cash               → validar Flash/Recon/Bank/Brand
# 4. Auditoría (portar auditoria.py) → audit_run + audit_finding
# 5. Room stats + ADR/Occ/Yield → validar Room Statistics
# 6. Frontend: dashboard + selector de día + tabs + botón REFRESH
# 7. Hallazgos (workflow 2.10)
# 8. Orquestación: batch por día → corre todo → gate → export
```

## Primera instrucción sugerida
> "Lee `START_HERE.md` y `CLAUDE.md` completos. Ejecuta la etapa 0 (scaffold + migraciones + seed) y la etapa 1 (ingesta Integrity con su test). No escribas código de negocio hasta confirmar que leíste el spec. Corre los tests después de cada módulo y corrige antes de continuar. No pares hasta que todos los módulos estén completos y los tests en verde."

---

*Todo lo que necesitás para construir está aquí y en CLAUDE.md. Construí, validá contra los goldens, entregá.*
