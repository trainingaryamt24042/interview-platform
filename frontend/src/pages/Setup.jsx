import { useEffect, useState } from "react";
import { api } from "../lib/api";

const EXPERIENCE_OPTIONS = [
  { value: "fresher", label: "Fresher", hint: "0 yrs · fundamentals" },
  { value: "junior", label: "Junior", hint: "1–3 yrs · practical" },
  { value: "mid", label: "Mid", hint: "3–5 yrs · trade-offs" },
  { value: "senior", label: "Senior", hint: "5+ yrs · system design" },
];

const DOMAIN_LABELS = {
  data_engineering: "Data Engineering",
  backend: "Backend",
  ai_ml: "AI / ML",
  devops: "DevOps",
  frontend: "Frontend",
  system_design: "System Design",
};

export default function Setup({ onStart }) {
  const [domains, setDomains] = useState({});
  const [domain, setDomain] = useState("data_engineering");
  const [experience, setExperience] = useState("mid");
  const [topics, setTopics] = useState([]);
  const [customTopic, setCustomTopic] = useState("");
  const [target, setTarget] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.topics().then((r) => setDomains(r.domains)).catch((e) => setError(e.message));
  }, []);

  // When domain changes, default to first 3 topics.
  useEffect(() => {
    if (domains[domain]) setTopics(domains[domain].slice(0, 3));
  }, [domain, domains]);

  const toggle = (t) =>
    setTopics((cur) => (cur.includes(t) ? cur.filter((x) => x !== t) : [...cur, t]));

  const start = async () => {
    setError(null);
    if (topics.length === 0 && !customTopic.trim()) {
      setError("Pick at least one topic, or add a custom one.");
      return;
    }
    setLoading(true);
    try {
      const { session_id, config } = await api.createSession({
        domain,
        experience,
        topics,
        custom_topic: customTopic.trim() || null,
        target_questions: Number(target) || 8,
      });
      onStart({ session_id, config });
    } catch (e) {
      setError(e.message.replace(/^\d+:\s*/, ""));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-6 animate-fade-in">
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-6 space-y-6">
        <header>
          <h1 className="text-2xl font-bold text-slate-800">New Interview</h1>
          <p className="text-slate-500 text-sm mt-1">
            Pick your domain, level, and topics. Difficulty calibrates automatically.
          </p>
        </header>

        {/* Domain */}
        <div>
          <label className="text-sm font-medium text-slate-700">Domain</label>
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
            {Object.keys(domains).map((d) => (
              <button
                key={d}
                onClick={() => setDomain(d)}
                className={
                  "px-3 py-2.5 rounded-xl border text-sm font-medium transition text-left " +
                  (domain === d
                    ? "bg-brand-50 text-brand-700 border-brand-300 shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:border-brand-300")
                }
              >
                {DOMAIN_LABELS[d] || d}
              </button>
            ))}
          </div>
        </div>

        {/* Experience */}
        <div>
          <label className="text-sm font-medium text-slate-700">Experience level</label>
          <div className="mt-2 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {EXPERIENCE_OPTIONS.map((o) => (
              <button
                key={o.value}
                onClick={() => setExperience(o.value)}
                className={
                  "px-3 py-2.5 rounded-xl border text-left transition " +
                  (experience === o.value
                    ? "bg-gradient-to-br from-brand-600 to-violet-600 text-white border-transparent shadow-sm"
                    : "bg-white text-slate-700 border-slate-200 hover:border-brand-300")
                }
              >
                <div className="text-sm font-semibold">{o.label}</div>
                <div className={"text-xs " + (experience === o.value ? "text-brand-100" : "text-slate-500")}>
                  {o.hint}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Topics */}
        <div>
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-slate-700">Topics</label>
            <span className="text-xs text-slate-400">
              {topics.length} selected
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {(domains[domain] || []).map((t) => (
              <button
                key={t}
                onClick={() => toggle(t)}
                className={
                  "px-3 py-1.5 rounded-full border text-sm transition " +
                  (topics.includes(t)
                    ? "bg-brand-50 text-brand-700 border-brand-300"
                    : "bg-white text-slate-600 border-slate-200 hover:border-brand-300")
                }
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Custom topic + count */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="text-sm font-medium text-slate-700">Custom topic (optional)</label>
            <input
              value={customTopic}
              onChange={(e) => setCustomTopic(e.target.value)}
              placeholder="e.g. Delta Lake, CRDTs, Vector DBs…"
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 bg-slate-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700"># Questions</label>
            <input
              type="number"
              min={1}
              max={50}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 bg-slate-50 focus:bg-white focus:border-brand-400 focus:ring-2 focus:ring-brand-100 outline-none transition"
            />
          </div>
        </div>

        {error && (
          <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <button
          onClick={start}
          disabled={loading}
          className="w-full py-3 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white font-medium shadow-sm hover:shadow-md disabled:opacity-50 transition"
        >
          {loading ? "Starting…" : "Start Interview →"}
        </button>
      </div>
    </div>
  );
}
