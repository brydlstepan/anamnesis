import { type FormEvent, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, ApiError, errorMessage } from "../lib/api";
import type { Meta } from "../lib/types";

export default function LoginPage({ meta, onLoggedIn }: { meta: Meta; onLoggedIn: () => Promise<void> }) {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const urlError = new URLSearchParams(window.location.search).get("login_error");
  const [error, setError] = useState<string | null>(urlError ? t(`login.errors.${urlError}`) : null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/api/v1/auth/login", { method: "POST", body: { email, password } });
      window.history.replaceState(null, "", "/");
      await onLoggedIn();
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("login.errors.invalid") : errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-page">
      <div className="card stack" style={{ width: "min(380px, 100%)" }}>
        <h1 style={{ color: "var(--accent)" }}>{t("app.name")}</h1>
        <h2>{t("login.title")}</h2>
        {error && <div className="error" role="alert">{error}</div>}
        {meta.oidc_enabled && (
          <>
            <a className="btn primary" style={{ justifyContent: "center" }} href="/api/v1/auth/oidc/login">
              {t("login.sso", { name: meta.oidc_display_name })}
            </a>
            <div className="muted" style={{ textAlign: "center" }}>{t("login.or")}</div>
          </>
        )}
        <form className="stack" onSubmit={submit}>
          <label className="field">
            <span>{t("login.email")}</span>
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="field">
            <span>{t("login.password")}</span>
            <input type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <button className={meta.oidc_enabled ? "btn" : "btn primary"} disabled={busy} type="submit">
            {t("login.submit")}
          </button>
        </form>
        <div className="muted" style={{ fontSize: 12 }}>{t("app.disclaimer")}</div>
      </div>
    </div>
  );
}
