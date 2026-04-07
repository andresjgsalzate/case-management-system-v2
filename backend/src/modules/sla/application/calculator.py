from datetime import datetime, timedelta, timezone


def is_holiday(dt: datetime, holidays: list[datetime]) -> bool:
    """Verifica si la fecha dada es un festivo en la lista."""
    for holiday in holidays:
        if holiday.date() == dt.date():
            return True
    return False


def is_working_time(dt: datetime, schedule: dict, holidays: list[datetime]) -> bool:
    """Verifica si un momento dado está dentro del horario laboral del tenant."""
    # weekday(): 0=lunes, 6=domingo
    weekday = dt.weekday()
    if weekday not in schedule.get("work_days", [0, 1, 2, 3, 4]):
        return False
    if is_holiday(dt, holidays):
        return False

    start_str = schedule.get("work_start_time", "00:00")
    end_str = schedule.get("work_end_time", "23:59")
    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))

    current_minutes = dt.hour * 60 + dt.minute
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m

    return start_minutes <= current_minutes <= end_minutes


def calculate_target_at(
    start: datetime,
    hours: float,
    schedule: dict,
    holidays: list[datetime],
) -> datetime:
    """
    Calcula la fecha objetivo sumando solo horas hábiles.

    TODO: Implementa el cuerpo de esta función.
    Parámetros:
        start    — momento de inicio del SLA (timezone-aware)
        hours    — horas hábiles que debe transcurrir
        schedule — dict con work_days, work_start_time, work_end_time
        holidays — lista de datetimes que son festivos
    Retorna:
        datetime cuando se completan `hours` horas hábiles desde `start`

    Restricciones:
        - Usar is_working_time() para evaluar cada momento
        - El resultado debe ser timezone-aware
        - No avanzar tiempo no hábil hacia el objetivo

    Enfoque sugerido (minuto a minuto):
        remaining_minutes = hours * 60
        current = start
        while remaining_minutes > 0:
            current += timedelta(minutes=1)
            if is_working_time(current, schedule, holidays):
                remaining_minutes -= 1
        return current
    """
    remaining_minutes = hours * 60
    current = start
    step = timedelta(minutes=1)
    while remaining_minutes > 0:
        current += step
        if is_working_time(current, schedule, holidays):
            remaining_minutes -= 1
    return current
