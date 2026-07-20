import { useEffect, useState } from "react";

const KEY = "sir-doge-privacy-ack";

export default function PrivacyBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(!localStorage.getItem(KEY));
  }, []);

  if (!visible) return null;

  return (
    <div className="privacy-banner" role="alert">
      <div>
        <strong>SirDoge Ledger runs entirely on this machine.</strong> Bank exports and
        categories are stored locally under your user profile. Lock your computer when away.
        Nothing is sent to the cloud.
      </div>
      <button
        type="button"
        onClick={() => {
          localStorage.setItem(KEY, "1");
          setVisible(false);
        }}
      >
        Understood
      </button>
    </div>
  );
}
