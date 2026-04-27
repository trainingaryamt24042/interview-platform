import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import Spinner from "../components/Spinner";
import Badge from "../components/Badge";
import ScoreBar from "../components/ScoreBar";

export default function Dashboard({ onNavigate }) {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <ErrorBox error={error} />;
  if (!data) {
    return (
      <div className="max-w-5xl mx-auto p-6">
        <Spinner label="Loading your dashboard…" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 space-y-6 animate-fade-in">
      {/* Greeting */}
      <header>
        <h1 className="text-3xl font-bold text-slate-800">
          Welcome back, {user?.username} 👋
        </h1>
        <p className="text-slate-500 mt-1">
          {data.has_history
            ? `${data.total_sessions} sessions · career average ${data.career_average}/3.00`
            : "Let's run your first mock interview."}
        </p>
      </header>

      {/* First-time empty state */}
      {!data.has_history ? (
        <FirstTimeCard onStart={() => onNavigate("setup")} />
      ) : (
        <>
          {/* Last grade card */}
          <LastGradeCard grade={data.last_grade} onViewAll={() => onNavigate("history")} />

          {/* Quick actions row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <ActionTile
              icon="✨"
              title="New Interview"
              subtitle="Pick domain & topics"
              onClick={() => onNavigate("setup")}
              primary
            />
            <ActionTile
              icon="📋"
              title="History"
              subtitle={`${data.total_sessions} past sessions`}
              onClick={() => onNavigate("history")}
            />
            <ActionTile
              icon="📊"
              title="Scoreboard"
              subtitle="Your topic strengths"
              onClick={() => onNavigate("scoreboard")}
            />
          </div>

          {/* Weak / strong topics */}
          {(data.weak_topics.length > 0 || data.strong_topics.length > 0) && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <TopicsList
                title="Focus areas"
                emoji="🎯"
                topics={data.weak_topics}
                empty="No weak topics yet — keep going!"
                tone="rose"
              />
              <TopicsList
                title="Strengths"
                emoji="💪"
                topics={data.strong_topics}
                empty="Build a track record to unlock this."
                tone="emerald"
              />
            </div>
          )}

          {/* Mini topic stats */}
          {data.topic_stats?.length > 0 && (
            <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-semibold text-slate-800">Topic averages</h2>
                <button
                  onClick={() => onNavigate("scoreboard")}
                  className="text-sm text-brand-600 hover:text-brand-700"
                >
                  View full scoreboard →
                </button>
              </div>
              <div className="space-y-2.5">
                {data.topic_stats.slice(0, 5).map((s) => (
                  <ScoreBar
                    key={s.topic}
                    score={Number(s.avg_score)}
                    label={`${s.topic} · ${s.total_questions} Qs`}
                  />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}

function ErrorBox({ error }) {
  return (
    <div className="max-w-3xl mx-auto p-6">
      <div className="bg-rose-50 border border-rose-200 text-rose-700 rounded-xl px-4 py-3">
        Could not load dashboard: {error}
      </div>
    </div>
  );
}

function FirstTimeCard({ onStart }) {
  return (
    <div className="bg-gradient-to-br from-brand-600 to-violet-600 text-white rounded-2xl p-8 shadow-md">
      <h2 className="text-xl font-semibold">No interviews yet</h2>
      <p className="opacity-90 mt-1">
        Start a mock interview to get instant AI feedback, track your progress, and see your weak topics.
      </p>
      <button
        onClick={onStart}
        className="mt-4 inline-flex items-center px-5 py-2.5 rounded-xl bg-white text-brand-700 font-medium hover:bg-brand-50 transition"
      >
        Start your first interview →
      </button>
    </div>
  );
}

function LastGradeCard({ grade, onViewAll }) {
  if (!grade) return null;
  const date = grade.completed_at?.split("T")[0] || "";
  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-xs text-slate-500 uppercase tracking-wide">Last interview</div>
          <h2 className="text-lg font-semibold text-slate-800 mt-0.5">
            {grade.domain.replace(/_/g, " ")} · {grade.experience}
          </h2>
          <p className="text-sm text-slate-500">
            {grade.total_questions} questions · {date}
          </p>
        </div>
        <Badge variant={grade.score_label}>{grade.score_label}</Badge>
      </div>

      <div className="mt-4">
        <ScoreBar score={Number(grade.overall_score)} />
      </div>

      {grade.improvements?.length > 0 && (
        <div className="mt-4 text-sm">
          <div className="font-medium text-slate-700 mb-1">Top areas to improve</div>
          <ul className="list-disc pl-5 text-slate-600 space-y-1">
            {grade.improvements.slice(0, 2).map((it, i) => <li key={i}>{it}</li>)}
          </ul>
        </div>
      )}

      <button
        onClick={onViewAll}
        className="mt-4 text-sm text-brand-600 hover:text-brand-700"
      >
        View all history →
      </button>
    </section>
  );
}

function ActionTile({ icon, title, subtitle, onClick, primary = false }) {
  return (
    <button
      onClick={onClick}
      className={
        "text-left p-4 rounded-2xl border transition shadow-sm hover:shadow-md " +
        (primary
          ? "bg-gradient-to-br from-brand-600 to-violet-600 text-white border-transparent"
          : "bg-white border-slate-200 text-slate-800 hover:border-brand-300")
      }
    >
      <div className="text-2xl">{icon}</div>
      <div className="mt-2 font-semibold">{title}</div>
      <div className={"text-sm " + (primary ? "text-brand-100" : "text-slate-500")}>
        {subtitle}
      </div>
    </button>
  );
}

const TONE = {
  rose: "bg-rose-50 text-rose-700 border-rose-200",
  emerald: "bg-emerald-50 text-emerald-700 border-emerald-200",
};

function TopicsList({ title, emoji, topics, empty, tone }) {
  return (
    <section className="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm">
      <h2 className="font-semibold text-slate-800 mb-3">
        {emoji} {title}
      </h2>
      {topics.length === 0 ? (
        <p className="text-sm text-slate-500">{empty}</p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {topics.map((t) => (
            <span key={t} className={`px-2.5 py-1 rounded-full border text-sm ${TONE[tone]}`}>
              {t}
            </span>
          ))}
        </div>
      )}
    </section>
  );
}
