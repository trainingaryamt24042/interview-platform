const VARIANTS = {
  excellent: "bg-emerald-50 text-emerald-700 border-emerald-200",
  good: "bg-amber-50 text-amber-700 border-amber-200",
  poor: "bg-rose-50 text-rose-700 border-rose-200",
  default: "bg-slate-100 text-slate-700 border-slate-200",
  brand: "bg-brand-50 text-brand-700 border-brand-200",
};

export default function Badge({ variant = "default", children }) {
  return (
    <span
      className={
        "inline-flex items-center px-2.5 py-1 rounded-full border text-xs font-medium uppercase tracking-wide " +
        (VARIANTS[variant] || VARIANTS.default)
      }
    >
      {children}
    </span>
  );
}
