import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../lib/api";
import Badge from "../components/Badge";
import ScoreBar from "../components/ScoreBar";
import Spinner from "../components/Spinner";

export default function HistoryDetail({ sessionId, grade, onBack }) {
  const [questions, setQuestions] = useState(null);
  const [error, setError] = useState(null);
  const [openIdx, setOpenIdx] = useState(null);

  useEffect(() => {
    api.gradeQuestions(sessionId).then(setQuestions).catch((e) => setError(e.message));
  }, [sessionId]);

  if (error) {
    return (
      <div className="max-w-3xl mx-auto p-6">
        <BackButton onBack={onBack} />
        <div className="bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3 mt-4">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6 space-y-5 animate-fade-in">
      <BackButton onBack={onBack} />

      {/* Summary card */}
      {grade && (
        <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <h1 className="text-xl font-bold text-slate-800">
                {grade.domain.replace(/_/g, " ")} · {grade.experience}
              </h1>
              <p className="text-sm text-slate-500">
                {grade.completed_at?.replace("T", " ").split(".")[0]} ·{" "}
                {grade.total_questions} questions ·{" "}
                {Math.round(grade.duration_seconds / 60)} min
              </p>
              <p className="text-sm text-slate-500 mt-1">
                {(grade.topics || []).join(" · ")}
              </p>
            </div>
            <Badge variant={grade.score_label}>{grade.score_label}</Badge>
          </div>
          <div className="mt-3">
            <ScoreBar score={Number(grade.overall_score)} />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-5">
            <MiniSection title="Strengths" items={grade.strengths} tone="emerald" />
            <MiniSection title="To improve" items={grade.improvements} tone="rose" />
            <MiniSection title="Recommendations" items={grade.recommendations} tone="brand" />
          </div>
        </div>
      )}

      {/* Per-question breakdown */}
      <div>
        <h2 className="font-semibold text-slate-800 mb-2 px-1">
          Question-by-question feedback
        </h2>
        {!questions ? (
          <Spinner label="Loading questions…" />
        ) : questions.length === 0 ? (
          <div className="text-sm text-slate-500">No questions on record.</div>
        ) : (
          <ul className="space-y-2">
            {questions.map((q, i) => (
              <li key={q.id || i}>
                <button
                  onClick={() => setOpenIdx(openIdx === i ? null : i)}
                  className="w-full text-left bg-white rounded-xl border border-slate-200 p-4 hover:border-brand-200 transition"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-xs text-slate-400 uppercase tracking-wide">
                        Q{q.question_index} · {q.qtype} · {q.topic}
                      </div>
                      <div className="text-sm text-slate-800 mt-1 truncate">
                        {q.question_text}
                      </div>
                    </div>
                    <Badge variant={q.score_label?.toLowerCase()}>
                      {q.score_label}
                    </Badge>
                  </div>
                  {openIdx === i && (
                    <div className="mt-3 pt-3 border-t border-slate-100 space-y-3">
                      <div>
                        <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">
                          Your answer
                        </div>
                        <div className="text-sm text-slate-700 whitespace-pre-wrap">
                          {q.answer_text || "(skipped)"}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">
                          Feedback
                        </div>
                        <div className="prose prose-sm max-w-none prose-slate">
                          <ReactMarkdown>{q.feedback || "—"}</ReactMarkdown>
                        </div>
                      </div>
                      {q.ideal_answer && (
                        <div>
                          <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">
                            Ideal answer
                          </div>
                          <div className="text-sm text-slate-700 whitespace-pre-wrap">
                            {q.ideal_answer}
                          </div>
                        </div>
                      )}
                      {q.model_used && (
                        <div className="text-xs text-slate-400">
                          Evaluated by {q.model_used}
                        </div>
                      )}
                    </div>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function BackButton({ onBack }) {
  return (
    <button
      onClick={onBack}
      className="text-sm text-slate-500 hover:text-slate-800 inline-flex items-center gap-1"
    >
      ← Back to history
    </button>
  );
}

const TONE_BG = {
  emerald: "bg-emerald-50 text-emerald-700",
  rose: "bg-rose-50 text-rose-700",
  brand: "bg-brand-50 text-brand-700",
};

function MiniSection({ title, items, tone }) {
  return (
    <div className={`rounded-xl p-3 ${TONE_BG[tone]}`}>
      <div className="text-xs font-semibold uppercase tracking-wide mb-1.5">
        {title}
      </div>
      {!items?.length ? (
        <div className="text-xs opacity-60">—</div>
      ) : (
        <ul className="text-xs space-y-1">
          {items.map((it, i) => (
            <li key={i}>• {it}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
