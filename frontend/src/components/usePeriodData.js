import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";

// Fetches /dashboard for a period; ignores responses that arrive after the period changed.
export default function usePeriodData({ start, end }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    api.get("/dashboard", { params: { start, end } })
      .then((r) => { if (current) { setData(r.data); setError(""); } })
      // Drop the previous period's numbers: shown under the new dates they'd be wrong.
      .catch((e) => { if (current) { setData(null); setError(errorMessage(e)); } });
    return () => { current = false; };
  }, [start, end]);
  return { data, error };
}
