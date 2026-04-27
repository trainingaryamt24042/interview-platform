import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import Spinner from "../components/Spinner";
import ScoreBar from "../components/ScoreBar";

export default function Scoreboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [sortBy, setSortBy] = useState("avg"); // 'avg' | 'volume' | 'recent'

  useEffect(() => {
    api.topicStats().then(setStats).catch((e) => setError(e.message));
  }, []);

  const sorted = useMemo(() => {
    if (!stats) return null;
    const copy = [...stats];
    if (sortBy === "avg") copy.sort((a, b) => b.avg_score - a.avg_score);
    else if (sortBy === "volume") copy.sort((a, b) => b.total_questions - a.total_questions);
    else if (sortBy === "recent")
      copy.sort((a, b) => (b.last_updated || "").localeCompare(a.last_updated || ""));
    return copy;
  }, [stats, sortBy]);

  const careerAvg = useMemo(() => {
    if (!stats?.length) return 0;
    const total = stats.reduce((acc, s) => acc + s.total_score, 0);
    const count = stats.reduce((acc, s) => acc + s.total_questions, 0);
    return count ? total / count : 0;
  }, [stats]);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <div className="bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3">
          {error}
        </div>
      </div>
    );
  }
  if (!stats) {
    return <div className="max-w-5xl mx-auto p-6"><Spinner label="Loading scoreboard…" /></div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 animate-fade-in space-y-5">
      {/* Hero */}
      <div className="bg-gradient-to-br from-brand-600 to-violet-600 text-white rounded-2xl p-6 shadow-md">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Scoreboard</h1>
            <p className="opacity-90 text-sm">
              Your per-topic performance across all interviews.
            </p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold tabular-nums">
              {careerAvg.toFixed(2)}
            </div>
            <div className="text-xs opacity-80">career average / 3.00</div>
          </div>
        </div>
      </div>

      {/* Empty state */}
      {stats.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-500">
          No data yet. Complete an interview to see your topic scoreboard.
        </div>
      ) : (
        <>
          {/* Sort controls */}
          <div className="flex items-center gap-2 px-1">
            <span className="text-sm text-slate-500">Sort by:</span>
            {[
              { id: "avg", label: "Score" },
              { id: "volume", label: "Questions" },
              { id: "recent", label: "Recent" },
            ].map((opt) => (
              <button
                key={opt.id}
                onClick={() => setSortBy(opt.id)}
                className={
                  "text-sm px-3 py-1 rounded-full border transition " +
                  (sortBy === opt.id
                    ? "bg-brand-50 text-brand-700 border-brand-200"
                    : "bg-white text-slate-600 border-slate-200 hover:border-brand-300")
                }
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* Top performers / focus areas */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Highlight
              title="🏆 Top topics"
              items={[...stats].sort((a, b) => b.avg_score - a.avg_score).slice(0, 3)}
              positive
            />
            <Highlight
              title="🎯 Focus areas"
              items={[...stats].sort((a, b) => a.avg_score - b.avg_score).slice(0, 3)}
            />
          </div>

          {/* Full table-as-cards */}
          <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
            <h2 className="font-semibold text-slate-800 mb-3">All topics</h2>
            <div className="space-y-3">
              {sorted.map((s) => (
                <div key={s.topic} className="flex items-center gap-3">
                  <div className="w-32 sm:w-44 text-sm font-medium text-slate-700 truncate">
                    {s.topic}
                  </div>
                  <div className="flex-1 min-w-0">
                    <ScoreBar score={Number(s.avg_score)} showValue={false} />
                  </div>
                  <div className="w-16 text-right text-sm tabular-nums text-slate-700">
                    {Number(s.avg_score).toFixed(2)}
                  </div>
                  <div className="w-20 text-right text-xs text-slate-400 hidden sm:block">
                    {s.total_questions} Qs
                  </div>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Highlight({ title, items, positive = false }) {
  const ring = positive ? "from-emerald-500 to-teal-500" : "from-rose-500 to-orange-500";
  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <h2 className="font-semibold text-slate-800 mb-3">{title}</h2>
      {items.length === 0 ? (
        <div className="text-sm text-slate-500">—</div>
      ) : (
        <ul className="space-y-2">
          {items.map((s, i) => (
            <li key={s.topic} className="flex items-center gap-3">
              <div
                className={`w-7 h-7 rounded-lg bg-gradient-to-br ${ring} text-white flex items-center justify-center text-xs font-bold`}
              >
                {i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-800 truncate">{s.topic}</div>
                <div className="text-xs text-slate-500">
                  {s.total_questions} questions
                </div>
              </div>
              <div className="text-sm tabular-nums font-medium text-slate-700">
                {Number(s.avg_score).toFixed(2)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
