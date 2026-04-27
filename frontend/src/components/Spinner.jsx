export default function Spinner({ label = "Loading…", size = "md" }) {
  const dot = size === "sm" ? "w-2 h-2" : "w-3 h-3";
  return (
    <div className="flex items-center gap-2 text-slate-500 animate-fade-in">
      <span className={`${dot} inline-block rounded-full bg-brand-500 animate-pulse`} />
      <span className={`${dot} inline-block rounded-full bg-brand-500 animate-pulse [animation-delay:0.15s]`} />
      <span className={`${dot} inline-block rounded-full bg-brand-500 animate-pulse [animation-delay:0.3s]`} />
      <span className="text-sm ml-1">{label}</span>
    </div>
  );
}

export function FullScreenSpinner({ label = "Loading…" }) {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Spinner label={label} />
    </div>
  );
}
