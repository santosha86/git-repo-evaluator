import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, type EvaluationReport } from "../lib/api";
import { RadarScores } from "../components/RadarScores";
import { VulnerabilityTable } from "../components/VulnerabilityTable";
import { GradeBadge } from "../components/GradeBadge";

export function EvaluationDetail() {
  const { id = "" } = useParams();
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.evaluation(id).then(setReport).catch((e) => setError(String(e)));
  }, [id]);

  if (error) return <div className="text-red-600">Error: {error}</div>;
  if (!report) return <div className="text-slate-500">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link to="/" className="text-sm text-brand-700 hover:underline">
            ← back
          </Link>
          <h2 className="mt-1 text-2xl font-semibold">
            <a href={report.repo_url} target="_blank" rel="noreferrer" className="hover:underline">
              {report.repo_owner}/{report.repo_name}
            </a>
          </h2>
          <div className="text-sm text-slate-500">
            Evaluated {report.evaluated_at.slice(0, 19)} · id {report.eval_id}
          </div>
        </div>
        <GradeBadge grade={report.grade} score={report.final_score} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Dimension scores</h3>
          <RadarScores dimensions={report.dimensions} />
        </section>
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-semibold text-slate-700">Breakdown</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-1">Dimension</th>
                <th className="py-1">Score</th>
                <th className="py-1">Weight</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.dimensions).map(([name, d]) => (
                <tr key={name} className="border-t border-slate-100">
                  <td className="py-1">{name.replace("_", " ")}</td>
                  <td className="py-1 font-mono">{d.score.toFixed(2)}</td>
                  <td className="py-1 text-slate-500">{(d.weight * 100).toFixed(0)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-slate-700">
          Vulnerabilities ({report.vulnerabilities.length})
        </h3>
        <VulnerabilityTable findings={report.vulnerabilities} />
      </section>

      {report.llm_analysis && (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">Deep analysis (Claude)</h3>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-700">
            {report.llm_analysis}
          </pre>
        </section>
      )}
    </div>
  );
}
