import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type EvaluationRow } from "../lib/api";
import { GradeBadge } from "../components/GradeBadge";

export function Home() {
  const [repo, setRepo] = useState("");
  const [deep, setDeep] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<EvaluationRow[]>([]);

  const refresh = () =>
    api
      .listEvaluations(50)
      .then(setRows)
      .catch((e) => setError(String(e)));

  useEffect(() => {
    refresh();
  }, []);

  const onEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repo.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await api.evaluate(repo.trim(), deep);
      setRepo("");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Evaluate a GitHub repo</h2>
        <form onSubmit={onEvaluate} className="flex flex-wrap items-center gap-3">
          <input
            value={repo}
            onChange={(e) => setRepo(e.target.value)}
            placeholder="owner/name or https://github.com/..."
            className="min-w-[320px] flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none"
          />
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={deep} onChange={(e) => setDeep(e.target.checked)} />
            Deep (Claude)
          </label>
          <button
            type="submit"
            disabled={loading}
            className="rounded bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {loading ? "Evaluating…" : "Evaluate"}
          </button>
          {error && <span className="text-sm text-red-600">{error}</span>}
        </form>
      </section>

      <section>
        <h2 className="mb-3 text-lg font-semibold">Recent evaluations</h2>
        {rows.length === 0 ? (
          <div className="text-sm text-slate-500">No evaluations yet.</div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Repo</th>
                  <th className="px-3 py-2">Grade</th>
                  <th className="px-3 py-2">Score</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.eval_id} className="border-t border-slate-200 hover:bg-slate-50">
                    <td className="px-3 py-2 text-slate-500">{r.evaluated_at.slice(0, 19)}</td>
                    <td className="px-3 py-2">
                      <Link
                        to={`/eval/${r.eval_id}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {r.repo_owner}/{r.repo_name}
                      </Link>
                    </td>
                    <td className="px-3 py-2">
                      <GradeBadge grade={r.grade} />
                    </td>
                    <td className="px-3 py-2 font-mono">{r.final_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
