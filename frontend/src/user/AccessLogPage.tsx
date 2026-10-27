import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, errorMessage } from "../lib/api";
import { useUser } from "./context";
import TopBar from "./TopBar";

interface Event { ts: string; actor: string; action: string; target: string | null; via: string }

export default function AccessLogPage() {
  const { t, i18n } = useTranslation();
  const { persons } = useUser();
  const own = persons.find((p) => p.is_me);
  const [events, setEvents] = useState<Event[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (own) api<Event[]>(`/api/v1/persons/${own.id}/access-log`).then(setEvents).catch((e) => setError(errorMessage(e)));
  }, [own]);

  return (
    <>
      <TopBar />
      <main className="settings-page">
        <h1>{t("accessLog.title")}</h1>
        {error && <div className="error">{error}</div>}
        <div className="card">
          {events?.length === 0 && <div className="muted">{t("accessLog.empty")}</div>}
          {events && events.length > 0 && (
            <table>
              <thead><tr><th>{t("accessLog.when")}</th><th>{t("accessLog.who")}</th><th>{t("accessLog.what")}</th></tr></thead>
              <tbody>
                {events.map((e, i) => (
                  <tr key={i}>
                    <td>{new Date(e.ts).toLocaleString(i18n.language)}</td>
                    <td>{e.actor} <span className="badge">{e.via}</span></td>
                    <td>{e.action}{e.target ? ` · ${e.target}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </>
  );
}
