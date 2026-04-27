const GRADE_COLOR: Record<string, string> = {
  "A+": "bg-emerald-600 text-white",
  A: "bg-emerald-500 text-white",
  "B+": "bg-sky-600 text-white",
  B: "bg-sky-500 text-white",
  "C+": "bg-amber-500 text-white",
  C: "bg-amber-600 text-white",
  D: "bg-orange-600 text-white",
  F: "bg-red-600 text-white",
};

export function GradeBadge({ grade, score }: { grade: string; score?: number }) {
  return (
    <span
      className={`inline-flex items-baseline gap-2 rounded-lg px-3 py-1 text-sm font-semibold ${
        GRADE_COLOR[grade] ?? "bg-slate-500 text-white"
      }`}
    >
      <span className="text-base">{grade}</span>
      {score !== undefined && <span className="text-xs opacity-80">{score.toFixed(2)}</span>}
    </span>
  );
}
