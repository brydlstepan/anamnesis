import { type FormEvent, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage } from "../lib/api";
import { setLanguage } from "../lib/i18n";
import type { EmergencyContact, Lang, Person, Share } from "../lib/types";
import { useUser } from "./context";
import TopBar from "./TopBar";

const BLOOD = ["0+", "0-", "A+", "A-", "B+", "B-", "AB+", "AB-"];

function Status({ msg }: { msg: { ok: boolean; text: string } | null }) {
  if (!msg) return null;
  return <span className={msg.ok ? "ok" : "error"} role="status">{msg.text}</span>;
}

function ProfileCard({ person }: { person: Person }) {
  const { t } = useTranslation();
  const { reloadPersons } = useUser();
  const [p, setP] = useState(person);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const canEdit = person.role !== "viewer";
  useEffect(() => setP(person), [person]);

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api(`/api/v1/persons/${person.id}`, {
        method: "PATCH",
        body: {
          name: p.name, birth_date: p.birth_date || null, sex: p.sex || null, body_model: p.body_model,
          blood_type: p.blood_type || null, organ_donation: p.organ_donation || null,
          emergency_contacts: p.emergency_contacts.filter((c) => c.name.trim()),
        },
      });
      await reloadPersons();
      setMsg({ ok: true, text: t("settings.saved") });
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) });
    }
  }

  const setContact = (i: number, c: Partial<EmergencyContact>) =>
    setP({ ...p, emergency_contacts: p.emergency_contacts.map((x, j) => (j === i ? { ...x, ...c } : x)) });

  return (
    <form className="card stack" onSubmit={save}>
      <h2>{t("settings.profile")} — {person.name}</h2>
      <fieldset disabled={!canEdit} style={{ border: "none", padding: 0, margin: 0 }} className="stack">
        <div className="form-grid">
          <label className="field"><span>{t("settings.name")}</span>
            <input value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} required /></label>
          <label className="field"><span>{t("settings.birthDate")}</span>
            <input type="date" value={p.birth_date ?? ""} onChange={(e) => setP({ ...p, birth_date: e.target.value })} /></label>
          <label className="field"><span>{t("settings.sex")}</span>
            <select value={p.sex ?? ""} onChange={(e) => setP({ ...p, sex: (e.target.value || null) as Person["sex"] })}>
              <option value="">{t("settings.none")}</option>
              {(["male", "female", "other", "unknown"] as const).map((s) => <option key={s} value={s}>{t(`settings.sexes.${s}`)}</option>)}
            </select></label>
          <label className="field"><span title={t("settings.bodyModelHint")}>{t("settings.bodyModel")}</span>
            <select value={p.body_model} onChange={(e) => setP({ ...p, body_model: e.target.value as Person["body_model"] })}>
              {(["male", "female"] as const).map((s) => <option key={s} value={s}>{t(`settings.bodyModels.${s}`)}</option>)}
            </select></label>
          <label className="field"><span>{t("settings.bloodType")}</span>
            <select value={p.blood_type ?? ""} onChange={(e) => setP({ ...p, blood_type: e.target.value || null })}>
              <option value="">{t("settings.none")}</option>
              {BLOOD.map((b) => <option key={b} value={b}>{b}</option>)}
            </select></label>
          <label className="field"><span>{t("settings.organDonation")}</span>
            <input value={p.organ_donation ?? ""} onChange={(e) => setP({ ...p, organ_donation: e.target.value })} /></label>
        </div>
        <h3>{t("settings.contacts")}</h3>
        {p.emergency_contacts.map((c, i) => (
          <div key={i} className="row" style={{ flexWrap: "nowrap" }}>
            <input placeholder={t("settings.contactName")} value={c.name} onChange={(e) => setContact(i, { name: e.target.value })} />
            <input placeholder={t("settings.phone")} value={c.phone} onChange={(e) => setContact(i, { phone: e.target.value })} />
            <input placeholder={t("settings.relation")} value={c.relation} onChange={(e) => setContact(i, { relation: e.target.value })} />
            <button type="button" className="btn small" onClick={() =>
              setP({ ...p, emergency_contacts: p.emergency_contacts.filter((_, j) => j !== i) })}>✕</button>
          </div>
        ))}
        <div className="row">
          <button type="button" className="btn small" onClick={() =>
            setP({ ...p, emergency_contacts: [...p.emergency_contacts, { name: "", phone: "", relation: "" }] })}>
            {t("settings.addContact")}</button>
          <span className="spacer" />
          <Status msg={msg} />
          <button className="btn primary" type="submit">{t("app.save")}</button>
        </div>
      </fieldset>
    </form>
  );
}

