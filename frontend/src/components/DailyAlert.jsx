import { useCallback, useEffect, useState } from "react";

// The day's pop-up: what is waiting for the user (late / today follow-ups, new leads). Closing it in any
// way hides it until midnight, unless new leads arrive after that (e.g. the admin hands some out in the
// afternoon). Both marks live in localStorage per user, so they survive reloads.

const readNumber = (key) => { try { return Number(localStorage.getItem(key)) || 0; } catch { return 0; } };
const writeNumber = (key, n) => { try { localStorage.setItem(key, String(n)); } catch { /* private mode: shows again next time */ } };
const nextMidnight = () => { const t = new Date(); t.setHours(24, 0, 0, 0); return t.getTime(); };

export function useDailyAlert(userId, counts) {
  const hideKey = `daily-alert-until-${userId}`;
  const seenKey = `daily-alert-leads-${userId}`;
  const [hiddenUntil, setHiddenUntil] = useState(() => readNumber(hideKey));
  const [seenLeads, setSeenLeads] = useState(() => readNumber(seenKey));
  const [now, setNow] = useState(Date.now);

  const markSeen = useCallback((n) => { writeNumber(seenKey, n); setSeenLeads(n); }, [seenKey]);
  const close = () => { const until = nextMidnight(); writeNumber(hideKey, until); setHiddenUntil(until); markSeen(counts?.new_leads || 0); };

  useEffect(() => {  // leads worked since closing: lower the mark so the next one handed out counts as new
    if (counts && counts.new_leads < seenLeads) markSeen(counts.new_leads);
  }, [counts, seenLeads, markSeen]);
  useEffect(() => {  // app left open overnight: show again after midnight
    const id = setInterval(() => setNow(Date.now()), 60000);
    return () => clearInterval(id);
  }, []);

  const pending = counts ? counts.new_leads + counts.follow_ups_due : 0;
  const newLeadsSinceClosed = !!counts && counts.new_leads > seenLeads;
  return { visible: pending > 0 && (now >= hiddenUntil || newLeadsSinceClosed), close };
}

const BellIcon = () => (
  <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
  </svg>
);

export default function DailyAlert({ name, counts, onClose, onGo }) {
  const now = new Date();
  const hour = now.getHours();
  const hello = hour < 12 ? "Bom dia" : hour < 18 ? "Boa tarde" : "Boa noite";
  const day = now.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const late = counts.follow_ups_late, todayDue = counts.follow_ups_due - late;
  const rows = [
    late > 0 && { tone: "late", n: late, label: late === 1 ? "retorno atrasado" : "retornos atrasados",
      hint: "Já passou do dia combinado", to: "/follow-ups" },
    todayDue > 0 && { tone: "today", n: todayDue, label: todayDue === 1 ? "retorno para hoje" : "retornos para hoje",
      hint: "Contatos combinados para hoje", to: "/follow-ups" },
    counts.new_leads > 0 && { tone: "new", n: counts.new_leads, label: counts.new_leads === 1 ? "nova oportunidade" : "novas oportunidades",
      hint: "Chegaram para você, ainda sem contato", to: "/leads" },
  ].filter(Boolean);
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal daily-alert" role="dialog" aria-labelledby="daily-alert-title">
        <button className="btn-x daily-alert-x" onClick={onClose} aria-label="Fechar">×</button>
        <div className="daily-alert-head">
          <span className="daily-alert-bell"><BellIcon /></span>
          <h2 id="daily-alert-title">{hello}, {(name || "").split(" ")[0]}!</h2>
          <p>{day.charAt(0).toUpperCase() + day.slice(1)}<br />Veja o que está esperando por você</p>
        </div>
        <div className="daily-alert-list">
          {rows.map((r) => (
            <button key={r.tone} type="button" className={`daily-alert-row daily-${r.tone}`} onClick={() => onGo(r.to)}>
              <span className="daily-alert-count">{r.n}</span>
              <span className="daily-alert-text"><strong>{r.label}</strong><small>{r.hint}</small></span>
              <span className="daily-alert-go" aria-hidden="true">›</span>
            </button>
          ))}
        </div>
        <button type="button" className="btn daily-alert-later" onClick={onClose}>Mais tarde</button>
      </div>
    </div>
  );
}
