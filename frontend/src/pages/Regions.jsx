import { useEffect, useMemo, useState } from "react";
import { api, errorMessage } from "../api";
import { ErrorBox, Field, Modal } from "../components/ui";
import { normalize, plural } from "../format";
import IBGE_REGIONS from "../assets/br-regions.json"; // UF -> mesorregião -> microrregião -> cities (IBGE; scripts/gerar_regioes_ibge.py)

const STATE_NAMES = { SC: "Santa Catarina", PR: "Paraná", RS: "Rio Grande do Sul" };

// "Jaraguá do Sul - SC" / "Jaraguá do Sul/SC" -> {city, state}
const parseCity = (text) => {
  const m = text.trim().match(/^(.+?)\s*[-/]\s*([A-Za-z]{2})$/);
  return m ? { city: m[1].trim(), state: m[2].toUpperCase() } : null;
};
const cityKey = (c) => `${normalize(c.city)}|${c.state}`;
const toCities = (names, state) => names.map((city) => ({ city, state }));
const ALL_CITIES = Object.entries(IBGE_REGIONS).flatMap(([state, regions]) =>
  Object.entries(regions).flatMap(([region, micros]) => toCities(Object.values(micros).flat(), state).map((c) => ({ ...c, region }))));
const KNOWN = new Set(ALL_CITIES.map(cityKey));

function AddCityModal({ seller, options, onAdd, onClose }) {
  const [text, setText] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function addTyped(e) {
    e.preventDefault();
    const c = parseCity(text);
    if (!c) { setNote("Escreva no formato Cidade - UF (ex.: Jaraguá do Sul - SC)."); return; }
    setBusy(true);
    const ok = await onAdd([c]);
    setBusy(false);
    if (ok) { setText(""); setNote(`${c.city}/${c.state} adicionada.`); }
  }

  async function suggest() {
    setBusy(true);
    const { data } = await api.get(`/users/${seller.id}/cities/suggestions`);
    await onAdd(data);
    setBusy(false);
    setNote(`${plural(data.length, "cidade sugerida", "cidades sugeridas")}.`);
  }

  return (
    <Modal title={`Adicionar cidade: ${seller.name}`} onClose={onClose}>
      <form onSubmit={addTyped} className="form-grid">
        <Field label="Cidade - UF" span={2}>
          <input autoFocus list="city-options" placeholder="Ex.: Jaraguá do Sul - SC" value={text} onChange={(e) => setText(e.target.value)} />
          <datalist id="city-options">
            {options.map((o) => <option key={`${o.city}|${o.state}`} value={`${o.city} - ${o.state}`} />)}
          </datalist>
        </Field>
        {note && <p className="muted span-2">{note}</p>}
        <div className="actions span-2">
          <button type="button" className="btn" disabled={busy} onClick={suggest}>Sugerir pelos clientes</button>
          <button className="btn btn-primary" disabled={busy}>Adicionar</button>
        </div>
      </form>
    </Modal>
  );
}

function CityCheck({ city, checked, others, disabled, onToggle, hint }) {
  return (
    <label className="region-city">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={() => onToggle(city, !checked)} />
      <span>{city.city}{hint && <small> {hint}</small>}{others && <small> também de {others}</small>}</span>
    </label>
  );
}