function AccountCard() {
  const { t } = useTranslation();
  const { me, reloadMe } = useUser();
  const [name, setName] = useState(me.display_name);
  const [lang, setLang] = useState<Lang>(me.language ?? "cs");
  const [showLog, setShowLog] = useState(me.show_access_log);
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/api/v1/auth/me", { method: "PATCH", body: { display_name: name, language: lang, show_access_log: showLog } });
      setLanguage(lang);
      await reloadMe();
      setMsg({ ok: true, text: t("settings.saved") });
    } catch (err) {
      setMsg({ ok: false, text: errorMessage(err) });
    }
  }

  async function changePassword(e: FormEvent) {
    e.preventDefault();
    try {
      await api("/api/v1/auth/me/password", { method: "POST", body: { current_password: cur, new_password: next } });
      setCur(""); setNext("");
      setPwMsg({ ok: true, text: t("settings.saved") });
    } catch (err) {
      setPwMsg({ ok: false, text: errorMessage(err) });
    }
  }

  return (
    <div className="card stack">
      <h2>{t("settings.account")} — {me.email}</h2>
      <form className="stack" onSubmit={save}>
        <div className="form-grid">
          <label className="field"><span>{t("settings.displayName")}</span>
            <input value={name} onChange={(e) => setName(e.target.value)} /></label>
          <label className="field"><span>{t("settings.language")}</span>
            <select value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
              <option value="cs">Čeština</option><option value="en">English</option>
            </select></label>
        </div>
        <label className="row"><input type="checkbox" checked={showLog} onChange={(e) => setShowLog(e.target.checked)} />
          {t("settings.showAccessLog")}</label>
        <div className="row"><span className="spacer" /><Status msg={msg} />
          <button className="btn primary" type="submit">{t("app.save")}</button></div>
      </form>
      {me.auth_provider === "local" && (
        <form className="stack" onSubmit={changePassword}>
          <h3>{t("settings.changePassword")}</h3>
          <div className="form-grid">
            <label className="field"><span>{t("settings.currentPassword")}</span>
              <input type="password" autoComplete="current-password" value={cur} onChange={(e) => setCur(e.target.value)} required /></label>
            <label className="field"><span>{t("settings.newPassword")}</span>
              <input type="password" autoComplete="new-password" minLength={12} value={next} onChange={(e) => setNext(e.target.value)} required /></label>
          </div>
          <div className="row"><span className="spacer" /><Status msg={pwMsg} />
            <button className="btn" type="submit">{t("settings.changePassword")}</button></div>
        </form>
      )}
    </div>
  );
}

function SharingCard({ personId }: { personId: string }) {
  const { t } = useTranslation();
  const [shares, setShares] = useState<Share[]>([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"viewer" | "editor">("viewer");
  const [directory, setDirectory] = useState<{ email: string; display_name: string }[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<Share[]>(`/api/v1/persons/${personId}/shares`).then(setShares).catch((e) => setError(errorMessage(e)));
  useEffect(() => {
    void load();
    api<{ email: string; display_name: string }[]>("/api/v1/users/directory")
      .then(setDirectory)
      .catch((e) => { if (!(e instanceof ApiError && e.status === 403)) setError(errorMessage(e)); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [personId]);

  async function add(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api(`/api/v1/persons/${personId}/shares`, { method: "POST", body: { email, role } });
      setEmail("");
      await load();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function update(s: Share, newRole: "viewer" | "editor") {
    await api(`/api/v1/shares/${s.id}`, { method: "PATCH", body: { role: newRole } }).catch((e) => setError(errorMessage(e)));
    await load();
  }

  async function revoke(s: Share) {
    if (!window.confirm(t("settings.revokeConfirm", { email: s.email }))) return;
    await api(`/api/v1/shares/${s.id}`, { method: "DELETE" }).catch((e) => setError(errorMessage(e)));
    await load();
  }

  return (
    <div className="card stack">
      <h2>{t("settings.sharing")}</h2>
      <div className="muted">{t("settings.sharingHint")}</div>
      {shares.length === 0 ? <div className="muted">{t("settings.noShares")}</div> : (
        <table>
          <tbody>
            {shares.map((s) => (
              <tr key={s.id}>
                <td>{s.display_name ? `${s.display_name} — ` : ""}{s.email}<br />
                  <span className="muted" style={{ fontSize: 12 }}>{t(`settings.${s.status}`)}</span></td>
                <td style={{ width: 130 }}>
                  <select value={s.role} onChange={(e) => void update(s, e.target.value as "viewer" | "editor")}>
                    <option value="viewer">{t("roles.viewer")}</option>
                    <option value="editor">{t("roles.editor")}</option>
                  </select>
                </td>
                <td style={{ width: 90 }}><button className="btn small danger" onClick={() => void revoke(s)}>{t("settings.revoke")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <form className="row" onSubmit={add} style={{ flexWrap: "nowrap" }}>
        <input type="email" placeholder={t("settings.shareEmail")} value={email} onChange={(e) => setEmail(e.target.value)}
          list={directory ? "user-directory" : undefined} required />
        {directory && (
          <datalist id="user-directory">
            {directory.map((u) => <option key={u.email} value={u.email}>{u.display_name}</option>)}
          </datalist>
        )}
        <select value={role} onChange={(e) => setRole(e.target.value as "viewer" | "editor")} style={{ width: 130 }}>
          <option value="viewer">{t("roles.viewer")}</option>
          <option value="editor">{t("roles.editor")}</option>
        </select>
        <button className="btn primary" type="submit">{t("settings.share")}</button>
      </form>
      {error && <div className="error">{error}</div>}
    </div>
  );
}

export default function SettingsPage() {
  const { t } = useTranslation();
  const { person, persons } = useUser();
  const own = persons.find((p) => p.is_me);
  return (
    <>
      <TopBar />
      <main className="settings-page">
        <h1>{t("settings.title")}</h1>
        {person && <ProfileCard person={person} />}
        <AccountCard />
        {own && <SharingCard personId={own.id} />}
      </main>
    </>
  );
}
