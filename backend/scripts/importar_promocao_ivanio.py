"""Cadastra os produtos da planilha "Preços promoção 2027 Ivânio" como produtos novos.

Para cada referência da planilha (ex.: 1028):
- referência = a da planilha; descrição em branco;
- preço = coluna "Por" e tamanhos = coluna "TAM." da planilha; coleção "Promoção 2027 Ivânio";
- só a cor "Sortidas" (criada se não existir);
- habilitado só para o vendedor Ivânio (os outros vendedores não veem).
Se a referência já existir como produto de outra coleção, para sem gravar nada (não mexe em produto existente).

Roda direto no servidor, sem deploy e sem dependências (só Python 3).
Sem --apply só simula. Com --apply, faz antes uma cópia do banco (<banco>.bak-AAAAMMDD-HHMMSS).
Pode rodar mais de uma vez: não duplica nada.

Uso (na pasta do backend, onde fica o dimarcy.db):
    python3 importar_promocao_ivanio.py              # simula
    python3 importar_promocao_ivanio.py --apply      # grava
    python3 importar_promocao_ivanio.py --db /caminho/dimarcy.db --apply
"""
import os
import sqlite3
import sys
import time
import unicodedata

# Referência -> (preço "Por", tamanhos) — planilha docs/"Preços promoção 2027 Ivânio.xlsx"
PROMO = {
    "1028": (79.80, "P,M,G,GG"), "1050": (79.80, "P,M,G,GG"), "1057": (69.80, "P,M,G,GG"),
    "1161": (69.80, "P,M,G,GG,XGG"), "1133": (69.80, "P,M,G,GG,XGG"), "1216": (89.80, "P,M,G,GG,XGG"),
    "1210": (79.80, "P,M,G,GG"), "1137": (59.80, "P,M,G,GG"), "1160": (89.80, "P,M,G,GG"),
    "1111": (68.90, "P,M,G,GG,XGG"), "1501": (24.90, "10,12,14"), "150": (12.90, "02,04,06,08"),
    "111": (17.80, "PP,P,M,G,GG"), "128": (35.90, "M,G,GG"), "130": (35.90, "M,G,GG"),
    # the sheet's 2006 is the children's one; "2006" in production is a different (regular) product
    "2006-INF": (19.80, "02,04,06,08"),
}
COLLECTION = "Promoção 2027 Ivânio"
COLOR = ("Sortidas", "#d64545", "#2f6fed")  # name, hex, hex2 (two-tone swatch)
SELLER = "ivanio"


def fold(text):
    """Lowercase without accents, so "Ivânio" == "ivanio"."""
    return "".join(c for c in unicodedata.normalize("NFD", text or "").casefold() if unicodedata.category(c) != "Mn")


def run(con, apply):
    cur = con.cursor()
    sellers = [(uid, name) for uid, name in cur.execute("SELECT id, name FROM users WHERE role = 'seller'")
               if SELLER in fold(name).split()]
    if len(sellers) != 1:
        raise SystemExit("Esperava 1 vendedor chamado Ivânio, achei %d: %r" % (len(sellers), sellers))
    seller_id, seller_name = sellers[0]

    existing = {}
    for ref in PROMO:  # validate everything before writing anything
        row = cur.execute("SELECT id, collection FROM products WHERE reference = ?", (ref,)).fetchone()
        if row and row[1] != COLLECTION:
            raise SystemExit("A referência %s já existe como outro produto (coleção %r). Nada foi gravado." % (ref, row[1]))
        existing[ref] = row[0] if row else None

    stats = {"vendedor": seller_name, "cor": "existente", "produtos novos": 0, "produtos atualizados": 0}
    color = cur.execute("SELECT id FROM colors WHERE lower(name) = lower(?)", (COLOR[0],)).fetchone()
    if color:
        color_id = color[0]
    else:
        cur.execute("INSERT INTO colors (name, hex, hex2) VALUES (?, ?, ?)", COLOR)
        color_id = cur.lastrowid
        stats["cor"] = "criada"

    for ref, (price, sizes) in PROMO.items():
        pid = existing[ref]
        if pid is None:
            cur.execute("INSERT INTO products (reference, description, collection, price, sizes, active) "
                        "VALUES (?, '', ?, ?, ?, 1)", (ref, COLLECTION, price, sizes))
            pid = cur.lastrowid
            stats["produtos novos"] += 1
        else:  # a re-run: refresh price and sizes, keep anything else edited in the app since
            cur.execute("UPDATE products SET price = ?, sizes = ?, active = 1 WHERE id = ?", (price, sizes, pid))
            stats["produtos atualizados"] += 1
        cur.execute("INSERT OR IGNORE INTO product_color (product_id, color_id) VALUES (?, ?)", (pid, color_id))
        cur.execute("DELETE FROM product_seller WHERE product_id = ?", (pid,))
        cur.execute("INSERT INTO product_seller (product_id, user_id) VALUES (?, ?)", (pid, seller_id))

    if apply:
        con.commit()
    else:
        con.rollback()
    return stats


def main(argv):
    db_path = argv[argv.index("--db") + 1] if "--db" in argv else "dimarcy.db"
    apply = "--apply" in argv
    if not os.path.isfile(db_path):
        raise SystemExit("Banco não encontrado: %s (use --db /caminho/do/dimarcy.db)" % os.path.abspath(db_path))

    if apply:  # safety copy, using SQLite's own online backup
        backup = "%s.bak-%s" % (db_path, time.strftime("%Y%m%d-%H%M%S"))
        with sqlite3.connect(db_path) as src, sqlite3.connect(backup) as dst:
            src.backup(dst)
        print("Cópia de segurança: %s" % backup)

    con = sqlite3.connect(db_path)
    try:
        stats = run(con, apply)
    finally:
        con.close()
    print("Banco: %s" % os.path.abspath(db_path))
    for k, v in stats.items():
        print("  %s: %s" % (k, v))
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])
