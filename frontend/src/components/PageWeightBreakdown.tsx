import type { PageWeightData } from "../lib/api";
import { formatBytes } from "../lib/formatting";

interface PageWeightBreakdownProps {
  data: PageWeightData;
}

const TYPE_COLORS: Record<string, string> = {
  images: "#f59e0b",
  js: "#8b5cf6",
  css: "#3b82f6",
  fonts: "#10b981",
  html: "#6b7280",
  other: "#d1d5db",
};

const TYPE_LABELS: Record<string, string> = {
  images: "Images",
  js: "JavaScript",
  css: "CSS",
  fonts: "Polices",
  html: "HTML",
  other: "Autres",
};

export default function PageWeightBreakdown({ data }: PageWeightBreakdownProps) {
  const totalMb = data.total_size_bytes / (1024 * 1024);
  const isHeavy = totalMb > 2;
  const isTooManyRequests = data.total_requests > 50;

  const sortedTypes = Object.entries(data.by_type).sort(
    ([, a], [, b]) => b.size_bytes - a.size_bytes,
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-sm text-gray-500">Poids total</p>
          <p className={`text-3xl font-bold ${isHeavy ? "text-red-500" : "text-green-600"}`}>
            {formatBytes(data.total_size_bytes)}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            Recommande : moins de 2 Mo
          </p>
        </div>
        <div className="rounded-xl border border-gray-200 bg-white p-5">
          <p className="text-sm text-gray-500">Requetes HTTP</p>
          <p className={`text-3xl font-bold ${isTooManyRequests ? "text-orange-500" : "text-green-600"}`}>
            {data.total_requests}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            Recommande : moins de 50
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-gray-200 bg-white p-5">
        <p className="text-sm font-medium text-gray-700 mb-3">Repartition par type</p>
        <div className="flex h-8 rounded-full overflow-hidden mb-3">
          {sortedTypes.map(([type, info]) => {
            const pct = data.total_size_bytes > 0
              ? (info.size_bytes / data.total_size_bytes) * 100
              : 0;
            if (pct < 1) return null;
            return (
              <div
                key={type}
                style={{
                  width: `${pct}%`,
                  backgroundColor: TYPE_COLORS[type] || TYPE_COLORS.other,
                }}
                title={`${TYPE_LABELS[type] || type}: ${formatBytes(info.size_bytes)}`}
              />
            );
          })}
        </div>
        <div className="flex flex-wrap gap-x-5 gap-y-1">
          {sortedTypes.map(([type, info]) => (
            <div key={type} className="flex items-center gap-1.5 text-sm">
              <span
                className="w-3 h-3 rounded-full inline-block"
                style={{ backgroundColor: TYPE_COLORS[type] || TYPE_COLORS.other }}
              />
              <span className="text-gray-600">
                {TYPE_LABELS[type] || type} : {formatBytes(info.size_bytes)}
              </span>
            </div>
          ))}
        </div>
      </div>

      {data.unoptimized_images && data.unoptimized_images.count > 0 && (
        <div className="rounded-xl border border-orange-200 bg-orange-50 p-5">
          <p className="font-medium text-orange-800">
            {data.unoptimized_images.count} image{data.unoptimized_images.count > 1 ? "s" : ""} non
            optimisee{data.unoptimized_images.count > 1 ? "s" : ""} ({formatBytes(data.unoptimized_images.total_size_bytes)})
          </p>
          <p className="text-sm text-orange-700 mt-1">
            Ces images de plus de 200 Ko pourraient etre converties en WebP ou AVIF.
          </p>
        </div>
      )}

      {data.third_party_count > 0 && (
        <p className="text-sm text-gray-500">
          {data.third_party_count} requetes tierces ({formatBytes(data.third_party_size_bytes)})
        </p>
      )}
    </div>
  );
}
