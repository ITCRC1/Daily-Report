"""Backfill quirúrgico del snapshot OTB de un día (solo fact_otb / _monthly /
_daily), SIN tocar el resto de los datos del día.

Para días cuyos crudos ya no están en el volumen (ej. 2026-07-01/02, subidos
antes de que el server persistiera los inputs) pero el owner re-provee los 2
`history_forecast` (Total + Rooms Only). Replica ingest_service.py 301-336.

Uso (apuntando a prod vía el proxy público):
  PYTHONPATH=backend DATABASE_URL="postgresql+asyncpg://.../railway" \
  backend/.venv/Scripts/python.exe scripts/otb_backfill.py 2026-07-02 \
  ruta/OPERA_HistoryForecast_Default_2026-07-02.XML \
  ruta/OPERA_HistoryForecast_TotalRevenue_2026-07-02.XML

El parser auto-detecta cuál es Total vs Rooms Only por el monto (no por el
nombre). Guard: aborta si DATABASE_URL no apunta a prod o si falta un archivo.
"""
import asyncio
import sys
from datetime import date as date_cls
from pathlib import Path

from sqlalchemy import delete, select

from app.db import SessionLocal, engine
from app.ingest import opera
from app.models import Otb, OtbDaily, OtbMonthly, Property

BD = date_cls.fromisoformat(sys.argv[1])
FILES = sys.argv[2:]


async def main():
    url = str(engine.url)
    print("DB:", url)
    assert "hayabusa" in url or "railway" in url, "NO apunta a prod -- abortado"
    assert FILES, "faltan los 2 archivos history_forecast"
    for f in FILES:
        assert Path(f).exists(), f"no existe: {f}"
    async with SessionLocal() as s:
        pid = (await s.execute(select(Property.id).where(Property.code == "COWLCR"))).scalar_one()
        # borrado SOLO de las 3 tablas OTB del dia (quirurgico, no toca revenue/occ/audit)
        await s.execute(delete(Otb).where(Otb.property_id == pid, Otb.business_date == BD))
        await s.execute(delete(OtbMonthly).where(OtbMonthly.property_id == pid, OtbMonthly.snapshot_date == BD))
        await s.execute(delete(OtbDaily).where(OtbDaily.property_id == pid, OtbDaily.snapshot_date == BD))

        hf = opera.parse_history_forecast(FILES, BD)
        for scope in ("total", "rooms"):
            if scope in hf:
                row = hf[scope]
                s.add(Otb(property_id=pid, business_date=BD, scope=scope,
                          source_file=Path(row["file"]).name, revenue=row["revenue"],
                          no_rooms=row["rooms"], no_persons=row["persons"],
                          inventory_rooms=row["inventory"], adr=row["adr"], occupancy=row["occupancy"]))

        monthly = opera.history_forecast_monthly(FILES)
        for (yr, mth), mv in monthly.items():
            s.add(OtbMonthly(property_id=pid, snapshot_date=BD, year=yr, month=mth,
                             total_revenue=mv["total_revenue"], rooms_only_revenue=mv["rooms_only_revenue"],
                             rooms_only_history=mv["rooms_only_history"], rooms_only_forecast=mv["rooms_only_forecast"],
                             rooms_occ=mv["rooms_occ"], guests=mv["guests"], rooms_avail=mv["rooms_avail"]))

        daily = opera.history_forecast_daily(FILES)
        for iso, dv in daily.items():
            s.add(OtbDaily(property_id=pid, snapshot_date=BD, the_date=date_cls.fromisoformat(iso),
                           rooms_sold=dv["rooms_sold"], rooms_avail=dv["rooms_avail"]))

        await s.commit()
        tot = sum(float(v["total_revenue"]) for v in monthly.values())
        ro = sum(float(v["rooms_only_revenue"]) for v in monthly.values())
        print(f"OTB backfill {BD}: otb={len(hf)} monthly={len(monthly)} daily={len(daily)}")
        print(f"  sum total_revenue={tot:,.2f}  sum rooms_only={ro:,.2f}")


asyncio.run(main())
