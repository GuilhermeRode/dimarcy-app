# Prospecção — Plano 4: filtros de qualidade e liberação pelo admin

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import only plausible wholesale customers (ME/EPP, not MEI, head office, with contact, open ≥ 6 months — all editable), keep imported leads "aguardando liberação" until the admin releases them to sellers, and let the admin start an import from the screen.

**Architecture:** Filters live in `app_settings` and are applied by the importer (they're part of the import scope, so changing one re-imports). A new lead status `pending` sits before `new` (= released). Release is an admin-only bulk endpoint. "Atualizar agora" spawns the importer as a separate OS process.

**Tech Stack:** FastAPI + SQLAlchemy (SQLite), stdlib importer, React/Vite. Backend tests: assert scripts from `backend/`.

**Spec:** `docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md`, section "Revisão 2 (2026-10-18)".

## Global Constraints

- Code in English; user-visible text pt-BR (CLAUDE.md). No new dependencies.
- New columns on existing tables via `_ensure_columns` in `backend/app/main.py` (leads is a table that may already exist in dev DBs).
- Lead statuses: `pending` (aguardando liberação, admin only) → `new` (liberado) → `converted` | `discarded`.
- Sellers never see `pending` leads anywhere (list, detail, contacts, due list) → 404 on detail/contacts.
- Size codes: Receita porte `00` não informado, `01` ME, `03` EPP, `05` demais. Stored `leads.size`: `mei`, `me`, `epp`, `large`, `""`. UI labels: MEI, ME, EPP, Grande, —.
- Defaults: `lead_sizes="01,03"`, `lead_exclude_mei=True`, `lead_head_office_only=True`, `lead_require_contact=True`, `lead_min_age_months=6` (0–120).
- Simples.zip: 7 columns; index 0 CNPJ básico, index 4 opção MEI (`"S"`/`"N"`). Estabelecimentos index 3: `"1"` matriz, `"2"` filial. Empresas index 5: porte.
- Run all backend suites before each commit: `cd backend && python test_leads.py && python test_lead_import.py && python test_dashboard.py && python test_permissions.py && python test_finance.py && python test_price_tables.py && python test_security.py`.

## Review Focus

- A seller must get 404 for a `pending` lead on `GET /leads/{id}`, `/contacts?lead_id=`, `POST /contacts`, convert and discard.
- Releasing leads whose city has no seller must not make them `new` (nobody would see them); the admin is told how many were skipped.
- Changing any filter must re-import (scope text), and the "less than half" guard must not block that.
- Two clicks on "Atualizar agora" must start only one import.
- Existing test fixtures must keep passing with the new defaults (head office, contact, size) — fixtures get explicit matriz/porte data, not looser defaults.

---

### Task 1: Filter settings and `leads.size` (backend)

**Files:** `backend/app/models.py`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/routers/settings.py`, `backend/test_leads.py`

**Produces:** `AppSettings.lead_sizes: str`, `lead_exclude_mei: bool`, `lead_head_office_only: bool`, `lead_require_contact: bool`, `lead_min_age_months: int`, `lead_import_started_at: datetime | None`, `lead_import_error: str | None`; `Lead.size: str` (String(5), default `""`); `LEAD_STATUSES = ["pending", "new", "converted", "discarded"]`; settings API reads/writes the five filters (all optional on PUT, None = keep) and returns them plus `lead_import_started_at`, `lead_import_error` to admins only.

- [ ] **Step 1: Test** — in `backend/test_leads.py` `check_settings`, after the existing asserts, add:

```python
    r = c.get("/api/settings", headers=admin).json()
    assert (r["lead_sizes"], r["lead_exclude_mei"], r["lead_head_office_only"], r["lead_require_contact"],
            r["lead_min_age_months"]) == ("01,03", True, True, True, 6), r
    assert r["lead_import_started_at"] is None and r["lead_import_error"] is None
    r = c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "03, 01,05", "lead_exclude_mei": False,
                                                    "lead_head_office_only": False, "lead_require_contact": False,
                                                    "lead_min_age_months": 0})
    assert r.status_code == 200, r.text
    assert (r.json()["lead_sizes"], r.json()["lead_min_age_months"]) == ("01,03,05", 0)
    assert c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "02"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_sizes": ""}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_min_age_months": 121}).status_code == 422
    r = c.put("/api/settings", headers=admin, json=base)  # omitted: unchanged
    assert r.json()["lead_sizes"] == "01,03,05" and r.json()["lead_exclude_mei"] is False
    assert "lead_sizes" not in c.get("/api/settings", headers=ctx["a"]).json()
    c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "01,03", "lead_exclude_mei": True,
                                                "lead_head_office_only": True, "lead_require_contact": True,
                                                "lead_min_age_months": 6})
