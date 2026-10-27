import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import type { RegionRef } from "../lib/types";
import { regionLabel, useUser } from "./context";

/** Searchable region list with left/right/both for lateral regions. (M2 adds click-on-3D-body picking.) */
export default function RegionPicker({ value, onChange }: { value: RegionRef[]; onChange: (v: RegionRef[]) => void }) {
  const { t } = useTranslation();
  const { regions, lang } = useUser();
  const [q, setQ] = useState("");

  const results = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return [];
    return regions
      .filter((r) => !r.group)
      .filter((r) => r.labels.cs.toLowerCase().includes(needle) || r.labels.en.toLowerCase().includes(needle) ||
        r.id.includes(needle))
      .slice(0, 12);
  }, [q, regions]);

  const keyOf = (r: RegionRef) => (typeof r === "string" ? r : r.region);
  const add = (ref: string) => {
    if (!value.some((v) => keyOf(v) === ref)) onChange([...value, ref]);
    setQ("");
  };

  return (
    <div className="stack" style={{ gap: 6 }}>
      {value.length > 0 && (
        <div className="row">
          {value.map((r) => (
            <span key={keyOf(r)} className="chip">
              {regionLabel(regions, r, lang, t)}
              <button type="button" aria-label={t("app.remove")}
                onClick={() => onChange(value.filter((x) => keyOf(x) !== keyOf(r)))}>✕</button>
            </span>
          ))}
        </div>
      )}
      <input placeholder={t("form.regionSearch")} value={q} onChange={(e) => setQ(e.target.value)} />
      {results.length > 0 && (
        <div className="region-results">
          {results.map((r) => (
            <div key={r.id} className="row" style={{ gap: 0 }}>
              {r.lateral ? (
                <>
                  <span style={{ flex: 1, padding: "6px 9px" }}>{r.labels[lang]}</span>
                  {(["left", "right", "both"] as const).map((s) => (
                    <button type="button" key={s} className="btn small" style={{ width: "auto", margin: 2 }}
                      onClick={() => add(`${r.id}:${s}`)}>{t(`form.${s}`)}</button>
                  ))}
                </>
              ) : (
                <button type="button" onClick={() => add(r.id)}>
                  <span>{r.labels[lang]}</span>
                  <span className="muted">{r.projected ? "◌" : ""}</span>
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
