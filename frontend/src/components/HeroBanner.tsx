import { useI18n } from "../i18n";

export default function HeroBanner() {
  const { t } = useI18n();
  return (
    <section className="hero" aria-label={t.appName}>
      <div className="hero-img-wrap">
        <img src="/sir-doge-hero.png" alt="Sir Doge" className="hero-img" />
        <div className="hero-overlay" />
      </div>
      <div className="hero-text">
        <p className="hero-tag">{t.hero.tag}</p>
        <h1 className="hero-title">{t.appName}</h1>
        <p className="hero-sub">{t.hero.sub}</p>
      </div>
    </section>
  );
}