```

Run `cd backend && python test_leads.py` → fails (KeyError `lead_sizes`).

- [ ] **Step 2: Model** — `models.py`: `LEAD_STATUSES = ["pending", "new", "converted", "discarded"]`; in `AppSettings` after `last_lead_import_at`:

```python
    lead_sizes: Mapped[str] = mapped_column(String(20), default="01,03", server_default="01,03")  # Receita porte codes
    lead_exclude_mei: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_head_office_only: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_require_contact: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    lead_min_age_months: Mapped[int] = mapped_column(Integer, default=6, server_default="6")
    lead_import_started_at: Mapped[datetime | None] = mapped_column(DateTime)  # set while an import runs
    lead_import_error: Mapped[str | None] = mapped_column(String(300))  # last failure, cleared on success
```

In `Lead`: `size: Mapped[str] = mapped_column(String(5), default="", server_default="")  # mei | me | epp | large | ""`; update the `status` comment to the new list.

- [ ] **Step 3: Migration** — `main.py`: add to the `app_settings` `_ensure_columns` dict
`"lead_sizes": "VARCHAR(20) DEFAULT '01,03'", "lead_exclude_mei": "BOOLEAN DEFAULT 1", "lead_head_office_only": "BOOLEAN DEFAULT 1", "lead_require_contact": "BOOLEAN DEFAULT 1", "lead_min_age_months": "INTEGER DEFAULT 6", "lead_import_started_at": "TIMESTAMP", "lead_import_error": "VARCHAR(300)"`, and a new call `_ensure_columns("leads", {"size": "VARCHAR(5) DEFAULT ''"})` (after `create_all`, so the table exists).

- [ ] **Step 4: Schemas** — `AppSettingsIn` gains optional fields (None = keep):

```python
    lead_sizes: str | None = None
    lead_exclude_mei: bool | None = None
    lead_head_office_only: bool | None = None
    lead_require_contact: bool | None = None
    lead_min_age_months: int | None = Field(default=None, ge=0, le=120)

    @field_validator("lead_sizes")
    @classmethod
    def _sizes(cls, v: str | None) -> str | None:
        if v is None:
            return v
        codes = sorted({p.strip() for p in v.split(",") if p.strip()})
        if not codes or any(c not in ("00", "01", "03", "05") for c in codes):
            raise ValueError("Escolha pelo menos um porte de empresa.")
        return ",".join(codes)
```

`AppSettingsAdminOut` gains `lead_sizes: str`, `lead_exclude_mei: bool`, `lead_head_office_only: bool`, `lead_require_contact: bool`, `lead_min_age_months: int`, `lead_import_started_at: datetime | None = None`, `lead_import_error: str | None = None`.

- [ ] **Step 5: Router** — `update_settings`: for each of the five fields, `if data.X is not None: s.X = data.X`.
- [ ] **Step 6:** Run all backend suites → OK. Commit "Settings: lead quality filters and import status fields".

---

### Task 2: Importer applies the filters, labels size, inserts `pending`, supports `--force` and records status

**Files:** `backend/app/lead_import.py`, `backend/test_lead_import.py`

**Consumes:** Task 1 settings fields and `Lead.size`.
**Produces:** `current_scope(db) -> tuple[set[str], set[str], dict, str]` (`states, cnaes, filters, scope_text`), `pick(row, cnaes, states, towns, filters, today)`, `run(db, latest_month, download, parts=10, force=False)`, `main(argv=None)` accepting `--force`.

