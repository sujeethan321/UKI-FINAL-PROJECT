import { createInstance } from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import ta from "./locales/ta.json";
import si from "./locales/si.json";

import applicationEn from "./locales/application.en.json";
import applicationTa from "./locales/application.ta.json";
import applicationSi from "./locales/application.si.json";

export const LANGUAGE_STORAGE_KEY = "lankapex_ui_language";
export const SUPPORTED_LANGUAGES = Object.freeze(["en", "ta", "si"]);
export const resources = { en: { translation: en, application: applicationEn }, ta: { translation: ta, application: applicationTa }, si: { translation: si, application: applicationSi } };

export function readLanguage(storage) {
  try {
    const value = storage?.getItem(LANGUAGE_STORAGE_KEY);
    return SUPPORTED_LANGUAGES.includes(value) ? value : "en";
  } catch { return "en"; }
}

export function createAppI18n({ language = "en" } = {}) {
  const instance = createInstance();
  instance.use(initReactI18next).init({
    resources, lng: SUPPORTED_LANGUAGES.includes(language) ? language : "en",
    fallbackLng: "en", ns: ["translation", "application"], defaultNS: "translation", supportedLngs: SUPPORTED_LANGUAGES, load: "languageOnly",
    initAsync: false, interpolation: { escapeValue: false },
    returnEmptyString: true, debug: false, saveMissing: false,
    react: { useSuspense: false },
  });
  return instance;
}

export function bindLanguagePreference(instance, storage, document) {
  const sync = language => {
    const safe = SUPPORTED_LANGUAGES.includes(language) ? language : "en";
    if (document?.documentElement) document.documentElement.lang = safe;
    try { storage?.setItem(LANGUAGE_STORAGE_KEY, safe); } catch { /* Storage may be blocked. */ }
  };
  sync(instance.resolvedLanguage || instance.language);
  instance.on("languageChanged", sync);
  return () => instance.off("languageChanged", sync);
}

let storage;
try { if (typeof window !== "undefined") storage = window.localStorage; } catch { /* English fallback. */ }
const i18n = createAppI18n({ language: readLanguage(storage) });
if (typeof document !== "undefined") bindLanguagePreference(i18n, storage, document);
export default i18n;
