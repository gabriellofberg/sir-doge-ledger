import { useEffect, useState } from "react";
import { useI18n } from "../i18n";

const KEY = "sir-doge-privacy-ack";

export default function PrivacyBanner() {
  const { t } = useI18n();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(!localStorage.getItem(KEY));
  }, []);

  if (!visible) return null;

  return (
    <div className="privacy-banner" role="alert">
      <div>
        <strong>{t.appName}.</strong> {t.privacy.body}
      </div>
      <button
        type="button"
        onClick={() => {
          localStorage.setItem(KEY, "1");
          setVisible(false);
        }}
      >
        {t.privacy.ok}
      </button>
    </div>
  );
}