- [ ] **Step 1: Verify the Simples layout against the real file** (one 310 MB download, streamed): write a throwaway snippet in the scratchpad (not in the repo) that calls `lead_import.download(latest_month(), "Simples.zip", <tmp path>)`, then prints the first 3 rows of `read_rows(path, 7)`. Confirm 7 columns and index 4 is `S`/`N`. Put the output in the report and delete the file. If the layout differs, stop and report (NEEDS_CONTEXT).
- [ ] **Step 2: Tests first** — in `backend/test_lead_import.py`:
  - `estab()` gets `matriz="1"` (index 3) as a new default parameter; existing fixtures keep working.
  - Every `check_run` fixture CNPJ básico that must be imported gets an `Empresas*.zip` row with porte `"01"` (ME) — add rows to the existing `Empresas2.zip` list (7 columns: básico, razão, natureza, qualificação, capital, porte, ente).
  - Add `"Simples.zip"` to the fake files (rows of 7 columns, `[básico, "S", "", "", "N", "", ""]`).
  - New `check_filters()` (call it from `__main__`) with its own fresh seller/scope and today 2026-10-16, asserting that with the default settings: a filial (`matriz="2"`) is out; a store without phone and e-mail is out; one opened 2026-07-01 (< 6 months) is out; porte `05` is out; porte `00` is out; a store whose básico is MEI (`opção MEI = "S"`) is out even with porte `01`; an EPP (`03`) store is in with `size == "epp"`; an ME store is in with `size == "me"`; every imported lead has `status == "pending"`.
  - Changing `lead_exclude_mei` to False and running again in the same month re-imports (scope changed) and the MEI store appears with `size == "mei"`.
  - `run(..., force=True)` with an unchanged month and scope does run (doesn't return "up-to-date").
  - `main(["--force"])`-style status: call a helper that runs the main wrapper with fake fetchers (see Step 4) and assert `lead_import_started_at` is None afterwards and `lead_import_error` holds the message after a failing run and is None after a successful one.
  Run → fails.
- [ ] **Step 3: Implement filters and size**
  - `current_scope`: read the five filters from settings into `filters = {"sizes": set(...), "exclude_mei": bool, "head_office_only": bool, "require_contact": bool, "min_age_months": int}`; scope text = `f"{states}|{cnaes}|{sizes}|mei{int}|ho{int}|ct{int}|age{n}"` (each list sorted, comma-joined).
  - `pick(...)`: also return `None` when `filters["head_office_only"] and row[3] != "1"`, when `filters["require_contact"]` and there's neither phone nor e-mail, and when `filters["min_age_months"]` and (`opened_at` is None or `opened_at > today - timedelta(days=30 * min_age_months)`).
  - `run`: always do the Empresas pass for **all** found básicos, collecting `porte` (index 5) and the razão social for the unnamed ones; then a Simples pass collecting the set of básicos with index 4 == `"S"`. Size per lead: `"mei"` if MEI, else `{"01": "me", "03": "epp", "05": "large"}.get(porte, "")`. Drop the lead when (`exclude_mei` and size == "mei") or (size != "mei" and porte (default `"00"`) not in `filters["sizes"]`). Print one progress line per file as today.
  - `apply`: new leads get `status="pending"` and `size`; refreshed leads update `size` too (status kept); vanished leads are deleted when status in (`pending`, `new`) and without contacts (keep the SQL re-check, now with `Lead.status.in_(("pending", "new"))`).
  - Sanity guard: `existing_new` counts `status in ("pending", "new")`.
  - `force=True` skips only the "up-to-date" early return.
- [ ] **Step 4: Status + CLI** — refactor `main` so the status logic is testable:

```python
def run_and_record(db: Session, latest_month, download, force: bool = False) -> str:
    """run() plus the status the Prospecção screen shows: started_at while running, last error."""
    s = get_app_settings(db)
    s.lead_import_started_at, s.lead_import_error = datetime.now(), None
    db.commit()
    try:
        return run(db, latest_month, download, force=force)
    except Exception as e:
        db.rollback()
        get_app_settings(db).lead_import_error = repr(e)[:300]
        raise
    finally:
        get_app_settings(db).lead_import_started_at = None
        db.commit()


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (sys.argv[1:] if argv is None else argv)
    with SessionLocal() as db:
        try:
            print(f"[lead_import] {run_and_record(db, latest_month, download, force)}", flush=True)
            return 0
        except Exception as e:  # logged by systemd; tomorrow's run tries again
            print(f"[lead_import] failed, nothing written: {e!r}", file=sys.stderr, flush=True)
            return 1
```

- [ ] **Step 5:** All backend suites OK (fix `test_leads.py` only if it relied on importer behavior — it shouldn't). Commit "Lead import: quality filters, size, pending status, --force and run status".

---

### Task 3: API — pending visibility, release, admin status tab, import-now

**Files:** `backend/app/leads.py`, `backend/app/routers/leads.py`, `backend/app/routers/contacts.py`, `backend/app/routers/settings.py`, `backend/app/schemas.py`, `backend/test_leads.py`

**Produces:**
- `ranked_leads(..., status="new")`; `GET /api/leads?status=pending|new` (admin may pass `pending`; a seller always gets `new`; other values → 422).
- `lead_out` adds `"size"`.
- `visible_lead`: a seller gets 404 for `pending` leads.
- convert, discard: conditional status `in ("pending", "new")`. Contacts POST: allowed when status in (`pending`, `new`), else 409 (unchanged text).
- `POST /api/leads/release` (admin only), body `{"ids": [int, ...]}` (1–500 ids) → `{"released": n, "skipped_no_seller": m}`: only `pending` leads whose city has an active seller become `new`; others untouched.
- `POST /api/settings/lead-import` (admin only) → 202 `{"started": true}`; 409 "Já existe uma importação em andamento." when `lead_import_started_at` is within the last 4 h. Starts `[sys.executable, "-m", "app.lead_import", "--force"]` with `cwd` = backend dir, stdout/stderr appended to `backend/lead_import.log`, detached (`start_new_session=True` on POSIX; `creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP` on Windows). It also sets `lead_import_started_at = now()` before spawning so a second click gets 409 even before the child starts. Make the spawn function a module-level `_spawn_import()` so tests can monkeypatch it.
- `backend/lead_import.log` added to `.gitignore`.

- [ ] **Step 1: Tests** (new `check_pending_release` in `test_leads.py`, called last): create leads with `status="pending"` via `add_lead(..., status="pending")` in Ana's city, in Bruno's city and in a city without seller; assert seller lists don't include them and `GET /leads/{id}`, `/contacts?lead_id=`, `POST /contacts`, convert, discard all 404 for the seller; admin `GET /leads?status=pending` lists them with `size`; a seller passing `status=pending` still gets only `new`; `status=foo` → 422; `POST /leads/release` by a seller → 403; admin releases all three ids → `{"released": 2, "skipped_no_seller": 1}` and the two now show for their sellers; releasing again → `{"released": 0, ...}`; admin can discard a pending lead (204). For import-now: monkeypatch `app.routers.settings._spawn_import` to record calls; first POST → 202 and one call; second POST → 409; after setting `lead_import_started_at` 5 h ago → 202 again; seller → 403.
- [ ] **Step 2:** Implement as listed. Keep the region join for sellers unchanged; add `Lead.status == status`.
- [ ] **Step 3:** All suites OK. Commit "Leads: pending status, admin release and import-now endpoint".

---

### Task 4: Prospecção (admin) — Aguardando / Liberados, release, import status

**Files:** `frontend/src/pages/Leads.jsx`, `frontend/src/components/LeadPanel.jsx`, `frontend/src/format.js`, `frontend/src/styles.css`

- [ ] **Step 1:** `format.js`: `export const LEAD_SIZES = { mei: "MEI", me: "ME", epp: "EPP", large: "Grande" };`
- [ ] **Step 2:** `Leads.jsx` (admin only; seller view unchanged):
  - Tabs under the header (reuse the app's tab/pill style used elsewhere — e.g. the Faturamento tabs or `pill-select`): **Aguardando liberação** (default) and **Liberados**; the tab is sent as `status=pending|new` and is part of `filters` (changing it reloads and clears selection).
  - Each row shows the size label (`LEAD_SIZES[l.size] || "—"`) in the meta line.
  - In "Aguardando": a checkbox per row (clicking the checkbox must not open the panel), a toolbar with **"Selecionar os 20 primeiros"**, **"Limpar seleção"** and **"Liberar (N)"** (disabled at 0 / while busy). On success: remove released rows from the list, adjust `total`, notice `"N lojas liberadas para os vendedores."` plus, when `skipped_no_seller > 0`, `" M sem vendedor — cadastre a cidade em Usuários."`.
  - Import status line in the header area: `Última importação: dados de <mês/ano> (<data>)` or `Ainda não houve importação.`; when `lead_import_started_at` → `Importando desde HH:MM…`; when `lead_import_error` → `Última tentativa falhou: <erro>` (muted/danger). Button **"Atualizar agora"** → `POST /settings/lead-import`; on 202 re-fetch `/settings` and show `Importando…`; on 409 show the message. Read status from `GET /settings` on mount.
  - Empty state for admin in "Aguardando": "Nenhuma loja aguardando liberação. Clique em Atualizar agora ou aguarde a importação da madrugada."
- [ ] **Step 3:** `LeadPanel.jsx`: show `Porte` in the info list; when `lead.status === "pending"` show a primary **"Liberar"** button (admin) that calls the same release endpoint with `[lead.id]` and informs the page via a new `onReleased` prop.
- [ ] **Step 4:** CSS only if needed, appended to the `prospecção / contatos` block; phone width must still work (checkbox column collapses with the row).
- [ ] **Step 5:** `npm run build` OK. Commit "Prospecção (admin): pending/released tabs, bulk release and import status".

---

### Task 5: Configurações — filtros da prospecção

**Files:** `frontend/src/pages/Settings.jsx`

- [ ] **Step 1:** Under the CNAE field, a "Filtros da prospecção" group:
  - Porte (checkboxes): ME (`01`), EPP (`03`), Grande (`05`), Não informado (`00`) → `lead_sizes` comma-joined; at least one required (show the backend 422 message otherwise).
  - Checkboxes: "Excluir MEI", "Só a matriz (sem filiais)", "Só lojas com telefone ou e-mail".
  - Number: "Abertas há pelo menos (meses)" 0–120.
  - Help text: "Mudar um filtro faz a próxima importação buscar as lojas de novo."
  - Send all five in the PUT body.
- [ ] **Step 2:** Remove the "Última importação" text from Configurações (it now lives in Prospecção) — or keep it; keep it only if it stays in sync. Prefer removing to avoid two sources.
- [ ] **Step 3:** `npm run build` OK. Commit "Configurações: prospecting quality filters".
