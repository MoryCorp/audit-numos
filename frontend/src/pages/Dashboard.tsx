import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createAudit, deleteAudit, getAudits, type AuditListItem } from "../lib/api";
import { formatDate, getScoreColor } from "../lib/formatting";

export default function Dashboard() {
  const [audits, setAudits] = useState<AuditListItem[]>([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchAudits = async () => {
    try {
      setAudits(await getAudits());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    fetchAudits();
    const interval = setInterval(fetchAudits, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    try {
      let normalizedUrl = url.trim();
      if (!/^https?:\/\//i.test(normalizedUrl)) {
        normalizedUrl = `https://${normalizedUrl}`;
      }
      await createAudit(normalizedUrl);
      setUrl("");
      await fetchAudits();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur lors de la creation de l'audit");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteAudit(id);
      await fetchAudits();
    } catch {
      /* ignore */
    }
  };

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      pending: "bg-gray-100 text-gray-700",
      running: "bg-blue-100 text-blue-700",
      partial: "bg-blue-100 text-blue-700",
      done: "bg-green-100 text-green-700",
      failed: "bg-red-100 text-red-700",
    };
    const labels: Record<string, string> = {
      pending: "En attente",
      running: "En cours...",
      partial: "Analyse SEO...",
      done: "Termine",
      failed: "Echoue",
    };
    return (
      <span className={`inline-block rounded-full px-3 py-1 text-sm font-medium ${styles[status] || styles.pending}`}>
        {labels[status] || status}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <h1 className="text-2xl font-bold text-gray-900">Numos Audit</h1>
          <p className="text-gray-500 mt-1">Audit de performance et SEO pour sites WordPress</p>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <form onSubmit={handleSubmit} className="flex gap-3 mb-10">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="flex-1 rounded-lg border border-gray-300 px-4 py-3 text-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !url.trim()}
            className="rounded-lg bg-blue-600 px-6 py-3 text-lg font-medium text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Lancement..." : "Lancer l'audit"}
          </button>
        </form>

        {error && (
          <div className="mb-6 rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
            {error}
          </div>
        )}

        {audits.length === 0 ? (
          <p className="text-center text-gray-400 py-12">Aucun audit pour le moment. Lancez-en un !</p>
        ) : (
          <div className="space-y-3">
            {audits.map((audit) => (
              <div
                key={audit.id}
                className="bg-white rounded-lg border border-gray-200 p-5 flex items-center justify-between hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  {audit.numos_score && (
                    <div
                      className="text-2xl font-bold w-16 text-center flex-shrink-0"
                      style={{ color: getScoreColor(audit.numos_score.global) }}
                    >
                      {audit.numos_score.global}
                    </div>
                  )}
                  {!audit.numos_score && <div className="w-16 flex-shrink-0" />}
                  <div className="min-w-0">
                    <Link
                      to={`/rapport/${audit.id}`}
                      className="text-lg font-medium text-gray-900 hover:text-blue-600 truncate block"
                    >
                      {audit.domain}
                    </Link>
                    <p className="text-sm text-gray-400">{formatDate(audit.created_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 flex-shrink-0">
                  {getStatusBadge(audit.status)}
                  {(audit.status === "done" || audit.status === "partial") && (
                    <Link
                      to={`/rapport/${audit.id}`}
                      className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                    >
                      Voir le rapport
                    </Link>
                  )}
                  <button
                    onClick={() => handleDelete(audit.id)}
                    className="text-gray-400 hover:text-red-500 transition-colors"
                    title="Supprimer"
                  >
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
