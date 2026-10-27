import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { setLanguage } from "../lib/i18n";
import type { Lang } from "../lib/types";
import { useUser } from "./context";

export default function TopBar({ onAdd }: { onAdd?: () => void }) {
  const { t } = useTranslation();
  const { me, persons, person, selectPerson, logout, lang, reloadMe } = useUser();
  const navigate = useNavigate();
  const canEdit = person && person.role !== "viewer";

  async function changeLang(l: Lang) {
    setLanguage(l);
    await api("/api/v1/auth/me", { method: "PATCH", body: { language: l } });
    await reloadMe();
  }

  return (
    <header className="topbar">
      <Link to="/" className="brand">{t("app.name")}</Link>
      {persons.length > 0 && (
        <select aria-label={t("nav.profile")} value={person?.id ?? ""} onChange={(e) => selectPerson(e.target.value)}>
          {persons.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({t(`roles.${p.role}`)})
            </option>
          ))}
        </select>
      )}
      {onAdd && canEdit && (
        <button className="btn primary" onClick={onAdd}>+ {t("nav.addRecord")}</button>
      )}
      <span className="spacer" />
      {me.show_access_log && person?.role === "owner" && (
        <Link className="btn" to="/access-log">{t("nav.accessLog")}</Link>
      )}
      <select aria-label="Language" value={lang} onChange={(e) => void changeLang(e.target.value as Lang)} style={{ width: 64 }}>
        <option value="cs">CS</option>
        <option value="en">EN</option>
      </select>
      <Link className="btn" to="/settings">{t("nav.settings")}</Link>
      <button className="btn" onClick={() => void logout().then(() => navigate("/"))}>{t("nav.logout")}</button>
    </header>
  );
}
