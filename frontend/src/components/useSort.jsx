import { useState } from "react";

// pt-BR order, ignoring case/accents; "numeric" keeps "Item 2" before "Item 10"
const collator = new Intl.Collator("pt-BR", { numeric: true, sensitivity: "base" });
const isEmpty = (v) => v == null || v === "";

/** Click-to-sort for list tables. `columns` maps a column key to `row => value` (string, number or ISO date).
 *  First click sorts ascending (A→Z, 0→9, oldest first), the next click descending; empty values always go last.
 *  Returns the sorted rows and `sortHeader(key, label, className)` to render each clickable <th>. */
export function useSort(rows, columns, initial = null) {
  const [sort, setSort] = useState(initial); // { key, dir: 1 | -1 }; null = the order the rows came in

  let sorted = rows;
  if (sort) {
    const get = columns[sort.key];
    sorted = [...rows].sort((a, b) => {
      const x = get(a), y = get(b);
      if (isEmpty(x) || isEmpty(y)) return isEmpty(x) - isEmpty(y);
      const c = typeof x === "number" && typeof y === "number" ? x - y : collator.compare(String(x), String(y));
      return c * sort.dir;
    });
  }

  const toggle = (key) => setSort((s) => ({ key, dir: s?.key === key ? -s.dir : 1 }));

  function sortHeader(key, label, className = "") {
    const dir = sort?.key === key ? sort.dir : 0;
    return (
      <th key={key} className={className} aria-sort={dir === 1 ? "ascending" : dir === -1 ? "descending" : "none"}>
        <button type="button" className="th-sort" onClick={() => toggle(key)}>
          {label}<span className="sort-arrow" aria-hidden="true">{dir === -1 ? "↓" : "↑"}</span>
        </button>
      </th>
    );
  }

  return { sorted, sort, sortHeader };
}
