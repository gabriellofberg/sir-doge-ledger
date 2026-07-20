export default function HeroBanner() {
  return (
    <section className="hero" aria-label="SirDoge Ledger">
      <div className="hero-img-wrap">
        <img src="/sir-doge-hero.png" alt="Sir Doge — meme Doge as private banker" className="hero-img" />
        <div className="hero-overlay" />
      </div>
      <div className="hero-text">
        <p className="hero-tag">private banker · local only · such finance</p>
        <h1 className="hero-title">SirDoge Ledger</h1>
        <p className="hero-sub">much budget · very audit · wow</p>
      </div>
    </section>
  );
}
