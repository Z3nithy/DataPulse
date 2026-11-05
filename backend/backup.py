"""Online SQLite backups; restore only into a new, offline database path."""
import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy.engine import make_url


def verify(path: Path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RuntimeError("Backup falhou na verificacao de integridade")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Backup possui relacionamentos invalidos")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"users", "datasets", "alembic_version"} <= tables:
            raise RuntimeError("Nao e um backup DataPulse migrado")
        return db.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def copy_database(source: Path, destination: Path):
    source, destination = source.resolve(strict=True), destination.resolve()
    if source == destination:
        raise ValueError("Origem e destino devem ser diferentes")
    verify(source)
    fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
            with closing(sqlite3.connect(destination)) as target:
                original.backup(target)
        verify(destination)
    except Exception:
        destination.unlink()
        raise


def retain_backups(directory: Path, keep: int, apply: bool = False) -> list[Path]:
    directory = directory.resolve(strict=True)
    if not directory.is_dir():
        raise NotADirectoryError(directory)
    if keep < 1:
        raise ValueError("A retencao deve preservar pelo menos um backup")
    backups = sorted(
        (path for path in directory.glob("datapulse-*.backup") if path.is_file()),
        key=lambda path: (path.stat().st_mtime_ns, path.name),
        reverse=True,
    )
    for path in backups:
        verify(path)
    expired = backups[keep:]
    if apply:
        for path in expired:
            path.unlink()
    return expired


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "verify", "restore", "retain"])
    parser.add_argument("path", type=Path, help="Arquivo do backup ou diretorio de retencao")
    parser.add_argument("--target", type=Path, help="Novo banco de destino (restore)")
    parser.add_argument("--keep", type=int, default=7, help="Backups verificados a manter (retain)")
    parser.add_argument("--apply", action="store_true", help="Executa a remocao em retain (padrao: simulacao)")
    args = parser.parse_args()
    if args.action == "verify":
        print(f"Integridade OK; migration {verify(args.path)}")
    elif args.action == "retain":
        expired = retain_backups(args.path, args.keep, args.apply)
        operation = "Removidos" if args.apply else "Seriam removidos"
        for path in expired:
            print(f"{operation}: {path}")
        if not expired:
            print("Nenhum backup excede a retencao configurada.")
    elif args.action == "restore":
        if args.target is None:
            parser.error("restore requer --target, sem sobrescrever o banco atual")
        copy_database(args.path, args.target)
        print("Restauracao verificada. Configure DATABASE_URL para o novo arquivo antes de iniciar API e worker.")
    else:
        from core.config import DATABASE_URL
        url = make_url(DATABASE_URL)
        if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
            parser.error("Backup integrado suporta SQLite em arquivo; use ferramentas nativas para outros bancos")
        copy_database(Path(url.database), args.path)
        print("Backup criado e verificado. Proteja e copie para armazenamento externo.")


if __name__ == "__main__":
    main()
