import { getMetricVerdict, METRIC_LABELS } from "../lib/formatting";

interface MetricCardProps {
  metricKey: string;
  value: number | null;
}

export default function MetricCard({ metricKey, value }: MetricCardProps) {
  const config = METRIC_LABELS[metricKey];
  if (!config || value === null) return null;

  const verdict = getMetricVerdict(value, config.thresholds);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5">
      <p className="text-sm font-medium text-gray-500 mb-1">{config.name}</p>
      <p className="text-3xl font-bold mb-1" style={{ color: verdict.color }}>
        {config.format(value)}
      </p>
      <span
        className="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: verdict.color }}
      >
        {verdict.label}
      </span>
      <p className="text-sm text-gray-500 mt-3">{config.explain(value)}</p>
    </div>
  );
}
