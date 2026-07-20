import { Link } from "react-router-dom";

type Props = {
  title: string;
  description: string;
  actionLabel?: string;
  actionTo?: string;
};

export default function EmptyState({ title, description, actionLabel, actionTo }: Props) {
  return (
    <section className="empty-state-panel">
      <div className="empty-state-icon" aria-hidden>
        ◌
      </div>
      <h2>{title}</h2>
      <p className="muted">{description}</p>
      {actionLabel && actionTo && (
        <Link to={actionTo} className="empty-state-cta">
          {actionLabel}
        </Link>
      )}
    </section>
  );
}
