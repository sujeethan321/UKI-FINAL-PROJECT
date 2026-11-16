import { Globe2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { SUPPORTED_LANGUAGES } from "../i18n";
import "./LanguageSelector.css";

export default function LanguageSelector() {
  const { t, i18n } = useTranslation();
  return <label className="landing-language lankapex-language-selector">
    <Globe2 size={21} aria-hidden="true" />
    <span className="lankapex-language-label">{t("language")}</span>
    <select value={i18n.resolvedLanguage || "en"} onChange={event => {
      if (SUPPORTED_LANGUAGES.includes(event.target.value)) void i18n.changeLanguage(event.target.value);
    }}>
      <option value="en" lang="en">English</option>
      <option value="ta" lang="ta">தமிழ்</option>
      <option value="si" lang="si">සිංහල</option>
    </select>
  </label>;
}
