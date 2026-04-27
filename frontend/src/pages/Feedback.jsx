import Badge from "../components/Badge";
import ScoreBar from "../components/ScoreBar";

export default function Feedback({ summary, onNavigate }) {
  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6 space-y-5 animate-fade-in">
      {/* Hero */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-slate-800">Interview Report</h1>
            <p className="text-slate-500 text-sm">
              {summary.total_questions} questions ·{" "}
              {Math.max(1, Math.round(summary.duration_seconds / 60))} min
            </p>
          </div>
          <Badge variant={summary.score_label}>{summary.score_label}</Badge>
        </div>
        <div className="mt-4">
          <ScoreBar score={summary.overall_score} />
          <div className="text-xs text-slate-500 mt-1 text-right">
            {summary.overall_score.toFixed(2)} / 3.00
          </div>
        </div>
      </div>

      {/* Per-topic */}
      {Object.keys(summary.per_topic_scores).length > 0 && (
        <Card title="Performance by topic">
          <div className="space-y-3">
            {Object.entries(summary.per_topic_scores)
              .sort((a, b) => a[1] - b[1])
              .map(([t, s]) => (
                <ScoreBar key={t} score={s} label={t} />
              ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Card title="✅ Strengths" tone="emerald">
          <BulletList items={summary.strengths} fallback="—" />
        </Card>
        <Card title="🎯 Areas to improve" tone="rose">
          <BulletList items={summary.improvements} fallback="—" />
        </Card>
      </div>

      <Card title="📚 Recommended next steps">
        <BulletList items={summary.recommendations} fallback="No recommendations." />
      </Card>

      <div className="flex flex-wrap gap-3 pt-2">
        <button
          onClick={() => onNavigate("setup")}
          className="px-5 py-3 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-medium shadow-sm hover:shadow-md transition"
        >
          Start another interview
        </button>
        <button
          onClick={() => onNavigate("dashboard")}
          className="px-5 py-3 rounded-xl border border-slate-200 bg-white text-slate-700 font-medium hover:bg-slate-50"
        >
          Back to Dashboard
        </button>
        <button
          onClick={() => onNavigate("history")}
          className="px-5 py-3 rounded-xl border border-slate-200 bg-white text-slate-700 font-medium hover:bg-slate-50"
        >
          View History
        </button>
      </div>
    </div>
  );
}

function Card({ title, tone, children }) {
  const border =
    tone === "emerald"
      ? "border-emerald-100"
      : tone === "rose"
      ? "border-rose-100"
      : "border-slate-200";
  return (
    <section className={`bg-white rounded-2xl border ${border} p-5 shadow-sm`}>
      <h2 className="font-semibold text-slate-800 mb-2">{title}</h2>
      {children}
    </section>
  );
}

function BulletList({ items, fallback }) {
  if (!items?.length)
    return <div className="text-sm text-slate-500">{fallback}</div>;
  return (
    <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}
