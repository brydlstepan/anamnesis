import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";
import AdminApp from "./admin/AdminApp";
import { api, errorMessage } from "./lib/api";
import { hasStoredLanguage, setLanguage } from "./lib/i18n";
import type { Meta } from "./lib/types";
import UserApp from "./user/UserApp";

export default function App() {
  const { t } = useTranslation();
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();

  useEffect(() => {
    api<Meta>("/api/v1/meta")
      .then((m) => {
        if (!hasStoredLanguage()) setLanguage(m.default_language);
        setMeta(m);
      })
      .catch((e) => setError(errorMessage(e)));
  }, []);

  if (error) return <div className="center-page error">{t("app.error")}: {error}</div>;
  if (!meta) return <div className="center-page muted">{t("app.loading")}</div>;

  const isAdmin = location.pathname === meta.admin_path || location.pathname.startsWith(meta.admin_path + "/");
  return isAdmin ? <AdminApp meta={meta} /> : <UserApp meta={meta} />;
}
