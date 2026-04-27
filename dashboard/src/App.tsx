import { Routes, Route, Link } from "react-router-dom";
import { Home } from "./pages/Home";
import { EvaluationDetail } from "./pages/EvaluationDetail";

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link to="/" className="text-lg font-bold text-slate-800">
            git-repo-evaluator
          </Link>
          <div className="text-xs text-slate-500">
            10 dimensions · vulnerability scan · Claude deep mode
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/eval/:id" element={<EvaluationDetail />} />
        </Routes>
      </main>
    </div>
  );
}
