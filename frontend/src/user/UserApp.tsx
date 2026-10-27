import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { api, ApiError, errorMessage, storage } from "../lib/api";
import { setLanguage } from "../lib/i18n";
import type { Lang, Me, Meta, Person, Region, TypeSchema } from "../lib/types";
import AccessLogPage from "./AccessLogPage";
import { Ctx, type UserCtx } from "./context";
import Dashboard from "./Dashboard";
import LoginPage from "./LoginPage";
import SettingsPage from "./SettingsPage";

export default function UserApp({ meta }: { meta: Meta }) {
  const { t, i18n } = useTranslation();
  const [me, setMe] = useState<Me | null | undefined>(undefined); // undefined = loading, null = logged out
  const [persons, setPersons] = useState<Person[]>([]);
  const [personId, setPersonId] = useState<string | null>(storage.get("anamnesis.person"));
  const [schema, setSchema] = useState<TypeSchema[]>([]);
  const [regions, setRegions] = useState<Region[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reloadMe = useCallback(async () => {
    try {
      const m = await api<Me>("/api/v1/auth/me");
      if (m.language && m.language !== i18n.language) setLanguage(m.language);
      setMe(m);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      else setError(errorMessage(e));
    }
  }, [i18n.language]);

  const reloadPersons = useCallback(async () => {
    setPersons(await api<Person[]>("/api/v1/persons"));
  }, []);

  useEffect(() => {
    void reloadMe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!me) return;
    Promise.all([
      reloadPersons(),
      api<{ types: TypeSchema[] }>("/api/v1/schema").then((s) => setSchema(s.types)),
      api<Region[]>("/api/v1/regions").then(setRegions),
    ]).catch((e) => setError(errorMessage(e)));
  }, [me, reloadPersons]);

  const person = useMemo(
    () => persons.find((p) => p.id === personId) ?? persons.find((p) => p.is_me) ?? persons[0] ?? null,
    [persons, personId],
  );

  const selectPerson = useCallback((id: string) => {
    storage.set("anamnesis.person", id);
    setPersonId(id);
  }, []);

  const logout = useCallback(async () => {
    await api("/api/v1/auth/logout", { method: "POST" });
    setMe(null);
    setPersons([]);
  }, []);

  if (error) return <div className="center-page error">{t("app.error")}: {error}</div>;
  if (me === undefined) return <div className="center-page muted">{t("app.loading")}</div>;
  if (me === null) return <LoginPage meta={meta} onLoggedIn={reloadMe} />;

  const ctx: UserCtx = {
    meta, me, persons, person, selectPerson, reloadPersons, reloadMe, schema, regions,
    lang: (i18n.language as Lang) ?? "cs", logout,
  };

  return (
    <Ctx.Provider value={ctx}>
      <div className="app-shell">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/access-log" element={<AccessLogPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        <footer className="footer">
          {t("app.disclaimer")} · Anamnesis {meta.version} · <Link to="/settings">{t("nav.settings")}</Link>
        </footer>
      </div>
    </Ctx.Provider>
  );
}
