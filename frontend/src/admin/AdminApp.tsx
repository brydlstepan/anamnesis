import { type FormEvent, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage } from "../lib/api";
import { setLanguage } from "../lib/i18n";
import type { Lang, Meta } from "../lib/types";

interface AdminUser {
  id: string;
  email: string;
  display_name: string;
  auth_provider: "local" | "oidc";
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}
interface AdminSettings {
  user_directory_enabled: boolean;
  max_upload_mb: number;
  default_language: Lang;
  access_log_retention_days: number;
}
interface AuditRow { ts: string; actor_kind: string; actor: string; action: string; target: string | null; ip: string | null }

function AdminLogin({ onLoggedIn }: { onLoggedIn: () => void }) {
  const { t } = useTranslation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api("/api/admin/auth/login", { method: "POST", body: { username, password } });
      onLoggedIn();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="center-page">
      <form className="card stack" style={{ width: "min(360px, 100%)" }} onSubmit={submit}>
        <h1>{t("admin.login")}</h1>
        {error && <div className="error" role="alert">{error}</div>}
        <label className="field"><span>{t("admin.username")}</span>
          <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
        <label className="field"><span>{t("login.password")}</span>
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button className="btn primary" type="submit">{t("login.submit")}</button>
      </form>
    </div>
  );
}

function Users() {
  const { t, i18n } = useTranslation();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [form, setForm] = useState({ email: "", display_name: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => api<AdminUser[]>("/api/admin/users").then(setUsers).catch((e) => setError(errorMessage(e))), []);
  useEffect(() => { void load(); }, [load]);

  const run = async (fn: () => Promise<unknown>) => {
    setError(null);
    try { await fn(); await load(); } catch (e) { setError(errorMessage(e)); }
  };

  async function create(e: FormEvent) {
    e.preventDefault();
    await run(async () => {
      await api("/api/admin/users", { method: "POST", body: form });
      setForm({ email: "", display_name: "", password: "" });
    });
  }

  const resetPassword = (u: AdminUser) => {
    const pw = window.prompt(t("admin.newPasswordPrompt", { email: u.email }));
    if (pw) void run(() => api(`/api/admin/users/${u.id}`, { method: "PATCH", body: { password: pw } }));
  };
  const remove = (u: AdminUser) => {
    const typed = window.prompt(t("admin.deleteConfirm", { email: u.email }));
    if (typed) void run(() => api(`/api/admin/users/${u.id}`, { method: "DELETE", query: { confirm_email: typed } }));
  };
  const fmt = (d: string | null) => (d ? new Date(d).toLocaleString(i18n.language) : "—");

  return (
    <div className="stack">
      {error && <div className="error" role="alert">{error}</div>}
      <div className="card" style={{ overflowX: "auto" }}>
        {users.length === 0 ? <div className="muted">{t("admin.noUsers")}</div> : (
          <table>
            <thead><tr><th>{t("admin.email")}</th><th>{t("admin.provider")}</th><th>{t("admin.status")}</th>
              <th>{t("admin.lastLogin")}</th><th /></tr></thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}<br /><span className="muted">{u.display_name}</span></td>
                  <td><span className="badge">{u.auth_provider}</span></td>
                  <td>{u.is_active ? t("admin.active") : <span className="error">{t("admin.disabled")}</span>}</td>
                  <td>{fmt(u.last_login_at)}</td>
                  <td>
                    <div className="row" style={{ justifyContent: "flex-end" }}>
                      <button className="btn small" onClick={() => void run(() =>
                        api(`/api/admin/users/${u.id}`, { method: "PATCH", body: { is_active: !u.is_active } }))}>
                        {u.is_active ? t("admin.disable") : t("admin.enable")}</button>
                      {u.auth_provider === "local" && (
                        <button className="btn small" onClick={() => resetPassword(u)}>{t("admin.resetPassword")}</button>)}
                      <button className="btn small danger" onClick={() => remove(u)}>{t("admin.deleteUser")}</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <form className="card stack" onSubmit={create}>
        <h2>{t("admin.createUser")}</h2>
        <div className="form-grid">
          <label className="field"><span>{t("admin.email")}</span>
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></label>
          <label className="field"><span>{t("admin.displayName")}</span>
            <input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></label>
          <label className="field full"><span>{t("admin.password")}</span>
            <input type="password" autoComplete="new-password" minLength={12} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} required /></label>
        </div>
        <div className="row"><span className="spacer" /><button className="btn primary" type="submit">{t("app.add")}</button></div>
      </form>
    </div>
  );
}

function SettingsTab() {
  const { t } = useTranslation();
  const [s, setS] = useState<AdminSettings | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { void api<AdminSettings>("/api/admin/settings").then(setS); }, []);
  if (!s) return null;

  async function save(e: FormEvent) {
    e.preventDefault();
    try {
      setS(await api<AdminSettings>("/api/admin/settings", { method: "PUT", body: s }));
      setMsg(t("settings.saved"));
    } catch (err) {
      setMsg(errorMessage(err));
    }
  }

  return (
    <form className="card stack" onSubmit={save}>
      <label className="row"><input type="checkbox" checked={s.user_directory_enabled}
        onChange={(e) => setS({ ...s, user_directory_enabled: e.target.checked })} /> {t("admin.userDirectory")}</label>
      <div className="form-grid">
        <label className="field"><span>{t("admin.maxUpload")}</span>
          <input type="number" min={1} max={2048} value={s.max_upload_mb}
            onChange={(e) => setS({ ...s, max_upload_mb: Number(e.target.value) })} /></label>
        <label className="field"><span>{t("admin.defaultLanguage")}</span>
          <select value={s.default_language} onChange={(e) => setS({ ...s, default_language: e.target.value as Lang })}>
            <option value="cs">Čeština</option><option value="en">English</option></select></label>
        <label className="field"><span>{t("admin.retention")}</span>
          <input type="number" min={30} max={3650} value={s.access_log_retention_days}
            onChange={(e) => setS({ ...s, access_log_retention_days: Number(e.target.value) })} /></label>
      </div>
      <div className="row"><span className="spacer" />{msg && <span className="muted">{msg}</span>}
        <button className="btn primary" type="submit">{t("app.save")}</button></div>
    </form>
  );
}

