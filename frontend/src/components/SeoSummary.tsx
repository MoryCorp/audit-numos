import type { CrawlSummary } from "../lib/api";

interface SeoSummaryProps {
  data: CrawlSummary;
}

const SEVERITY_STYLES = {
  critical: { dot: "bg-red-500", text: "text-red-700", bg: "bg-red-50" },
  warning: { dot: "bg-orange-400", text: "text-orange-700", bg: "bg-orange-50" },
  info: { dot: "bg-yellow-400", text: "text-yellow-700", bg: "bg-yellow-50" },
};

export default function SeoSummary({ data }: SeoSummaryProps) {
  const issues = data.issues || [];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="flex items-baseline justify-between mb-2">
          <h3 className="text-lg font-semibold text-gray-900">Sante SEO</h3>
          <span className="text-sm text-gray-400">
            {data.total_crawled} page{data.total_crawled > 1 ? "s" : ""} analysee{data.total_crawled > 1 ? "s" : ""}
          </span>
        </div>

        {issues.length === 0 ? (
          <div className="rounded-lg bg-green-50 border border-green-200 p-4 mt-3">
            <p className="text-green-700 font-medium">
              Aucun probleme majeur detecte. Votre site est en bonne sante technique.
            </p>
          </div>
        ) : (
          <div className="space-y-2 mt-4">
            {issues.map((issue) => {
              const style = SEVERITY_STYLES[issue.severity];
              return (
                <div
                  key={issue.key}
                  className={`flex items-start gap-3 rounded-lg ${style.bg} px-4 py-3`}
                >
                  <span className={`w-2.5 h-2.5 rounded-full ${style.dot} mt-1.5 flex-shrink-0`} />
                  <p className={`${style.text}`}>
                    <span className="font-bold text-lg">{issue.count}</span>{" "}
                    {issue.label}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Sitemap info */}
      {data.sitemap_urls > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-4">
          <p className="text-gray-600">
            <span className="font-medium">Sitemap</span> : {data.sitemap_urls} URL{data.sitemap_urls > 1 ? "s" : ""} declaree{data.sitemap_urls > 1 ? "s" : ""}
            {data.sitemap_errors > 0 && (
              <span className="text-red-600 font-medium">
                , {data.sitemap_errors} en erreur
              </span>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
