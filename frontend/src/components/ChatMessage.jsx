import ReactMarkdown from "react-markdown";

export default function ChatMessage({ role, children, meta, badge }) {
  const isAssistant = role === "assistant";
  return (
    <div className={`animate-slide-up flex ${isAssistant ? "justify-start" : "justify-end"}`}>
      <div
        className={
          "max-w-3xl px-4 py-3 rounded-2xl shadow-sm " +
          (isAssistant
            ? "bg-white border border-slate-200 text-slate-800 rounded-bl-sm"
            : "bg-gradient-to-br from-brand-600 to-violet-600 text-white rounded-br-sm")
        }
      >
        {(meta || badge) && (
          <div className={"flex items-center gap-2 mb-1.5 " + (isAssistant ? "" : "justify-end")}>
            {meta && (
              <span
                className={
                  "text-[11px] uppercase tracking-wide font-medium " +
                  (isAssistant ? "text-slate-400" : "text-brand-100")
                }
              >
                {meta}
              </span>
            )}
            {badge}
          </div>
        )}
        <div
          className={
            "prose prose-sm max-w-none " +
            (isAssistant
              ? "prose-slate prose-headings:font-semibold prose-p:my-2 prose-li:my-0.5"
              : "prose-invert prose-p:my-1")
          }
        >
          {typeof children === "string" ? <ReactMarkdown>{children}</ReactMarkdown> : children}
        </div>
      </div>
    </div>
  );
}