function AuditTab() {
  const { t, i18n } = useTranslation();
  const [rows, setRows] = useState<AuditRow[]>([]);
  useEffect(() => { void api<AuditRow[]>("/api/admin/audit").then(setRows); }, []);
  return (
    <div className="card" style={{ overflowX: "auto" }}>
      <table>
        <thead><tr><th>{t("accessLog.when")}</th><th>{t("accessLog.who")}</th><th>{t("accessLog.what")}</th><th>IP</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{new Date(r.ts).toLocaleString(i18n.language)}</td>
              <td>{r.actor} <span className="badge">{r.actor_kind}</span></td>
              <td>{r.action}{r.target ? ` · ${r.target}` : ""}</td>
              <td className="muted">{r.ip}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AdminApp({ meta }: { meta: Meta }) {
  const { t, i18n } = useTranslation();
  const [admin, setAdmin] = useState<string | null | undefined>(undefined);
  const [tab, setTab] = useState<"users" | "settings" | "audit">("users");

  const check = useCallback(() => {
    api<{ username: string }>("/api/admin/auth/me")
      .then((a) => setAdmin(a.username))
      .catch((e) => setAdmin(e instanceof ApiError && e.status === 401 ? null : undefined));
  }, []);
  useEffect(check, [check]);

  if (admin === undefined) return <div className="center-page muted">{t("app.loading")}</div>;
  if (admin === null) return <AdminLogin onLoggedIn={check} />;

  return (
    <div className="app-shell">
      <header className="topbar">
        <span className="brand">{t("app.name")}</span>
        <strong>{t("admin.title")}</strong>
        <nav className="admin-tabs">
          {(["users", "settings", "audit"] as const).map((x) => (
            <button key={x} className={`btn ${tab === x ? "active" : ""}`} onClick={() => setTab(x)}>{t(`admin.${x}`)}</button>
          ))}
        </nav>
        <span className="spacer" />
        <select value={i18n.language} onChange={(e) => setLanguage(e.target.value as Lang)} style={{ width: 64 }}>
          <option value="cs">CS</option><option value="en">EN</option>
        </select>
        <span className="muted hide-mobile">{admin}</span>
        <button className="btn" onClick={() => void api("/api/admin/auth/logout", { method: "POST" }).then(() => setAdmin(null))}>
          {t("nav.logout")}</button>
      </header>
      <main className="settings-page" style={{ maxWidth: 1000 }}>
        <div className="banner">{t("admin.noMedicalData")}</div>
        {tab === "users" && <Users />}
        {tab === "settings" && <SettingsTab />}
        {tab === "audit" && <AuditTab />}
      </main>
      <footer className="footer">Anamnesis {meta.version} · {meta.admin_path}</footer>
    </div>
  );
}
