from datetime import datetime, timezone


SCHEDULE = {
    "work_days": [0, 1, 2, 3, 4],
    "work_start_time": "08:00",
    "work_end_time": "18:00",
}


def test_is_working_time_monday_morning():
    from backend.src.modules.sla.application.calculator import is_working_time
    # Lunes 2026-04-06 10:00 UTC
    dt = datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc)
    assert is_working_time(dt, SCHEDULE, []) is True


def test_is_not_working_time_saturday():
    from backend.src.modules.sla.application.calculator import is_working_time
    # Sábado 2026-04-11
    dt = datetime(2026, 4, 11, 10, 0, tzinfo=timezone.utc)
    assert is_working_time(dt, SCHEDULE, []) is False


def test_is_not_working_time_outside_hours():
    from backend.src.modules.sla.application.calculator import is_working_time
    # Lunes 2026-04-06 20:00 (fuera de horario)
    dt = datetime(2026, 4, 6, 20, 0, tzinfo=timezone.utc)
    assert is_working_time(dt, SCHEDULE, []) is False


def test_is_not_working_time_holiday():
    from backend.src.modules.sla.application.calculator import is_working_time
    dt = datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc)
    holidays = [datetime(2026, 4, 6, tzinfo=timezone.utc)]
    assert is_working_time(dt, SCHEDULE, holidays) is False


def test_calculate_target_simple():
    from backend.src.modules.sla.application.calculator import calculate_target_at
    start = datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)  # Lunes 8am
    target = calculate_target_at(start, hours=2.0, schedule=SCHEDULE, holidays=[])
    expected = datetime(2026, 4, 6, 10, 0, tzinfo=timezone.utc)
    assert target == expected


def test_calculate_target_crosses_end_of_day():
    from backend.src.modules.sla.application.calculator import calculate_target_at
    # Empieza lunes 17:00, SLA 2h.
    # El loop avanza +1min antes de contar: 17:01..18:00 = 60min, 08:00..08:59 = 60min → total 120min
    start = datetime(2026, 4, 6, 17, 0, tzinfo=timezone.utc)
    target = calculate_target_at(start, hours=2.0, schedule=SCHEDULE, holidays=[])
    assert target.date() == datetime(2026, 4, 7, tzinfo=timezone.utc).date()
    assert target.hour == 8
    assert target.minute == 59


def test_calculate_target_skips_weekend():
    from backend.src.modules.sla.application.calculator import calculate_target_at
    # Viernes 17:30 + 1h → lunes 8:30
    start = datetime(2026, 4, 10, 17, 30, tzinfo=timezone.utc)  # viernes
    target = calculate_target_at(start, hours=1.0, schedule=SCHEDULE, holidays=[])
    assert target.weekday() == 0  # lunes


def test_calculate_target_skips_holiday():
    from backend.src.modules.sla.application.calculator import calculate_target_at
    # Lunes festivo: SLA de 2h debe contar solo desde martes
    start = datetime(2026, 4, 6, 8, 0, tzinfo=timezone.utc)
    holidays = [datetime(2026, 4, 6, tzinfo=timezone.utc)]
    target = calculate_target_at(start, hours=2.0, schedule=SCHEDULE, holidays=holidays)
    assert target.date() == datetime(2026, 4, 7, tzinfo=timezone.utc).date()
