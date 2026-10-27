import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../lib/api";
import type { MedRecord } from "../lib/types";
import { regionLabel, useUser } from "./context";
import { TypeDot } from "./ui";

const HIDDEN = new Set([
  "id", "person_id", "type", "title", "date", "regions", "attachments", "review_state", "origin",
  "editable", "version", "created_at", "updated_at", "status",
]);

function formatValue(v: unknown, t: (k: string) => string): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) {
    return v.map((x) => (typeof x === "object" && x !== null && "code" in x
      ? `${(x as { system: string }).system}:${(x as { code: string }).code} ${(x as { display?: string }).display ?? ""}`.trim()
      : typeof x === "object" ? JSON.stringify(x) : String(x))).join("\n");
  }
  if (typeof v === "object") {
    const o = v as { low?: number; high?: number; text?: string };
    if ("low" in o || "high" in o || "text" in o) return o.text ?? `${o.low ?? ""} – ${o.high ?? ""}`;
    return JSON.stringify(v, null, 1);
  }
  const s = String(v);
  const translated = t(`enum.${s}`);
  return translated.startsWith("enum.") ? s : translated;
}

export default function RecordDetail({ record, records, onEdit, onDeleted, onSelect }: {
  record: MedRecord;
  records: MedRecord[];
  onEdit: () => void;
  onDeleted: () => void;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  const { regions, lang } = useUser();
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    if (!window.confirm(t("form.deleteConfirm"))) return;
    try {
      await api(`/api/v1/records/${record.id}`, { method: "DELETE" });
      onDeleted();
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const titleOf = (id: string) => records.find((r) => r.id === id)?.title ?? id;
  const extraFields = Object.entries(record).filter(([k, v]) => !HIDDEN.has(k) && v !== null && v !== "" &&
    !(Array.isArray(v) && v.length === 0));

  return (
    <div className="stack">
      <div className="row">
        <TypeDot type={record.type} />
        <span className="badge">{t(`types.${record.type}`)}</span>
        {record.status && <span className="badge">{t(`enum.${record.status}`)}</span>}
        <span className="spacer" />
        {record.editable && (
          <>
            <button className="btn small" onClick={onEdit}>{t("app.edit")}</button>
            <button className="btn small danger" onClick={() => void remove()}>{t("app.delete")}</button>
          </>
        )}
      </div>
      <h2 style={{ margin: 0 }}>{record.title}</h2>
      <div className="muted">{record.date}{record.end_date ? ` – ${String(record.end_date)}` : ""}</div>
      {record.review_state === "draft" && <div className="banner">{t("dashboard.draft")}</div>}
      {record.origin !== "native" && (
        <div className="banner">{t("dashboard.readOnly", { source: record.origin.replace("source:", "") })}</div>
      )}
      {error && <div className="error">{error}</div>}
      {record.regions.length > 0 && (
        <div className="row">
          {record.regions.map((r, i) => <span key={i} className="chip">{regionLabel(regions, r, lang, t)}</span>)}
        </div>
      )}
      <dl className="fields">
        {extraFields.map(([k, v]) => (
          <div key={k} style={{ display: "contents" }}>
            <dt>{t(`fields.${k}`)}</dt>
            <dd>
              {(k === "links" || k === "reason") && Array.isArray(v)
                ? v.map((id) => (
                  <div key={String(id)}><button className="btn link" onClick={() => onSelect(String(id))}>
                    {titleOf(String(id))}</button></div>))
                : formatValue(v, t)}
            </dd>
          </div>
        ))}
      </dl>
      {record.attachments.length > 0 && (
        <div className="stack">
          <h3 style={{ margin: 0 }}>{t("dashboard.attachments")}</h3>
          {record.attachments.map((a) => (
            <a key={a.id} href={a.url} target="_blank" rel="noopener noreferrer">
              {a.filename} <span className="muted">({Math.ceil(a.size / 1024)} kB)</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
