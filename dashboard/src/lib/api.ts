export type DimensionScore = {
  name: string;
  score: number;
  weight: number;
  evidence: string[];
  raw: Record<string, unknown>;
};

export type VulnerabilityFinding = {
  finding_id: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  category: string;
  title: string;
  description: string;
  file: string | null;
  line: number | null;
};

export type EvaluationReport = {
  eval_id: string;
  repo_owner: string;
  repo_name: string;
  repo_url: string;
  evaluated_at: string;
  dimensions: Record<string, DimensionScore>;
  final_score: number;
  grade: string;
  vulnerabilities: VulnerabilityFinding[];
  llm_analysis: string | null;
};

export type RepoRow = {
  repo_owner: string;
  repo_name: string;
  repo_url: string;
  first_evaluated: string;
  last_evaluated: string;
  eval_count: string;
  latest_grade: string;
  latest_score: string;
};

export type EvaluationRow = {
  eval_id: string;
  repo_owner: string;
  repo_name: string;
  evaluated_at: string;
  final_score: string;
  grade: string;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  return res.json();
}

export const api = {
  listRepos: () => fetch("/api/repos").then((r) => json<RepoRow[]>(r)),

  listEvaluations: (limit = 50) =>
    fetch(`/api/evaluations?limit=${limit}`).then((r) => json<EvaluationRow[]>(r)),

  evaluation: (id: string) =>
    fetch(`/api/evaluations/${id}`).then((r) => json<EvaluationReport>(r)),

  history: (owner: string, name: string) =>
    fetch(`/api/repos/${owner}/${name}/history`).then((r) => json<EvaluationRow[]>(r)),

  latest: (owner: string, name: string) =>
    fetch(`/api/repos/${owner}/${name}/latest`).then((r) => json<EvaluationReport>(r)),

  evaluate: (repo: string, deep = false) =>
    fetch("/api/evaluate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ repo, deep }),
    }).then((r) => json<EvaluationReport>(r)),
};
