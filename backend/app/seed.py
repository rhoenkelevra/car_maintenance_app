"""Seed data for local development: the 2014 Prius and its maintenance items.

Intervals are Toyota Japan's "severe use" values (most trips under 8 km).
See SPEC.md section 11 for where each value comes from.
"""

from __future__ import annotations

from datetime import date, timedelta

from .models import Car, FuelLogIn, ItemIn, MaintenanceIn, ScheduleIn

START_KM = 93_000


def seed_car(start_date: date) -> Car:
    return Car(
        maker="Toyota",
        model="Prius",
        model_code="ZVW30",
        year=2014,
        start_km=START_KM,
        start_date=start_date,
        shaken_expiry=date(2027, 3, 20),
    )


def _interval(**kwargs) -> ScheduleIn:
    return ScheduleIn(type="interval", **kwargs)


def seed_items() -> list[ItemIn]:
    return [
        ItemIn(
            name="Óleo do motor",
            jp_term="エンジンオイル交換",
            notes="0W-20, 4,2 L com filtro.",
            schedules=[_interval(every_km=7_500, every_months=6)],
        ),
        ItemIn(
            name="Filtro de óleo",
            jp_term="オイルフィルター交換",
            schedules=[_interval(every_km=7_500)],
        ),
        ItemIn(
            name="Filtro de ar do motor",
            jp_term="エアクリーナーエレメント交換",
            schedules=[_interval(every_km=25_000)],
        ),
        ItemIn(
            name="Fluido de freio",
            jp_term="ブレーキフルード交換",
            schedules=[_interval(every_months=24)],
        ),
        ItemIn(
            name="Líquido de arrefecimento do motor",
            jp_term="冷却水(スーパーLLC)交換",
            schedules=[_interval(every_km=80_000, every_months=48)],
        ),
        ItemIn(
            name="Fluido do transeixo (e-CVT)",
            jp_term="トランスミッションフルード交換",
            notes="Conta a partir de 0 km: nunca trocado.",
            schedules=[_interval(every_km=100_000, baseline_km=0)],
        ),
        ItemIn(
            name="Velas de ignição",
            jp_term="スパークプラグ交換",
            notes="Não confirmado: 100.000 ou 200.000 km. Conferir no メンテナンスノート.",
            schedules=[ScheduleIn(type="one_time", at_km=100_000)],
        ),
        ItemIn(
            name="Líquido do inversor",
            jp_term="インバーター冷却水交換",
            notes="Sem agenda: a Toyota manda consultar a concessionária.",
        ),
        ItemIn(
            name="Bateria auxiliar 12V",
            jp_term="補機バッテリー交換",
            schedules=[_interval(every_months=36)],
        ),
        ItemIn(
            name="Filtro do ar-condicionado",
            jp_term="エアコンフィルター交換",
            schedules=[_interval(every_km=15_000)],
        ),
        ItemIn(
            name="Calibragem dos pneus",
            jp_term="タイヤ空気圧点検",
            schedules=[_interval(every_months=1)],
        ),
        ItemIn(
            name="Rodízio de pneus",
            jp_term="タイヤローテーション",
            schedules=[_interval(every_km=5_000)],
        ),
        ItemIn(
            name="Palhetas do limpador",
            jp_term="ワイパーゴム交換",
            schedules=[_interval(every_months=12)],
        ),
        ItemIn(
            name="Vistoria (shaken)",
            jp_term="車検",
            schedules=[
                _interval(anchor="fixed", every_months=24, first_due_date=date(2027, 3, 20))
            ],
        ),
        ItemIn(
            name="Inspeção de 12 meses",
            jp_term="法定12ヶ月点検",
            schedules=[
                _interval(anchor="fixed", every_months=24, first_due_date=date(2028, 3, 20))
            ],
        ),
        ItemIn(
            name="Aditivo de combustível",
            jp_term="燃料添加剤",
            schedules=[_interval(every_fillups=3, every_km=5_000)],
        ),
        ItemIn(
            name="Reaplicar coating",
            jp_term="コーティング再施工",
            notes="Intervalo provisório.",
            schedules=[_interval(every_months=6)],
        ),
        ItemIn(
            name="Imposto do automóvel",
            jp_term="自動車税",
            schedules=[ScheduleIn(type="yearly", months=[5], day=31)],
        ),
    ]


def demo_history(
    today: date, item_ids: dict[str, str]
) -> tuple[date, list[FuelLogIn], list[MaintenanceIn]]:
    """Fake logs, relative to today, so every status shows up on screen.

    Returns the car's start date, the fuel logs and the maintenance records.
    """

    def ago(days: int) -> date:
        return today - timedelta(days=days)

    start = ago(190)
    fuel = [
        FuelLogIn(date=ago(days), km=km, litres=litres, price_total=round(litres * 172))
        for days, km, litres in [
            (180, 93_300, 28.4),
            (150, 93_750, 31.0),
            (120, 94_200, 30.2),
            (90, 94_650, 32.5),
            (60, 95_100, 29.8),
            (40, 95_400, 21.3),
            (20, 95_700, 22.0),
            (5, 95_950, 18.6),
        ]
    ]
    maintenance = [
        # Purchase service: oil is now past 6 months (orange); the oil filter
        # and tyre rotation are still fine by km.
        MaintenanceIn(
            date=start,
            km=START_KM,
            item_ids=[
                item_ids["Óleo do motor"],
                item_ids["Filtro de óleo"],
                item_ids["Rodízio de pneus"],
            ],
            cost_total=12_800,
            shop="Concessionária (revisão de entrega)",
        ),
        # Monthly tyre pressure last checked two months ago (red).
        MaintenanceIn(date=ago(60), km=95_100, item_ids=[item_ids["Calibragem dos pneus"]]),
        # Additive put in at the fill-up 40 days ago; two fill-ups since (yellow).
        MaintenanceIn(
            date=ago(40),
            km=95_400,
            item_ids=[item_ids["Aditivo de combustível"]],
            cost_total=1_480,
        ),
    ]
    return start, fuel, maintenance
