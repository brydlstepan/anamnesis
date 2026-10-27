import { type FormEvent, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage } from "../lib/api";
import { RECORD_TYPES, type Attachment, type FieldDef, type MedRecord, type RecordType, type RegionRef } from "../lib/types";
import { useUser } from "./context";
import RegionPicker from "./RegionPicker";
import { TypeDot } from "./ui";

type Range = { low: string; high: string; text: string };
type Raw = string | string[] | RegionRef[] | Range;

// ---- conversion between API values and form inputs -------------------------------------------

function toRaw(f: FieldDef, v: unknown): Raw {
  switch (f.kind) {
    case "regions":
      return (v as RegionRef[]) ?? [];
    case "links":
      return (v as string[]) ?? [];
    case "tags":
      return ((v as string[]) ?? []).join(", ");
    case "list":
      return ((v as unknown[]) ?? []).map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join("\n");
    case "codes":
      return ((v as { system: string; code: string; display?: string }[]) ?? [])
        .map((c) => `${c.system}:${c.code}${c.display ? " " + c.display : ""}`).join("\n");
    case "range": {
      const r = (v as { low?: number; high?: number; text?: string }) ?? {};
      return { low: r.low?.toString() ?? "", high: r.high?.toString() ?? "", text: r.text ?? "" };
    }
    default:
      return v === null || v === undefined ? "" : String(v);
  }
}

function fromRaw(f: FieldDef, raw: Raw): unknown {
  const s = typeof raw === "string" ? raw.trim() : "";
  switch (f.kind) {
    case "regions":
    case "links":
      return raw;
    case "tags":
      return s ? s.split(",").map((x) => x.trim()).filter(Boolean) : [];
    case "list":
      return s ? s.split("\n").map((x) => x.trim()).filter(Boolean).map((x) => {
        if (x.startsWith("{")) { try { return JSON.parse(x); } catch { return x; } }
        return x;
      }) : [];
    case "codes":
      return s ? s.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
        const [head, ...rest] = l.split(" ");
        const [system, ...code] = head.split(":");
        return { system, code: code.join(":"), ...(rest.length ? { display: rest.join(" ") } : {}) };
      }) : [];
    case "range": {
      const r = raw as Range;
      const out: Record<string, unknown> = {};
      if (r.low.trim()) out.low = Number(r.low.replace(",", "."));
      if (r.high.trim()) out.high = Number(r.high.replace(",", "."));
      if (r.text.trim()) out.text = r.text.trim();
      return Object.keys(out).length ? out : null;
    }
    case "number":
      return s ? Number(s.replace(",", ".")) : null;
    case "text_or_number": {
      const n = Number(s.replace(",", "."));
      return s && /^-?\d+([.,]\d+)?$/.test(s) && !Number.isNaN(n) ? n : s || null;
    }
    default:
      return s || null;
  }
}

const isEmpty = (raw: Raw) =>
  Array.isArray(raw) ? raw.length === 0 : typeof raw === "string" ? !raw.trim() : !raw.low && !raw.high && !raw.text;

// ---- component -----------------------------------------------------------------------------------

