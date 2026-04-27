import { useEffect, useState } from "react";
import { api } from "../lib/api";
import Spinner from "../components/Spinner";
import Badge from "../components/Badge";

export default function History({ onOpen }) {
  const [grades, setGrades] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.grades().then(setGrades).catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <div className="bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3">
          {error}
        </div>
      </div>
    );
  }
  if (!grades) {
    return <div className="max-w-5xl mx-auto p-6"><Spinner label="Loading history…" /></div>;
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 animate-fade-in">
      <header className="mb-5">
        <h1 className="text-2xl font-bold text-slate-800">Interview History</h1>
        <p className="text-slate-500 text-sm">
          {grades.length === 0
            ? "No interviews yet."
            : `${grades.length} past interview${grades.length === 1 ? "" : "s"} — click any to drill in.`}
        </p>
      </header>

      {grades.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200 p-8 text-center text-slate-500">
          You haven't completed any interviews yet. Go to the Setup screen to start one.
        </div>
      ) : (
        <ul className="space-y-3">
          {grades.map((g) => (
            <li key={g.session_id}>
              <button
                onClick={() => onOpen(g.session_id, g)}
                className="w-full text-left bg-white rounded-2xl border border-slate-200 p-4 sm:p-5 shadow-sm hover:shadow-md hover:border-brand-200 transition"
              >
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-slate-800">
                        {g.domain.replace(/_/g, " ")}
                      </span>
                      <Badge variant="brand">{g.experience}</Badge>
                      <Badge variant={g.score_label}>{g.score_label}</Badge>
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {(g.topics || []).slice(0, 4).join(" · ")}
                      {(g.topics || []).length > 4 ? "…" : ""}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                      {g.completed_at?.replace("T", " ").split(".")[0]} ·{" "}
                      {g.total_questions} Q · {Math.round(g.duration_seconds / 60)} min
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-slate-800 tabular-nums">
                      {Number(g.overall_score).toFixed(2)}
                    </div>
                    <div className="text-xs text-slate-400">/ 3.00</div>
                  </div>
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
