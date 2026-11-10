"""Backup self-check (scripts/backup.py). Run from backend/:  python test_backup.py
Uses a throwaway folder, never dimarcy.db."""
import importlib.util
import os
import sqlite3
import tarfile
import tempfile
from contextlib import closing

spec = importlib.util.spec_from_file_location("backup", os.path.join("scripts", "backup.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "dimarcy.db")
with closing(sqlite3.connect(db)) as con:
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (42)")
    con.commit()
os.makedirs(os.path.join(tmp, "uploads", "products"))
open(os.path.join(tmp, "uploads", "products", "a.jpg"), "w").write("img")
dest = os.path.join(tmp, "backups")
os.makedirs(dest)
for i in range(3):  # older fakes so pruning has something to drop
    open(os.path.join(dest, "backup-2000010%d-000000.tar.gz" % i), "w").close()

out = mod.backup(db, dest, keep=2)
assert sorted(os.listdir(dest)) == ["backup-20000102-000000.tar.gz", os.path.basename(out)], os.listdir(dest)

with tarfile.open(out) as tar:
    names = tar.getnames()
    assert "dimarcy.db" in names and "uploads/products/a.jpg" in names, names
    tar.extract("dimarcy.db", os.path.join(tmp, "restored"), filter="data")
with closing(sqlite3.connect(os.path.join(tmp, "restored", "dimarcy.db"))) as con:
    assert con.execute("SELECT x FROM t").fetchone() == (42,)
print("ok")
