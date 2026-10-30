import { fileUrl } from "../api";
import { swatchBg } from "./ui";
import { ProductsIcon } from "./icons";

// A color mix as one strip in the real fabric colors, each segment as wide as its pieces.
// `colors` already ranked; segments without hex are the pooled "Outras cores".
export function ColorStrip({ colors, total, className = "" }) {
  const pct = (c) => Math.round((c.pieces / total) * 100);
  return (
    <div className={`color-strip ${className}`} role="img" aria-label={colors.map((c) => `${c.name} ${pct(c)}%`).join(", ")}>
      {colors.map((c) => (
        <span key={c.name} title={`${c.name} · ${c.pieces} pç · ${pct(c)}%`} className={c.hex ? "" : "others"}
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

export function ProductThumb({ url, size }) {
  const style = size ? { width: size, height: size } : undefined;
  return url
    ? <img className="product-thumb" src={fileUrl(url)} alt="" loading="lazy" style={style} />
    : <span className="product-thumb product-thumb-empty" style={style}><ProductsIcon size={16} /></span>;
}
