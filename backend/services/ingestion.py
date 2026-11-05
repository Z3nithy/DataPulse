import csv
import hashlib
import http.client
import ipaddress
import json
import math
import os
import socket
import ssl
import zipfile
from datetime import date, datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from xlrd import XLRDError, open_workbook, xldate_as_datetime, XL_CELL_DATE

from core.config import API_ALLOWED_HOSTS, MAX_IMPORT_BYTES, MAX_ROWS
from models import DataRecord, DataSource, Dataset, IngestionJob
from models.entities import utcnow
from services.analytics import refresh_dataset
from services.events import notify


class ImportProblem(ValueError):
    pass


def check_api_url(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname
    if (parts.scheme != "https" or not host or host.lower() not in API_ALLOWED_HOSTS
            or parts.username or parts.password or parts.port not in (None, 443)
            or parts.query or parts.fragment):
        raise HTTPException(422, "Host da API nao autorizado ou URL invalida")
    return host


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        # Pin the validated address while retaining TLS hostname verification.
        addresses = socket.getaddrinfo(self.host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ImportProblem("API deve resolver exclusivamente para enderecos publicos")
        address = addresses[0]
        raw = socket.socket(address[0], address[1], address[2])
        raw.settimeout(15)
        try:
            raw.connect(address[4])
            self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)
        except (OSError, ssl.SSLError):
            raw.close()
            raise


def fetch_api(source: DataSource) -> bytes:
    try:
        host = check_api_url(source.url or "")
    except HTTPException as exc:
        raise ImportProblem(str(exc.detail)) from exc
    headers = {"Accept": "application/json", "Accept-Encoding": "identity"}
    if source.credential_env:
        secret = os.getenv(source.credential_env)
        if not secret:
            raise ImportProblem("Credencial da API nao configurada no servidor")
        if any(ord(c) < 32 or ord(c) > 126 for c in secret):
            raise ImportProblem("Credencial da API contem caracteres invalidos")
        headers["Authorization"] = f"Bearer {secret}"
    connection = PublicHTTPSConnection(host, timeout=15)
    try:
        connection.request("GET", urlsplit(source.url).path or "/", headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            raise ImportProblem(f"API retornou HTTP {response.status}; redirecionamentos nao sao seguidos")
        if response.getheader("Content-Encoding", "identity") != "identity":
            raise ImportProblem("API deve retornar JSON sem compressao")
        body = response.read(MAX_IMPORT_BYTES + 1)
    except (OSError, http.client.HTTPException, ValueError, UnicodeError):
        raise ImportProblem("Falha na conexao HTTPS com a API")
    finally:
        connection.close()
    if len(body) > MAX_IMPORT_BYTES:
        raise ImportProblem("Resposta da API excede 5 MB")
    return body


def table_rows(values) -> list[dict]:
    iterator = iter(values)
    header = next(iterator, None)
    if not header:
        raise ImportProblem("Arquivo sem cabecalho")
    names = [str(value).strip() if value is not None else "" for value in header]
    if len(names) > 100 or any(not name or len(name) > 100 for name in names) or len(set(names)) != len(names):
        raise ImportProblem("Cabecalho requer ate 100 nomes unicos e nao vazios")
    rows = []
    for values in iterator:
        if len(rows) >= MAX_ROWS:
            raise ImportProblem("Importacao excede 10000 linhas")
        if len(values) != len(names):
            raise ImportProblem("Linha com quantidade de colunas diferente do cabecalho")
        rows.append(dict(zip(names, values)))
    return rows


def reject_nonfinite(_value: str):
    raise ImportProblem("JSON contem numero nao finito")


def parse_file(content: bytes, filename: str) -> list[dict]:
    if not content or len(content) > MAX_IMPORT_BYTES:
        raise ImportProblem("Arquivo vazio ou maior que 5 MB")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".json":
            rows = json.loads(content.decode("utf-8-sig"), parse_constant=reject_nonfinite)
        elif suffix == ".csv":
            text = content.decode("utf-8-sig")
            sample = text[:8192]
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
            except csv.Error:
                dialect = csv.excel
            rows = table_rows(csv.reader(StringIO(text), dialect, strict=True))
        elif suffix == ".xlsx":
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 30 * 1024 * 1024:
                    raise ImportProblem("Excel descompactado excede 30 MB")
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            try:
                if not workbook.worksheets:
                    raise ImportProblem("Arquivo Excel sem planilhas")
                sheet = workbook.worksheets[0]
                if sheet.max_row and sheet.max_row > MAX_ROWS + 1:
                    raise ImportProblem("Excel excede 10000 linhas")
                if sheet.max_column and sheet.max_column > 100:
                    raise ImportProblem("Excel excede 100 colunas")
                rows = table_rows(sheet.iter_rows(values_only=True))
            finally:
                workbook.close()
        elif suffix == ".xls":
            workbook = open_workbook(file_contents=content, on_demand=True)
            try:
                sheet = workbook.sheet_by_index(0)
                if sheet.nrows > MAX_ROWS + 1 or sheet.ncols > 100:
                    raise ImportProblem("Excel excede 10000 linhas ou 100 colunas")
                rows = table_rows([
                    [xldate_as_datetime(cell.value, workbook.datemode)
                     if cell.ctype == XL_CELL_DATE else cell.value for cell in sheet.row(i)]
                    for i in range(sheet.nrows)
                ])
            finally:
                workbook.release_resources()
        else:
            raise ImportProblem("Formato nao suportado; use CSV, JSON, XLSX ou XLS")
    except ImportProblem:
        raise
    except (UnicodeError, ValueError, SyntaxError, RecursionError, csv.Error, zipfile.BadZipFile,
            InvalidFileException, XLRDError, KeyError, IndexError, OSError) as exc:
        raise ImportProblem("Arquivo invalido ou corrompido") from exc
    if not isinstance(rows, list) or not rows or len(rows) > MAX_ROWS:
        raise ImportProblem("Dados devem ser uma lista com 1 a 10000 objetos")
    if any(not isinstance(row, dict) for row in rows):
        raise ImportProblem("Cada registro deve ser um objeto")
    normalized = []
    for row in rows:
        names = [str(key).strip() for key in row]
        if (len(names) > 100 or len(set(names)) != len(names)
                or any(not name or len(name) > 100 for name in names)):
            raise ImportProblem("Colunas invalidas ou duplicadas apos padronizacao")
        normalized.append(dict(zip(names, row.values())))
    return normalized


def normalize(value, kind: str):
    if isinstance(value, str):
        value = value.strip()
    if value is None or value == "":
        return None
    if isinstance(value, (dict, list, tuple)):
        raise ValueError("Valores aninhados nao sao suportados")
    if kind == "number":
        if isinstance(value, bool):
            raise ValueError("Booleano nao e numero")
        number = float(value)
        if not math.isfinite(number) or abs(number) > 1e100:
            raise ValueError("Numero fora do intervalo permitido (+/-1e100)")
        return number if number != 0 else 0.0
    if kind == "boolean":
        if type(value) is bool:
            return value
        if str(value).lower() not in ("true", "false"):
            raise ValueError("Booleano deve ser true ou false")
        return str(value).lower() == "true"
    if kind == "date":
        if isinstance(value, date) and not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed.isoformat()
    if isinstance(value, (float, int)) and not math.isfinite(value):
        raise ValueError("Numero nao finito")
    return str(value)


def infer_schema(rows: list[dict]) -> list[dict]:
    names = list(dict.fromkeys(name for row in rows for name in row))
    if len(names) > 100:
        raise ImportProblem("Dataset excede 100 colunas")
    if not names:
        raise ImportProblem("Dados sem colunas")
    result = []
    for name in names:
        values = [row[name] for row in rows if row.get(name) is not None
                  and str(row[name]).strip() != ""]
        kind = "string"
        for candidate in ("boolean", "number", "date"):
            if not values:
                break
            try:
                for value in values:
                    normalize(value, candidate)
                kind = candidate
                break
            except (ValueError, TypeError, OverflowError):
                continue
        result.append({"name": name, "kind": kind, "required": False})
    return result


def run_import(db: Session, dataset: Dataset, user_id: int, filename: str,
               content: bytes | None, source: DataSource | None = None,
               job: IngestionJob | None = None) -> IngestionJob:
    job = job or IngestionJob(dataset_id=dataset.id, created_by=user_id, filename=filename[:255])
    db.add(job)
    db.flush()
    try:
        if content is None:
            if source is None or source.kind != "api":
                raise ImportProblem("Envie um arquivo ou configure uma fonte API")
            content = fetch_api(source)
        rows = parse_file(content, filename)
        job.total_rows = len(rows)
        schema = dataset.schema or infer_schema(rows)
        names = {column["name"] for column in schema}
        fingerprints = set(db.scalars(select(DataRecord.fingerprint).where(
            DataRecord.dataset_id == dataset.id,
        )))
        existing_count = db.scalar(select(func.count()).select_from(DataRecord).where(
            DataRecord.dataset_id == dataset.id,
        ))
        accepted = []
        errors = []
        duplicates = 0
        rejected = 0
        for index, row in enumerate(rows, start=1):
            try:
                if set(row) - names:
                    raise ValueError("Registro contem colunas fora do esquema")
                cleaned = {}
                for column in schema:
                    try:
                        value = normalize(row.get(column["name"]), column["kind"])
                    except (ValueError, TypeError, OverflowError) as exc:
                        raise ValueError(
                            f"Valor invalido na coluna {column['name']} ({column['kind']})"
                        ) from exc
                    if value is None and column.get("required"):
                        raise ValueError(f"Coluna obrigatoria: {column['name']}")
                    cleaned[column["name"]] = value
                if all(value is None for value in cleaned.values()):
                    raise ValueError("Registro vazio")
                fingerprint = hashlib.sha256(json.dumps(
                    cleaned, sort_keys=True, ensure_ascii=True, allow_nan=False,
                ).encode()).hexdigest()
                if fingerprint in fingerprints:
                    duplicates += 1
                else:
                    fingerprints.add(fingerprint)
                    accepted.append((cleaned, fingerprint))
            except (ValueError, TypeError, OverflowError) as exc:
                rejected += 1
                if len(errors) < 30:
                    errors.append({"row": index, "message": str(exc)})
        if existing_count + len(accepted) > MAX_ROWS:
            raise ImportProblem("Dataset excederia 10000 registros; divida os dados em datasets")
        dataset.schema = schema
        for data, fingerprint in accepted:
            db.add(DataRecord(dataset_id=dataset.id, job_id=job.id, data=data, fingerprint=fingerprint))
        job.imported_rows = len(accepted)
        job.duplicate_rows = duplicates
        job.rejected_rows = rejected
        job.errors = errors
        job.status = "completed_with_errors" if rejected else "completed"
        db.flush()
        refresh_dataset(db, dataset)
    except ImportProblem as exc:
        job.status = "failed"
        job.errors = [{"message": str(exc)}]
    job.finished_at = utcnow()
    notify(db, "import", "Importacao " + job.status,
           f"{job.filename}: {job.imported_rows} importados, {job.duplicate_rows} duplicados, "
           f"{job.rejected_rows} rejeitados." + (f" {job.errors[0]['message']}" if job.errors else ""),
           "/ingestion", user_id=user_id)
    return job
