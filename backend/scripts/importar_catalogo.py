"""Importa um catálogo (refs, descrição, preço, tamanhos) e cores para o banco SQLite do Di Marcy Pedidos.

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
- Produtos casam pela referência; cores pelo nome (sem diferenciar maiúsculas/acentos de caixa).
- Cada produto recebe todas as cores do arquivo; cores que ele já tinha continuam.
- Valida todas as linhas antes de gravar: se uma estiver errada, nada é gravado.
- Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).
- Pode rodar mais de uma vez: não duplica nada.

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 importar_catalogo.py catalogo-2027.json                 # simula
    python3 importar_catalogo.py catalogo-2027.json --apply         # grava
    python3 importar_catalogo.py catalogo-2027.json --db /caminho/dimarcy.db --apply
"""
import json
import os
import re
import sqlite3
import sys
import time

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def clean(text):
    return " ".join(str(text if text is not None else "").split())


def validate(data):
    for c in data["colors"]:
        if not clean(c.get("name")) or not HEX.match(c.get("hex") or "#cccccc"):
            raise ValueError("Cor inválida: %r" % (c,))
    for p in data["products"]:
        sizes = [clean(s) for s in p.get("sizes", []) if clean(s)]
        try:
            price = float(p.get("price"))
        except (TypeError, ValueError):
            price = -1
        if not clean(p.get("reference")) or not clean(p.get("description")) or not sizes or price < 0 \
                or any(len(s) > 5 for s in sizes):
            raise ValueError("Produto inválido: %r" % (p,))


def run(data, con, apply):
    validate(data)
    cur = con.cursor()
    for table in ("products", "colors", "product_color"):
        if not cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
            raise SystemExit("Este banco não tem a tabela '%s'. É o banco certo?" % table)
    stats = {"cores novas": 0, "cores existentes": 0, "produtos novos": 0, "produtos atualizados": 0}

    existing = {name.casefold(): cid for cid, name in cur.execute("SELECT id, name FROM colors")}
    color_ids = []
    for c in data["colors"]:
        name = clean(c["name"])
        cid = existing.get(name.casefold())
        if cid is None:
            cur.execute("INSERT INTO colors (name, hex) VALUES (?, ?)", (name, c.get("hex") or "#cccccc"))
            cid = cur.lastrowid
            existing[name.casefold()] = cid
            stats["cores novas"] += 1
        else:
            stats["cores existentes"] += 1
        color_ids.append(cid)

    for p in data["products"]:
        ref = clean(p["reference"])
        desc = clean(p["description"])
        price = round(float(p["price"]), 2)
        sizes = ",".join(clean(s).upper() for s in p["sizes"] if clean(s))
        row = cur.execute("SELECT id FROM products WHERE reference = ?", (ref,)).fetchone()
        if row is None:
            cur.execute("INSERT INTO products (reference, description, price, sizes, active) VALUES (?, ?, ?, ?, 1)",
                        (ref, desc, price, sizes))
            pid = cur.lastrowid
            stats["produtos novos"] += 1
        else:
            pid = row[0]
            cur.execute("UPDATE products SET description = ?, price = ?, sizes = ?, active = 1 WHERE id = ?",
                        (desc, price, sizes, pid))
            stats["produtos atualizados"] += 1
        cur.executemany("INSERT OR IGNORE INTO product_color (product_id, color_id) VALUES (?, ?)",
                        [(pid, cid) for cid in color_ids])

    if apply:
        con.commit()
    else:
        con.rollback()
    return stats


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    if "--db" in argv:
        args = [a for a in args if a != db_path]
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))
    with open(args[0], encoding="utf-8") as f:
        data = json.load(f)
    validate(data)  # before the backup: a bad file changes nothing at all

    if apply:  # safety copy, using SQLite's own online backup
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        print("Cópia de segurança: %s" % backup)

    con = sqlite3.connect(db_path)
    try:
        stats = run(data, con, apply)
    finally:
        con.close()
    print("Banco: %s" % os.path.abspath(db_path))
    for k, v in stats.items():
        print("  %s: %d" % (k, v))
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])
