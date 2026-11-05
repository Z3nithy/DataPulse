import math
import operator
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Alert, DataRecord, Dataset, Insight, KPI
from models.entities import utcnow
from schemas.datapulse import AnalyticsQuery

COMPARISONS = {
    "eq": operator.eq, "ne": operator.ne, "gt": operator.gt,
    "gte": operator.ge, "lt": operator.lt, "lte": operator.le,
}


def get_dataset(db: Session, dataset_id: int) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(404, "Dataset nao encontrado")
    return dataset


def validate_query(dataset: Dataset, query: AnalyticsQuery) -> dict[str, dict]:
    columns = {c["name"]: c for c in dataset.schema}
    for field in [query.field, query.date_field, *query.group_by, *[f.field for f in query.filters]]:
        if field is not None and field not in columns:
            raise HTTPException(422, f"Coluna desconhecida: {field}")
    if query.field and columns[query.field]["kind"] != "number":
        raise HTTPException(422, "Agregacao requer coluna numerica")
    if query.date_field and columns[query.date_field]["kind"] != "date":
        raise HTTPException(422, "date_field requer coluna do tipo date")
    for condition in query.filters:
        kind = columns[condition.field]["kind"]
        value = condition.value
        if value is not None:
            valid = (
                (kind == "number" and type(value) in (float, int))
                or (kind == "boolean" and type(value) is bool)
                or (kind in ("string", "date") and isinstance(value, str))
            )
            if not valid:
                raise HTTPException(422, f"Filtro incompativel com {condition.field}")
            if kind == "date":
                try:
                    datetime.fromisoformat(value)
                except ValueError:
                    raise HTTPException(422, "Filtro de data requer formato ISO")
        if condition.operator == "contains" and kind != "string":
            raise HTTPException(422, "contains requer coluna string")
        if condition.operator == "contains" and not isinstance(value, str):
            raise HTTPException(422, "contains requer valor string")
        if value is None and condition.operator not in ("eq", "ne"):
            raise HTTPException(422, "Comparacao com null requer eq ou ne")
    return columns


def matches(row: dict, query: AnalyticsQuery, columns: dict) -> bool:
    for condition in query.filters:
        value = row.get(condition.field)
        expected = condition.value
        if expected is not None and columns[condition.field]["kind"] == "date":
            parsed = datetime.fromisoformat(expected)
            if parsed.tzinfo:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            expected = parsed.isoformat()
        if condition.operator == "contains":
            if value is None or expected not in value:
                return False
        elif value is None or expected is None:
            if condition.operator == "eq" and value is expected:
                continue
            if condition.operator == "ne" and value is not expected:
                continue
            return False
        elif not COMPARISONS[condition.operator](value, expected):
            return False
    return True


def period_key(value: str, period: str) -> str:
    date = datetime.fromisoformat(value)
    if period == "day":
        return date.strftime("%Y-%m-%d")
    if period == "week":
        return (date - timedelta(days=date.weekday())).strftime("%Y-%m-%d")
    return date.strftime("%Y-%m" if period == "month" else "%Y")


def aggregate(rows: list[dict], query: AnalyticsQuery) -> dict:
    values = [r[query.field] for r in rows if query.field and r.get(query.field) is not None]
    try:
        total = math.fsum(values) if values else None
    except OverflowError:
        raise HTTPException(422, "Agregacao excede o limite numerico")
    if total is not None and not math.isfinite(total):
        raise HTTPException(422, "Agregacao excede o limite numerico")
    stats = {
        "sum": total, "avg": statistics.mean(values) if values else None,
        "min": min(values) if values else None, "max": max(values) if values else None,
    }
    return {"count": len(rows), "value": len(rows) if query.aggregation == "count"
            else stats[query.aggregation], "statistics": stats}


