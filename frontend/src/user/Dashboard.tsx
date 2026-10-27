import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../lib/api";
import { RECORD_TYPES, type MedRecord } from "../lib/types";
import { regionLabel, useUser } from "./context";
import RecordDetail from "./RecordDetail";
import RecordForm from "./RecordForm";
import TopBar from "./TopBar";
import { TypeDot } from "./ui";

type Tab = "list" | "body" | "detail" | "timeline";

export default function Dashboard() {
  const { t } = useTranslation();
  const { person, regions, lang } = useUser();
  const [records, setRecords] = useState<MedRecord[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [q, setQ] = useState("");
  const [regionFilter, setRegionFilter] = useState<string | null>(null);
  const [form, setForm] = useState<{ record: MedRecord | null } | null>(null);
  const [tab, setTab] = useState<Tab>("list");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!person) return;
    try {
      setRecords(await api<MedRecord[]>(`/api/v1/persons/${person.id}/records`));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  }, [person]);

  useEffect(() => {
    setSelectedId(null);
    setRegionFilter(null);
    void load();
  }, [load]);

  const baseId = (r: unknown) => (typeof r === "string" ? r : (r as { region: string }).region).split(":")[0];

  // Region filter matches the region and all its descendants (e.g. lower_limb → knee).
  const regionMatches = useMemo(() => {
    if (!regionFilter) return null;
    const set = new Set([regionFilter]);
    let grew = true;
    while (grew) {
      grew = false;
      for (const r of regions) if (r.parent && set.has(r.parent) && !set.has(r.id)) { set.add(r.id); grew = true; }
    }
    return set;
  }, [regionFilter, regions]);

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return records.filter(
      (r) =>
        (!typeFilter || r.type === typeFilter) &&
        (!needle || r.title.toLowerCase().includes(needle)) &&
        (!regionMatches || r.regions.some((x) => regionMatches.has(baseId(x)))),
    );
  }, [records, typeFilter, q, regionMatches]);

  const regionCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of records) for (const x of r.regions) counts.set(baseId(x), (counts.get(baseId(x)) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [records]);

  const years = useMemo(() => {
    const m = new Map<number, MedRecord[]>();
    for (const r of visible) {
      const y = parseInt(r.date.slice(0, 4), 10);
      if (!m.has(y)) m.set(y, []);
      m.get(y)!.push(r);
    }
    if (!m.size) return [];
    const min = Math.min(...m.keys());
    const max = Math.max(...m.keys(), new Date().getFullYear());
    return Array.from({ length: max - min + 1 }, (_, i) => [min + i, m.get(min + i) ?? []] as const);
  }, [visible]);

  const selected = records.find((r) => r.id === selectedId) ?? null;
  const select = (id: string) => { setSelectedId(id); setTab("detail"); };

  if (!person) return <><TopBar /><div className="center-page muted">{t("app.loading")}</div></>;

  return (
    <>
      <TopBar onAdd={() => setForm({ record: null })} />
      <main className="dashboard">
        <nav className="mobile-tabs">
          {(["list", "body", "detail", "timeline"] as Tab[]).map((x) => (
            <button key={x} className={`btn ${tab === x ? "active" : ""}`} onClick={() => setTab(x)}>
              {x === "list" ? t("dashboard.records") : x === "detail" ? "Detail" : t(`dashboard.${x}`)}
            </button>
          ))}
        </nav>

        <section className={`pane list ${tab === "list" ? "mobile-active" : ""}`}>
          <div className="stack">
            <div className="row">
              <h2 style={{ margin: 0 }}>{t("dashboard.records")}</h2>
              <span className="badge">{visible.length}</span>
            </div>
            <input placeholder={t("app.search")} value={q} onChange={(e) => setQ(e.target.value)} />
            <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="">{t("dashboard.allTypes")}</option>
              {RECORD_TYPES.map((x) => <option key={x} value={x}>{t(`types.${x}`)}</option>)}
            </select>
            {regionFilter && (
              <button className="chip" onClick={() => setRegionFilter(null)} title={t("dashboard.clearRegion")}>
                {t("dashboard.regionFilter", { region: regionLabel(regions, regionFilter, lang, t) })} ✕
              </button>
            )}
            {error && <div className="error">{error}</div>}
            {visible.length === 0 && <div className="muted">{t("dashboard.noRecords")}</div>}
            <div>
              {visible.map((r) => (
                <button key={r.id}
                  className={`record-item ${r.id === selectedId ? "selected" : ""} ${r.review_state === "draft" ? "draft" : ""}`}
                  onClick={() => select(r.id)}>
                  <TypeDot type={r.type} />
                  <span>
                    <div className="title">{r.title}</div>
                    <div className="sub">
                      {r.date} · {t(`types.${r.type}`)}
                      {r.status ? ` · ${t(`enum.${r.status}`)}` : ""}
                      {r.origin !== "native" ? " · ↗" : ""}
                    </div>
                  </span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className={`pane body ${tab === "body" ? "mobile-active" : ""}`}>
          <h2>{t("dashboard.body")}</h2>
          <div className="body-placeholder">
            <svg viewBox="0 0 60 140" aria-hidden="true">
              <circle cx="30" cy="12" r="9" fill="currentColor" />
              <path d="M16 26h28l4 44h-8l-2 66h-8l-2-40-2 40h-8l-2-66h-8z" fill="currentColor" />
            </svg>
            <div className="muted">{t("dashboard.bodyComing")}</div>
            <div className="region-cloud">
              {regionCounts.length === 0 && <span className="muted">{t("dashboard.noRegions")}</span>}
              {regionCounts.map(([id, n]) => (
                <button key={id} className={`chip ${regionFilter === id ? "active" : ""}`}
                  onClick={() => { setRegionFilter(regionFilter === id ? null : id); setTab("list"); }}>
                  {regionLabel(regions, id, lang, t)} <span className="badge">{n}</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className={`pane detail ${tab === "detail" ? "mobile-active" : ""}`}>
          {selected ? (
            <RecordDetail record={selected} records={records} onEdit={() => setForm({ record: selected })}
              onSelect={select}
              onDeleted={() => { setSelectedId(null); void load(); }} />
          ) : (
            <div className="muted">{t("dashboard.selectRecord")}</div>
          )}
        </section>

        <section className={`pane timeline ${tab === "timeline" ? "mobile-active" : ""}`}>
          <div className="row"><h3 style={{ margin: 0 }}>{t("dashboard.timeline")}</h3>
            <span className="muted" style={{ fontSize: 12 }}>(M2: scrubber)</span></div>
          <div className="timeline-strip">
            {years.map(([y, rs]) => (
              <div key={y} className="timeline-year">
                <div className="dots">
                  {rs.map((r) => (
                    <button key={r.id} title={`${r.date} ${r.title}`} onClick={() => select(r.id)}
                      style={{ border: "none", padding: 0, background: "none", cursor: "pointer" }}>
                      <TypeDot type={r.type} />
                    </button>
                  ))}
                </div>
                {y}
              </div>
            ))}
          </div>
        </section>
      </main>

      {form && (
        <RecordForm
          record={form.record}
          records={records}
          onClose={() => setForm(null)}
          onSaved={(r) => { setForm(null); void load().then(() => select(r.id)); }}
        />
      )}
    </>
  );
}
