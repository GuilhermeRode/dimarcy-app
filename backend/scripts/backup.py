"""Cópia de segurança diária: banco (cópia online do SQLite, conferida) + uploads/ + private/ num único
backup-AAAAMMDD-HHMMSS.tar.gz. Mantém só as KEEP cópias mais recentes.

Roda direto no servidor, sem dependências (só Python 3). Pode rodar com o app no ar.

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 scripts/backup.py                         # grava em ../backups
    python3 scripts/backup.py --dest /outro/lugar --keep 30
"""
import argparse
import os
import sqlite3
import sys
import tarfile
import tempfile
import time
from contextlib import closing

PREFIX = "backup-"


def backup(db_path, dest, keep, extra_dirs=("uploads", "private")):
    if not os.path.isfile(db_path):
        sys.exit("Banco não encontrado: %s" % db_path)
    os.makedirs(dest, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    final = os.path.join(dest, "%s%s.tar.gz" % (PREFIX, stamp))
    base = os.path.dirname(os.path.abspath(db_path))

    with tempfile.TemporaryDirectory() as tmp:
        copy = os.path.join(tmp, os.path.basename(db_path))
        with closing(sqlite3.connect(db_path)) as src, closing(sqlite3.connect(copy)) as dst:
            src.backup(dst)  # consistent snapshot even while the app writes
            ok = dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        if not ok:
            sys.exit("Cópia do banco falhou na verificação de integridade; nada foi gravado.")
        partial = final + ".part"  # a crash mid-write never leaves a file that looks complete
        with tarfile.open(partial, "w:gz") as tar:
            tar.add(copy, arcname=os.path.basename(db_path))
            for d in extra_dirs:
                if os.path.isdir(os.path.join(base, d)):
                    tar.add(os.path.join(base, d), arcname=d)
        os.replace(partial, final)

    old = sorted(f for f in os.listdir(dest) if f.startswith(PREFIX) and f.endswith(".tar.gz"))
    for f in old[:-keep] if keep > 0 else []:
        os.remove(os.path.join(dest, f))
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="dimarcy.db")
    p.add_argument("--dest", default=os.path.join("..", "backups"))
    p.add_argument("--keep", type=int, default=14)
    a = p.parse_args()
    out = backup(a.db, a.dest, a.keep)
    print("Cópia de segurança: %s (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
