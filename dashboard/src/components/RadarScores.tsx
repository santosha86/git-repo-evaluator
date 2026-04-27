import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { DimensionScore } from "../lib/api";

type Props = {
  dimensions: Record<string, DimensionScore>;
};

export function RadarScores({ dimensions }: Props) {
  const data = Object.entries(dimensions).map(([name, d]) => ({
    dimension: name.replace("_", " "),
    score: d.score,
  }));

  return (
    <div className="h-96 w-full">
      <ResponsiveContainer>
        <RadarChart data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11 }} />
          <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10 }} />
          <Radar
            dataKey="score"
            stroke="#0284c7"
            fill="#0ea5e9"
            fillOpacity={0.4}
          />
          <Tooltip />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