export default function RecordForm({ record, records, onClose, onSaved }: {
  record: MedRecord | null;
  records: MedRecord[];
  onClose: () => void;
  onSaved: (r: MedRecord) => void;
}) {
  const { t } = useTranslation();
  const { schema, person } = useUser();
  const [type, setType] = useState<RecordType | null>(record?.type ?? null);
  const fields = useMemo(() => schema.find((s) => s.type === type)?.fields ?? [], [schema, type]);
  const [values, setValues] = useState<Record<string, Raw>>({});
  const [shown, setShown] = useState<Set<string>>(new Set());
  const [attachments, setAttachments] = useState<Attachment[]>(record?.attachments ?? []);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [initialised, setInitialised] = useState<string | null>(null);

  // initialise values once the schema for the type is known
  if (type && fields.length && initialised !== type) {
    const v: Record<string, Raw> = {};
    const s = new Set<string>();
    for (const f of fields) {
      if (f.kind === "attachments") continue;
      v[f.name] = toRaw(f, record?.[f.name]);
      if (f.required || !isEmpty(v[f.name])) s.add(f.name);
    }
    setValues(v);
    setShown(s);
    setInitialised(type);
  }

  const set = (name: string, raw: Raw) => setValues((prev) => ({ ...prev, [name]: raw }));
  const hidden = fields.filter((f) => !shown.has(f.name) && f.kind !== "attachments");
  const needsFile = fields.some((f) => f.kind === "attachments" && f.required);

  async function upload(file: File) {
    if (!person) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const att = await api<Attachment>(`/api/v1/persons/${person.id}/attachments`, { method: "POST", form });
      setAttachments((a) => [...a, att]);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function removeAttachment(a: Attachment) {
    setAttachments((list) => list.filter((x) => x.id !== a.id));
    const isNew = !record?.attachments.some((x) => x.id === a.id);
    if (isNew) await api(`/api/v1/attachments/${a.id}`, { method: "DELETE" }).catch(() => undefined);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!person || !type) return;
    const payload: Record<string, unknown> = { type, attachment_ids: attachments.map((a) => a.id) };
    for (const f of fields) {
      if (f.kind === "attachments" || !shown.has(f.name)) continue;
      const v = fromRaw(f, values[f.name]);
      if (v !== null && !(Array.isArray(v) && v.length === 0)) payload[f.name] = v;
    }
    if (record?.extra) payload.extra = record.extra;
    setBusy(true);
    setErrors({});
    setError(null);
    try {
      const saved = record
        ? await api<MedRecord>(`/api/v1/records/${record.id}`, { method: "PUT", body: payload })
        : await api<MedRecord>(`/api/v1/persons/${person.id}/records`, { method: "POST", body: payload });
      onSaved(saved);
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fieldErrors).length) setErrors(err.fieldErrors);
      else setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function renderInput(f: FieldDef) {
    const raw = values[f.name] ?? toRaw(f, undefined);
    switch (f.kind) {
      case "textarea":
        return <textarea value={raw as string} onChange={(e) => set(f.name, e.target.value)} />;
      case "enum":
        return (
          <select value={raw as string} onChange={(e) => set(f.name, e.target.value)} required={f.required}>
            <option value="">—</option>
            {f.options.map((o) => <option key={o} value={o}>{t(`enum.${o}`)}</option>)}
          </select>
        );
      case "date":
        return <input value={raw as string} placeholder={t("form.datePlaceholder")} inputMode="numeric"
          onChange={(e) => set(f.name, e.target.value)} required={f.required} />;
      case "number":
        return <input value={raw as string} inputMode="decimal" onChange={(e) => set(f.name, e.target.value)} />;
      case "regions":
        return <RegionPicker value={raw as RegionRef[]} onChange={(v) => set(f.name, v)} />;
      case "links":
        return (
          <select multiple value={raw as string[]} style={{ minHeight: 80 }}
            onChange={(e) => set(f.name, [...e.target.selectedOptions].map((o) => o.value))}>
            {records.filter((r) => r.id !== record?.id).map((r) => (
              <option key={r.id} value={r.id}>{r.date} — {r.title}</option>
            ))}
          </select>
        );
      case "codes":
        return <textarea value={raw as string} placeholder={t("form.codesHint")} style={{ minHeight: 60 }}
          onChange={(e) => set(f.name, e.target.value)} />;
      case "list":
        return <textarea value={raw as string} placeholder={t("form.listHint")} style={{ minHeight: 60 }}
          onChange={(e) => set(f.name, e.target.value)} />;
      case "tags":
        return <input value={raw as string} placeholder={t("form.tagsHint")} onChange={(e) => set(f.name, e.target.value)} />;
      case "range": {
        const r = raw as Range;
        return (
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input placeholder={t("form.rangeLow")} value={r.low} inputMode="decimal" onChange={(e) => set(f.name, { ...r, low: e.target.value })} />
            <input placeholder={t("form.rangeHigh")} value={r.high} inputMode="decimal" onChange={(e) => set(f.name, { ...r, high: e.target.value })} />
            <input placeholder={t("form.rangeText")} value={r.text} onChange={(e) => set(f.name, { ...r, text: e.target.value })} />
          </div>
        );
      }
      default:
        return <input value={raw as string} onChange={(e) => set(f.name, e.target.value)} required={f.required} />;
    }
  }

  const wide = new Set(["textarea", "regions", "codes", "list", "links", "range"]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal card stack" role="dialog" aria-modal="true">
        <div className="row">
          <h2 style={{ margin: 0 }}>{record ? t("form.editRecord") : t("form.newRecord")}</h2>
          {type && <span className="badge"><TypeDot type={type} /> {t(`types.${type}`)}</span>}
          <span className="spacer" />
          <button className="btn" type="button" onClick={onClose}>{t("app.close")}</button>
        </div>

        {!type ? (
          <>
            <div className="muted">{t("form.chooseType")}</div>
            <div className="type-grid">
              {RECORD_TYPES.map((x) => (
                <button key={x} className="btn" type="button" onClick={() => setType(x)}>
                  <TypeDot type={x} /> {t(`types.${x}`)}
                </button>
              ))}
            </div>
          </>
        ) : (
          <form className="stack" onSubmit={submit} noValidate>
            <div className="form-grid">
              {fields.filter((f) => shown.has(f.name)).map((f) => (
                <label key={f.name} className={`field ${wide.has(f.kind) ? "full" : ""}`}>
                  <span>
                    {t(`fields.${f.name}`)}{f.required && <span className="req" title={t("form.required")}>*</span>}
                  </span>
                  {renderInput(f)}
                  {errors[f.name] && <span className="error" style={{ fontSize: 12 }}>{errors[f.name]}</span>}
                </label>
              ))}
            </div>

            {hidden.length > 0 && (
              <select value="" aria-label={t("form.addField")} style={{ width: "auto" }}
                onChange={(e) => e.target.value && setShown(new Set([...shown, e.target.value]))}>
                <option value="">{t("form.addField")}</option>
                {hidden.map((f) => <option key={f.name} value={f.name}>{t(`fields.${f.name}`)}</option>)}
              </select>
            )}

            <div className="stack" style={{ gap: 6 }}>
              <span className="muted" style={{ fontSize: 12 }}>
                {t("dashboard.attachments")}{needsFile && <span className="req">*</span>} · {t("form.uploadHint")}
              </span>
              {attachments.map((a) => (
                <span key={a.id} className="chip" style={{ alignSelf: "flex-start" }}>
                  {a.filename}
                  <button type="button" aria-label={t("app.remove")} onClick={() => void removeAttachment(a)}>✕</button>
                </span>
              ))}
              <input type="file" accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.glb" disabled={busy}
                onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
              {errors.file && <span className="error" style={{ fontSize: 12 }}>{errors.file}</span>}
            </div>

            {error && <div className="error" role="alert">{error}</div>}
            <div className="row">
              <span className="spacer" />
              <button className="btn" type="button" onClick={onClose}>{t("app.cancel")}</button>
              <button className="btn primary" type="submit" disabled={busy}>{t("app.save")}</button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
