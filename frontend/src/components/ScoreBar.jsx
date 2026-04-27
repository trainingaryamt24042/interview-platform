// Reusable horizontal score bar (0..3 scale).
export default function ScoreBar({ score, max = 3, showValue = true, label = null, color }) {
  const pct = Math.max(0, Math.min(1, score / max)) * 100;
  const fill =
    color ||
    (score >= 2.5 ? "bg-emerald-500" : score >= 1.5 ? "bg-amber-500" : "bg-rose-500");
  return (
    <div className="w-full">
      {label && (
        <div className="flex justify-between text-xs text-slate-600 mb-1">
          <span>{label}</span>
          {showValue && <span className="font-medium">{score.toFixed(2)}/{max}</span>}
        </div>
      )}
      <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full ${fill} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
