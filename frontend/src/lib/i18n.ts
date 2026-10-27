import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import cs from "../locales/cs.json";
import en from "../locales/en.json";
import { storage } from "./api";
import type { Lang } from "./types";

const saved = storage.get("anamnesis.lang") as Lang | null;

void i18n.use(initReactI18next).init({
  resources: { cs: { translation: cs }, en: { translation: en } },
  lng: saved ?? "cs",
  fallbackLng: "en",
  interpolation: { escapeValue: false }, // React escapes
  returnNull: false,
});

export function setLanguage(lang: Lang) {
  storage.set("anamnesis.lang", lang);
  void i18n.changeLanguage(lang);
  document.documentElement.lang = lang;
}

export function hasStoredLanguage(): boolean {
  return storage.get("anamnesis.lang") !== null;
}

export default i18n;
