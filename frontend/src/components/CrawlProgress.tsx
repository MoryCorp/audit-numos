interface CrawlProgressProps {
  progress: { crawled: number; queued: number; errors: number } | null;
}

export default function CrawlProgress({ progress }: CrawlProgressProps) {
  const crawled = progress?.crawled ?? 0;

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-6">
      <div className="flex items-center gap-3 mb-3">
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600" />
        <h3 className="text-lg font-semibold text-blue-900">Analyse SEO en cours</h3>
      </div>
      <p className="text-blue-700 text-2xl font-bold mb-1">
        {crawled} page{crawled > 1 ? "s" : ""} analysee{crawled > 1 ? "s" : ""}
      </p>
      {progress && progress.queued > 0 && (
        <div className="mt-3">
          <div className="h-2 bg-blue-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-600 rounded-full transition-all duration-500"
              style={{
                width: `${Math.min((crawled / (crawled + progress.queued)) * 100, 100)}%`,
              }}
            />
          </div>
          <p className="text-xs text-blue-500 mt-1">
            {progress.queued} page{progress.queued > 1 ? "s" : ""} restante{progress.queued > 1 ? "s" : ""}
          </p>
        </div>
      )}
      <p className="text-sm text-blue-600 mt-2">
        Le rapport se met a jour automatiquement.
      </p>
    </div>
  );
}
