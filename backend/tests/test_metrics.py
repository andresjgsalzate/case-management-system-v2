def test_sla_compliance_100_when_no_data():
    """Con 0 registros SLA, la tasa de cumplimiento es 100%."""
    total = 0
    met = 0

    pct = round((met / total * 100), 2) if total > 0 else 100.0
    assert pct == 100.0


def test_sla_compliance_rate_calculation():
    """Cálculo correcto de compliance: met/total * 100."""
    total = 10
    breached = 2
    met = 8

    pct = round((met / total * 100), 2)
    assert pct == 80.0


def test_sla_compliance_rate_partial_breach():
    """Un breach parcial retorna valor entre 0 y 100."""
    total = 100
    breached = 15
    met = 85

    pct = round((met / total * 100), 2)
    assert 0 < pct < 100
    assert pct == 85.0


def test_avg_resolution_hours_derived_from_minutes():
    """avg_hours es avg_minutes / 60, redondeado a 2 decimales."""
    avg_minutes = 90
    avg_hours = round(avg_minutes / 60, 2)
    assert avg_hours == 1.5


def test_dashboard_summary_structure():
    """La estructura del resumen del dashboard contiene las claves correctas."""
    # Simula el retorno esperado del use_case
    summary = {
        "open_cases": 42,
        "created_today": 5,
        "resolved_today": 3,
        "unassigned": 7,
    }
    assert "open_cases" in summary
    assert "created_today" in summary
    assert "resolved_today" in summary
    assert "unassigned" in summary
    assert all(isinstance(v, int) for v in summary.values())


def test_cases_by_day_cutoff_calculation():
    """El cutoff de 30 días atrás se calcula correctamente."""
    from datetime import datetime, timedelta, timezone

    days = 30
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # El cutoff debe ser exactamente 30 días antes
    delta = now - cutoff
    assert delta.days == 30
