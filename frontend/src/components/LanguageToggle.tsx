import { useI18n } from "../i18n";

export default function LanguageToggle() {
  const { lang, setLang } = useI18n();
  return (
    <div className="lang-toggle" role="group" aria-label="Language">
      <button
        type="button"
        className={lang === "sv" ? "selected" : ""}
        onClick={() => setLang("sv")}
        title="Svenska"
      >
        🇸🇪
      </button>
      <button
        type="button"
        className={lang === "en" ? "selected" : ""}
        onClick={() => setLang("en")}
        title="English"
      >
        🇺🇸
      </button>
    </div>
  );
}