function SellerRegion({ seller, sellers, options, country, onSave }) {
  const { cities } = seller;
  const [state, setState] = useState(() => ["SC", "PR", "RS"].sort((a, b) =>
    cities.filter((c) => c.state === b).length - cities.filter((c) => c.state === a).length)[0]);
  const [open, setOpen] = useState(null);
  const [showEmpty, setShowEmpty] = useState(false);
  const [search, setSearch] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const has = useMemo(() => new Set(cities.map(cityKey)), [cities]);
  const others = useMemo(() => {  // who else has each city: two sellers may share one
    const map = {};
    for (const s of sellers) {
      if (s.id !== seller.id) for (const c of s.cities) (map[cityKey(c)] ||= []).push(s.name);
    }
    return map;
  }, [sellers, seller.id]);

  async function save(list) {
    setBusy(true);
    const ok = await onSave(seller.id, list);
    setBusy(false);
    return ok;
  }
  const add = (list) => {
    const seen = new Set(has);
    return save([...cities, ...list.filter((c) => !seen.has(cityKey(c)) && seen.add(cityKey(c)))]);
  };
  const remove = (list) => {
    const out = new Set(list.map(cityKey));
    return save(cities.filter((c) => !out.has(cityKey(c))));
  };
  const toggle = (city, on) => (on ? add([city]) : remove([city]));
  const check = (c, hint) => (
    <CityCheck key={cityKey(c)} city={c} checked={has.has(cityKey(c))} disabled={busy} onToggle={toggle} hint={hint}
      others={others[cityKey(c)]?.join(", ")} />
  );

  const count = (list) => list.filter((c) => has.has(cityKey(c))).length;
  const custom = parseCity(search); // "Cidade - UF": any city, even one the IBGE list doesn't have
  const typed = normalize((custom?.city ?? search).trim());
  const outside = cities.filter((c) => !KNOWN.has(cityKey(c)));
  const regions = Object.entries(IBGE_REGIONS[state]).map(([region, micros]) => {
    const all = toCities(Object.values(micros).flat(), state);
    return { region, micros, all, mine: count(all) };
  });
  const shownRegions = regions.filter((r) => showEmpty || r.mine || r.region === open); // an emptied region stays while open
  const hidden = regions.length - regions.filter((r) => r.mine).length;
  const searchable = useMemo(() => [...new Map([...country, ...cities, ...ALL_CITIES].map((c) => [cityKey(c), c])).values()], [country, cities]);
  const found = typed.length >= 2 ? searchable.filter((c) => normalize(c.city).includes(typed) && (!custom || c.state === custom.state)).slice(0, 40) : null;

  return (
    <section className="regions-detail">
      <div className="regions-head">
        <div>
          <h2>{seller.name}</h2>
          <span className="muted">{plural(cities.length, "cidade", "cidades")}</span>
        </div>
        <div className="regions-tools">
          <input type="search" aria-label="Buscar cidade" placeholder="Buscar cidade" value={search} onChange={(e) => setSearch(e.target.value)} />
          <button type="button" className="btn" onClick={() => setAdding(true)}>Adicionar cidade</button>
        </div>
      </div>

      {found ? (
        <div className="region-cities">
          {found.map((c) => check(c, c.region ? `${c.region}/${c.state}` : c.state))}
          {!found.length && !custom && <p className="muted">Nenhuma cidade com esse nome. Para incluir mesmo assim, escreva Cidade - UF.</p>}
          {custom && !searchable.some((c) => cityKey(c) === cityKey(custom)) && (
            <button type="button" className="btn" disabled={busy} onClick={() => add([custom])}>Adicionar {custom.city}/{custom.state}</button>
          )}
        </div>
      ) : (
        <>
          <div className="region-states" role="tablist">
            {Object.keys(IBGE_REGIONS).map((uf) => (
              <button type="button" key={uf} role="tab" aria-selected={uf === state} className={uf === state ? "active" : ""}
                onClick={() => { setState(uf); setOpen(null); setShowEmpty(false); }}>
                {STATE_NAMES[uf]} <small>{cities.filter((c) => c.state === uf).length}</small>
              </button>
            ))}
          </div>
          <div className="region-rows">
            {shownRegions.map(({ region, micros, all, mine }) => {
              const isOpen = open === region;
              return (
                <div key={region} className="region-row">
                  <div className="region-row-head">
                    <button type="button" className="region-row-name" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : region)}>
                      <span className="region-caret" aria-hidden="true">{isOpen ? "▾" : "▸"}</span>
                      <strong>{region}</strong>
                    </button>
                    <span className="region-meter" aria-hidden="true"><i style={{ width: `${(mine / all.length) * 100}%` }} /></span>
                    <span className="region-count">{mine} de {all.length}</span>
                    <button type="button" className="btn" disabled={busy}
                      onClick={() => (mine === all.length ? remove(all) : add(all))}>{mine === all.length ? "Remover todas" : "Incluir todas"}</button>
                  </div>
                  {isOpen && Object.entries(micros).map(([micro, names]) => {
                    const list = toCities(names, state);
                    const n = count(list);
                    return (
                      <div key={micro} className="region-micro">
                        <div className="region-micro-head">
                          <h4>{micro}</h4>
                          <span className="muted">{n} de {list.length}</span>
                          <button type="button" className="link-btn" disabled={busy}
                            onClick={() => (n === list.length ? remove(list) : add(list))}>{n === list.length ? "Remover todas" : "Incluir todas"}</button>
                        </div>
                        <div className="region-cities">{list.map((c) => check(c))}</div>
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
          {!shownRegions.length && <p className="muted">Nenhuma cidade neste estado.</p>}
          {!!hidden && (
            <button type="button" className="link-btn region-empty-toggle" onClick={() => setShowEmpty(!showEmpty)}>
              {showEmpty ? "Ocultar regiões sem cidades" : `Adicionar outra região (${hidden})`}
            </button>
          )}
          {!!outside.length && (
            <div className="region-micro">
              <div className="region-micro-head"><h4>Outras cidades</h4></div>
              <div className="region-cities">{outside.map((c) => check(c, c.state))}</div>
            </div>
          )}
        </>
      )}
      {adding && <AddCityModal seller={seller} options={options} onAdd={add} onClose={() => setAdding(false)} />}
    </section>
  );
}

export default function Regions() {
  const [sellers, setSellers] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [options, setOptions] = useState([]);
  const [country, setCountry] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    // the whole country only for the search: its own chunk, loaded once this screen opens
    import("../assets/br-cities.json").then(({ default: byState }) =>
      setCountry(Object.entries(byState).flatMap(([state, names]) => toCities(names, state))));
    (async () => {
      try {
        const { data: users } = await api.get("/users");
        const active = users.filter((u) => u.active).sort((a, b) => (a.role === "seller" ? 0 : 1) - (b.role === "seller" ? 0 : 1) || a.name.localeCompare(b.name));
        const rows = await Promise.all(active.map((u) => api.get(`/users/${u.id}/cities`).then((r) => ({ ...u, cities: r.data }))));
        setSellers(rows);
        setSelectedId(rows[0]?.id ?? null);
        setOptions((await api.get("/users/cities/options")).data);
      } catch (err) { setError(errorMessage(err)); }
    })();
  }, []);

  async function save(id, cities) {
    setError("");
    try {
      const { data } = await api.put(`/users/${id}/cities`, cities);
      setSellers((list) => list.map((s) => (s.id === id ? { ...s, cities: data } : s)));
      return true;
    } catch (err) { setError(errorMessage(err)); return false; }
  }

  const selected = sellers?.find((s) => s.id === selectedId);

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Regiões</h1>
          <p className="muted">As cidades de cada vendedor na Prospecção. Cada alteração é salva na hora.</p>
        </div>
      </header>
      <ErrorBox msg={error} />
      {sellers && (
        <div className="regions">
          <div className="regions-list">
            {sellers.map((s) => (
              <button type="button" key={s.id} className={s.id === selectedId ? "active" : ""} aria-pressed={s.id === selectedId}
                onClick={() => { setError(""); setSelectedId(s.id); }}>
                <strong>{s.name}</strong>
                <small>{s.role === "admin" ? "Administrador · " : ""}{plural(s.cities.length, "cidade", "cidades")}</small>
              </button>
            ))}
          </div>
          {selected && <SellerRegion key={selected.id} seller={selected} sellers={sellers} options={options} country={country} onSave={save} />}
        </div>
      )}
    </div>
  );
}
