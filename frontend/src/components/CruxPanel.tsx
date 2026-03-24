import type { CruxData } from "../lib/api";
import { getVerdictColor, METRIC_LABELS } from "../lib/formatting";

interface CruxPanelProps {
  data: CruxData | null;
  label: string;
}

const CRUX_KEY_MAP: Record<string, string> = {
  LARGEST_CONTENTFUL_PAINT_MS: "LCP",
  CUMULATIVE_LAYOUT_SHIFT_SCORE: "CLS",
  INTERACTION_TO_NEXT_PAINT: "INP",
  EXPERIMENTAL_TIME_TO_FIRST_BYTE: "TTFB",
};

export default function CruxPanel({ data, label }: CruxPanelProps) {
  if (!data || !data.metrics) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">{label}</h3>
        <p className="text-gray-500">
          Pas assez de trafic pour des donnees terrain. Resultats de laboratoire uniquement.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-1">{label}</h3>
      <p className="text-sm text-gray-500 mb-5">Ce que vivent reellement vos visiteurs</p>

      <div className="space-y-5">
        {Object.entries(data.metrics).map(([key, metric]) => {
          const shortKey = CRUX_KEY_MAP[key];
          if (!shortKey) return null;
          const config = METRIC_LABELS[shortKey];
          if (!config) return null;

          const p75 = metric.percentile;
          const formatted = config.format(p75);
          const color = getVerdictColor(metric.category);
          const distributions = metric.distributions || [];

          return (
            <div key={key}>
              <div className="flex items-baseline justify-between mb-1.5">
                <span className="font-medium text-gray-700">{config.name}</span>
                <span className="text-lg font-bold" style={{ color }}>
                  {formatted}
                  <span className="text-xs text-gray-400 ml-1">(P75)</span>
                </span>
              </div>
              <div className="flex h-5 rounded-full overflow-hidden">
                {distributions.map((d, i) => {
                  const colors = ["#0cce6b", "#ffa400", "#ff4e42"];
                  const pct = Math.round(d.proportion * 100);
                  return (
                    <div
                      key={i}
                      className="flex items-center justify-center text-xs font-medium text-white"
                      style={{
                        width: `${pct}%`,
                        backgroundColor: colors[i],
                        minWidth: pct > 0 ? "2rem" : 0,
                      }}
                    >
                      {pct > 5 ? `${pct}%` : ""}
                    </div>
                  );
                })}
              </div>
              <p className="text-xs text-gray-400 mt-1">{config.explain(p75)}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
