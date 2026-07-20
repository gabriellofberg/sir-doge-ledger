type Props = {
  title: string;
  hint: string;
};

export default function ChartPlaceholder({ title, hint }: Props) {
  return (
    <section className="panel chart-panel chart-placeholder">
      <h2>{title}</h2>
      <div className="chart-placeholder-body">
        <div className="chart-placeholder-bars" aria-hidden>
          <span style={{ height: "35%" }} />
          <span style={{ height: "55%" }} />
          <span style={{ height: "40%" }} />
          <span style={{ height: "70%" }} />
          <span style={{ height: "45%" }} />
          <span style={{ height: "60%" }} />
        </div>
        <p className="muted">{hint}</p>
      </div>
    </section>
  );
}