def execute_query(db: Session, query: AnalyticsQuery) -> dict:
    dataset = get_dataset(db, query.dataset_id)
    columns = validate_query(dataset, query)
    rows = [data for data in db.scalars(
        select(DataRecord.data).where(DataRecord.dataset_id == dataset.id)
    ) if matches(data, query, columns)]
    buckets = defaultdict(list)
    for row in rows:
        key = tuple(row.get(field) for field in query.group_by)
        if query.date_field:
            date = row.get(query.date_field)
            if not date:
                continue
            key = (period_key(date, query.period), *key)
        if query.group_by or query.date_field:
            buckets[key].append(row)
    if len(buckets) > 500:
        raise HTTPException(422, "Consulta excede 500 grupos; adicione filtros")
    time_label = "period"
    while time_label in query.group_by:
        time_label = "_" + time_label
    names = ([time_label] if query.date_field else []) + query.group_by
    groups = [
        {"group": dict(zip(names, key)), **aggregate(items, query)}
        for key, items in sorted(buckets.items(), key=lambda item: tuple(
            "" if value is None else str(value) for value in item[0]
        ))
    ]
    return {
        "dataset_id": dataset.id, **aggregate(rows, query), "groups": groups,
        "comparison": compare_series(groups) if query.date_field and not query.group_by else None,
    }


def compare_series(series: list[dict]) -> dict:
    previous = series[-2]["value"] if len(series) >= 2 else None
    current = series[-1]["value"] if series else None
    growth = None
    if previous is not None and current is not None and previous != 0:
        growth = (current - previous) / abs(previous) * 100
        if not math.isfinite(growth):
            growth = None
    direction = "insufficient_data"
    if previous is not None and current is not None:
        direction = "up" if current > previous else "down" if current < previous else "stable"
    return {
        "current": current, "previous": previous, "growth_percent": growth, "direction": direction,
        "comparison": "Ultimos dois periodos observados; lacunas nao sao preenchidas.",
    }


def trends(db: Session, query: AnalyticsQuery) -> dict:
    if not query.date_field:
        raise HTTPException(422, "Selecione uma coluna de data para tendencias")
    result = execute_query(db, query)
    series = result["groups"]
    return {"series": series, **compare_series(series)}


def refresh_insights(db: Session, dataset: Dataset) -> None:
    rows = list(db.scalars(select(DataRecord.data).where(DataRecord.dataset_id == dataset.id)))
    active_keys = set()
    for column in dataset.schema:
        if column["kind"] != "number":
            continue
        name = column["name"]
        values = [r[name] for r in rows if r.get(name) is not None]
        if len(values) < 5:
            continue
        mean = statistics.mean(values)
        std = statistics.pstdev(values)
        outliers = [v for v in values if std > 0 and abs(v - mean) / std > 3]
        if not outliers:
            continue
        key = f"zscore:{name}"
        active_keys.add(key)
        insight = db.scalar(select(Insight).where(
            Insight.dataset_id == dataset.id, Insight.rule_key == key,
        ))
        if insight is None:
            insight = Insight(dataset_id=dataset.id, rule_key=key)
            db.add(insight)
        insight.kind = "anomaly"
        insight.title = f"Valores atipicos em {name}"
        insight.details = {
            "field": name, "sample_size": len(values), "mean": mean,
            "standard_deviation": std, "anomaly_count": len(outliers),
            "rule": "|z-score| > 3; minimo de 5 valores; nao e previsao ou IA.",
        }
        insight.updated_at = utcnow()
    for insight in db.scalars(select(Insight).where(Insight.dataset_id == dataset.id)):
        if insight.rule_key not in active_keys:
            db.delete(insight)


def evaluate_alert(db: Session, alert: Alert) -> None:
    previous = alert.triggered
    kpi = db.get(KPI, alert.kpi_id)
    result = execute_query(db, AnalyticsQuery.model_validate(kpi.query))
    alert.last_value = result["value"]
    alert.triggered = bool(
        alert.enabled and alert.last_value is not None
        and COMPARISONS[alert.operator](alert.last_value, alert.threshold)
    )
    alert.evaluated_at = utcnow()
    if alert.triggered and not previous:
        from services.events import notify
        notify(db, "alert", f"Limite atingido: {alert.name}",
               f"Valor {alert.last_value}; condicao {alert.operator} {alert.threshold}.",
               "/alerts", email=True)
    elif previous and not alert.triggered:
        from services.events import notify
        notify(db, "alert", f"Alerta normalizado: {alert.name}",
               "Regra desativada ou valor novamente dentro do limite.", "/alerts")


def refresh_dataset(db: Session, dataset: Dataset) -> None:
    refresh_insights(db, dataset)
    for alert in db.scalars(select(Alert).join(KPI).where(KPI.dataset_id == dataset.id)):
        evaluate_alert(db, alert)
