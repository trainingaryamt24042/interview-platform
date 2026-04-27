import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import ChatMessage from "../components/ChatMessage";
import Spinner from "../components/Spinner";
import Badge from "../components/Badge";

export default function Interview({ session, onFinish, onCancel }) {
  const [messages, setMessages] = useState([]);
  const [currentQ, setCurrentQ] = useState(null);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("Thinking…");
  const [askedCount, setAskedCount] = useState(0);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    nextQuestion();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const nextQuestion = async (qtype = null) => {
    setBusy(true);
    setBusyLabel("Generating question…");
    setError(null);
    try {
      const { question, total_so_far } = await api.generateQuestion(session.session_id, qtype);
      setCurrentQ(question);
      setAskedCount(total_so_far);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          meta: `Q${total_so_far} · ${question.qtype} · ${question.topic}`,
          content: question.text,
        },
      ]);
    } catch (e) {
      setError(humanError(e));
    } finally {
      setBusy(false);
    }
  };

  const submit = async () => {
    if (!answer.trim() || !currentQ || busy) return;
    const myAnswer = answer.trim();
    setMessages((m) => [...m, { role: "user", content: myAnswer }]);
    setAnswer("");
    setBusy(true);
    setBusyLabel("Evaluating…");
    setError(null);
    try {
      const { evaluation } = await api.evaluateAnswer(
        session.session_id,
        currentQ.id,
        myAnswer
      );
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          meta: "Feedback",
          badge: <Badge variant={evaluation.score_label}>{evaluation.score_label}</Badge>,
          content: renderEvalMarkdown(evaluation),
        },
      ]);
    } catch (e) {
      setError(humanError(e));
      setBusy(false);
      return;
    }
    setBusy(false);
    if (askedCount < session.config.target_questions) {
      await nextQuestion();
    }
  };

  const askScenario = async () => {
    setBusy(true);
    setBusyLabel("Generating scenario…");
    setError(null);
    try {
      const { scenario } = await api.generateScenario(
        session.session_id,
        currentQ?.topic || null
      );
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          meta: `Scenario · ${scenario.topic}`,
          content:
            `**${scenario.title}**\n\n${scenario.context}\n\n**Problem:** ${scenario.problem}\n\n` +
            (scenario.expected_approach.length
              ? "**Expected approach:**\n" +
                scenario.expected_approach.map((p) => `- ${p}`).join("\n")
              : ""),
        },
      ]);
    } catch (e) {
      setError(humanError(e));
    } finally {
      setBusy(false);
    }
  };

  const finish = async () => {
    setBusy(true);
    setBusyLabel("Compiling your report…");
    try {
      const { summary } = await api.endSession(session.session_id);
      onFinish(summary);
    } catch (e) {
      setError(humanError(e));
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="bg-white/90 backdrop-blur border-b border-slate-200 px-4 sm:px-6 py-3 flex items-center justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <button
              onClick={onCancel}
              className="text-slate-400 hover:text-slate-700 text-sm"
              title="Back to dashboard"
            >
              ←
            </button>
            <span className="text-sm font-medium text-slate-700 truncate">
              {session.config.domain.replace(/_/g, " ")} · {session.config.experience}
            </span>
          </div>
          <div className="text-xs text-slate-400 truncate">
            {session.config.topics.join(", ")}
            {session.config.custom_topic ? ` · ${session.config.custom_topic}` : ""}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-500 tabular-nums">
            {askedCount} / {session.config.target_questions}
          </span>
          <button
            onClick={askScenario}
            disabled={busy}
            className="px-3 py-1.5 rounded-lg border border-slate-200 text-sm hover:bg-slate-50 disabled:opacity-50"
          >
            Scenario
          </button>
          <button
            onClick={finish}
            disabled={busy || askedCount === 0}
            className="px-3 py-1.5 rounded-lg bg-rose-600 text-white text-sm hover:bg-rose-700 disabled:opacity-50"
          >
            End & Score
          </button>
        </div>
      </header>

      {/* Chat */}
      <main className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.map((m, i) => (
            <ChatMessage key={i} role={m.role} meta={m.meta} badge={m.badge}>
              {m.content}
            </ChatMessage>
          ))}
          {busy && (
            <div className="px-2">
              <Spinner label={busyLabel} />
            </div>
          )}
          {error && (
            <div className="text-sm text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
              {error}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </main>

      {/* Composer */}
      <footer className="bg-white border-t border-slate-200 px-4 py-3">
        <div className="max-w-4xl mx-auto flex gap-2 items-end">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            }}
            rows={3}
            placeholder="Type your answer… (Ctrl/Cmd+Enter to submit)"
            disabled={busy || !currentQ}
            className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm focus:ring-2 focus:ring-brand-200 focus:border-brand-400 outline-none disabled:bg-slate-50"
          />
          <button
            onClick={submit}
            disabled={busy || !answer.trim()}
            className="h-10 px-5 rounded-xl bg-gradient-to-r from-brand-600 to-violet-600 text-white text-sm font-medium hover:shadow-md disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </footer>
    </div>
  );
}

function renderEvalMarkdown(ev) {
  let md = ev.feedback || "";
  if (ev.strengths?.length) md += "\n\n**Strengths**\n" + ev.strengths.map((s) => `- ${s}`).join("\n");
  if (ev.gaps?.length) md += "\n\n**Gaps**\n" + ev.gaps.map((s) => `- ${s}`).join("\n");
  if (ev.ideal_answer) md += `\n\n**Ideal answer:** ${ev.ideal_answer}`;
  if (ev.model_used) md += `\n\n_Model: ${ev.model_used}_`;
  return md;
}

function humanError(e) {
  const m = e.message || String(e);
  if (m.includes("502")) return "AI service is having a moment — please try again.";
  return m.replace(/^\d+:\s*/, "");
}
