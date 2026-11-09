import hashlib
import json
from datetime import date, datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from models import (
    BackgroundTask, DataRecord, DataSource, Dataset, IngestionJob, KPI,
)

DEMO_DATASET_DESCRIPTION = "Dados sintéticos para explorar os recursos do DataPulse."
DEMO_DATASET_NAME = "Vendas de demonstração"
DEMO_SOURCE_NAME = "Fonte de vendas demonstrativa"
DEMO_JOB_FILENAME = "vendas-demonstracao.csv"
DEMO_COLUMNS = [
    {"name": "data", "kind": "date", "required": True},
    {"name": "categoria", "kind": "string", "required": True},
    {"name": "regiao", "kind": "string", "required": True},
    {"name": "receita", "kind": "number", "required": True},
    {"name": "pedidos", "kind": "number", "required": True},
]


class DemoDataRestoreInProgress(Exception):
    pass


def _sample_rows() -> list[dict]:
    rows = []
    categories = ("Tecnologia", "Serviços", "Acessórios")
    regions = ("Sudeste", "Sul", "Nordeste")
    for month in range(1, 13):
        for index, category in enumerate(categories):
            rows.append({
                "data": date(2026, month, 5 + index * 7).isoformat(),
                "categoria": category,
                "regiao": regions[index],
                "receita": 2400 + month * 230 + index * 370,
                "pedidos": 16 + month * 2 + index * 5,
            })
    return rows


def _unique_name(db: Session, model, base_name: str) -> str:
    existing = set(db.scalars(select(model.name)))
    if base_name not in existing:
        return base_name
    index = 2
    while f"{base_name} ({index})" in existing:
        index += 1
    return f"{base_name} ({index})"


def _create_sample_dataset(db: Session, user_id: int) -> Dataset:
    source = DataSource(
        name=_unique_name(db, DataSource, DEMO_SOURCE_NAME),
        kind="csv",
        created_by=user_id,
    )
    db.add(source)
    db.flush()
    dataset = Dataset(
        name=_unique_name(db, Dataset, DEMO_DATASET_NAME),
        description=DEMO_DATASET_DESCRIPTION,
        source_id=source.id,
        schema=DEMO_COLUMNS,
        created_by=user_id,
    )
    db.add(dataset)
    db.flush()
    return dataset


def _replace_demo_records(db: Session, dataset: Dataset, user_id: int) -> int:
    rows = _sample_rows()
    job = IngestionJob(
        dataset_id=dataset.id,
        status="completed",
        filename=DEMO_JOB_FILENAME,
        total_rows=len(rows),
        imported_rows=len(rows),
        finished_at=datetime.now(timezone.utc),
        created_by=user_id,
    )
    db.add(job)
    db.flush()

    for row in rows:
        payload = json.dumps(row, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        db.add(DataRecord(
            dataset_id=dataset.id,
            job_id=job.id,
            fingerprint=hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            data=row,
        ))
    return len(rows)


def _ensure_demo_kpi(db: Session, dataset: Dataset, user_id: int) -> None:
    query = {"dataset_id": dataset.id, "aggregation": "sum", "field": "receita"}
    kpi = db.scalar(select(KPI).where(
        KPI.name == "Receita total",
        KPI.dataset_id == dataset.id,
        KPI.created_by == user_id,
    ).limit(1))
    if kpi is not None:
        kpi.query = query
        kpi.target = 160000
        return

    name = _unique_name(db, KPI, "Receita total")
    db.add(KPI(
        name=name,
        dataset_id=dataset.id,
        query=query,
        target=160000,
        created_by=user_id,
    ))


def create_demo_data(db: Session, user_id: int) -> bool:
    if db.scalar(select(func.count(DataSource.id))) or db.scalar(select(func.count(Dataset.id))):
        return False

    dataset = _create_sample_dataset(db, user_id)
    _replace_demo_records(db, dataset, user_id)
    _ensure_demo_kpi(db, dataset, user_id)
    return True


def restore_demo_data(db: Session, user_id: int) -> tuple[bool, int]:
    dataset = db.scalar(select(Dataset).where(
        Dataset.created_by == user_id,
        Dataset.description == DEMO_DATASET_DESCRIPTION,
    ).order_by(Dataset.id).limit(1))
    if dataset is None:
        dataset = _create_sample_dataset(db, user_id)
        record_count = _replace_demo_records(db, dataset, user_id)
        _ensure_demo_kpi(db, dataset, user_id)
        return True, record_count

    task_in_progress = db.scalar(select(BackgroundTask.id).where(
        BackgroundTask.dataset_id == dataset.id,
        BackgroundTask.status.in_(("queued", "running")),
    ).limit(1))
    if task_in_progress is not None:
        raise DemoDataRestoreInProgress

    dataset.schema = DEMO_COLUMNS
    db.execute(delete(DataRecord).where(DataRecord.dataset_id == dataset.id))
    record_count = _replace_demo_records(db, dataset, user_id)
    _ensure_demo_kpi(db, dataset, user_id)
    return False, record_count
