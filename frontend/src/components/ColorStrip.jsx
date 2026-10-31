import { useEffect, useRef, useState } from "react";
import { fileUrl } from "../api";
import { plural } from "../format";
import { Swatch, swatchBg } from "./ui";
import { ProductsIcon } from "./icons";

// A color mix as one strip in the real fabric colors, each segment as wide as its pieces.
// `colors` already ranked; segments without hex are the pooled "Outras cores".
export function ColorStrip({ colors, total, className = "", titles = true }) {
  const pct = (c) => Math.round((c.pieces / total) * 100);
  return (
    <div className={`color-strip ${className}`} role="img" aria-label={colors.map((c) => `${c.name} ${pct(c)}%`).join(", ")}>
      {colors.map((c) => (
        <span key={c.name} title={titles ? `${c.name} · ${c.pieces} pç · ${pct(c)}%` : undefined} className={c.hex ? "" : "others"}
          style={{ flexGrow: c.pieces, background: c.hex ? swatchBg(c.hex, c.hex2) : undefined }} />
      ))}
    </div>
  );
}

// The ranked colors plus one "Outras cores" for the tail
export function pooledColors(colors, total, top) {
  const head = colors.slice(0, top);
  const rest = total - head.reduce((t, c) => t + c.pieces, 0);
  return rest > 0 ? [...head, { name: "Outras cores", hex: null, pieces: rest }] : head;
}

// Ranked rows of a color mix: swatch, name, pieces and share (the pooled "Outras cores" has no hex)
export function ColorList({ colors, total }) {
  return (
    <ol className="color-ranking">
      {colors.map((c) => (
        <li key={c.name} className={c.hex ? "" : "others"}>
          {c.hex ? <Swatch hex={c.hex} hex2={c.hex2} size={16} /> : <span className="swatch swatch-others" />}
          <span className="color-name">{c.name}</span>
          <span className="color-qty">{plural(c.pieces, "peça", "peças")}</span>
          <strong>{Math.round((c.pieces / total) * 100)}%</strong>
        </li>
      ))}
    </ol>
  );
}

const POP_WIDTH = 280;
const POP_MAX_HEIGHT = 260; // keep in sync with .color-pop

// A reference's color strip: the mouse over it previews every color sold, a click/tap keeps them open
// (phones have no hover). Fixed position, so the table's scroll area doesn't clip the list.
export function RefColors({ colors, total, className = "", style }) {
  const button = useRef(null);
  const [pos, setPos] = useState(null);
  const [pinned, setPinned] = useState(false);
  const close = () => { setPos(null); setPinned(false); };
  function place() {
    const r = button.current.getBoundingClientRect();
    const above = r.bottom + POP_MAX_HEIGHT + 8 > window.innerHeight && r.top > POP_MAX_HEIGHT;
    setPos({
      left: Math.max(8, Math.min(r.left, window.innerWidth - POP_WIDTH - 8)),
      ...(above ? { bottom: window.innerHeight - r.top + 6 } : { top: r.bottom + 6 }),
    });
  }
  useEffect(() => {
    if (!pos) return undefined;
    const outside = (e) => { if (!button.current?.contains(e.target)) close(); };
    const scrolled = (e) => { if (!e.target.closest?.(".color-pop")) close(); };
    window.addEventListener("pointerdown", outside);
    window.addEventListener("scroll", scrolled, true);
    return () => {
      window.removeEventListener("pointerdown", outside);
      window.removeEventListener("scroll", scrolled, true);
    };
  }, [Boolean(pos)]);
  return (
    <>
      <button ref={button} type="button" className={`color-bar ${className}`} style={style} aria-expanded={Boolean(pos)}
        aria-label={`Ver ${plural(colors.length, "cor vendida", "cores vendidas")}`}
        onMouseEnter={place} onMouseLeave={() => { if (!pinned) setPos(null); }}
        onClick={() => { if (pinned) close(); else { place(); setPinned(true); } }}>
        <ColorStrip colors={pooledColors(colors, total, 5)} total={total} titles={false} />
      </button>
      {pos && <div className="color-pop" style={pos}><ColorList colors={colors} total={total} /></div>}
    </>
  );
}

export function ProductThumb({ url, size }) {
  const style = size ? { width: size, height: size } : undefined;
  return url
    ? <img className="product-thumb" src={fileUrl(url)} alt="" loading="lazy" style={style} />
    : <span className="product-thumb product-thumb-empty" style={style}><ProductsIcon size={16} /></span>;
}
