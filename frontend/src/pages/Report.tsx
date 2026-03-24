import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getReport, type AuditReport } from "../lib/api";
import {
  formatDate,
  formatSeconds,
  getScoreColor,
  getVerdictLabel,
} from "../lib/formatting";
import ScoreGauge from "../components/ScoreGauge";
import MetricCard from "../components/MetricCard";
import CruxPanel from "../components/CruxPanel";
import PageWeightBreakdown from "../components/PageWeightBreakdown";

export default function Report() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<AuditReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;

    let active = true;
    const load = async () => {
      try {
        const data = await getReport(id);
        if (active) {
          setReport(data);
          setLoading(false);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Erreur de chargement");
          setLoading(false);
        }
      }
    };

    load();
    // Polling if still running
    const interval = setInterval(async () => {
      try {
        const data = await getReport(id);
        if (active) setReport(data);
        if (data.status === "done" || data.status === "failed") clearInterval(interval);
      } catch {
        /* ignore */
      }
    }, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [id]);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4" />
          <p className="text-gray-500">Chargement du rapport...</p>
        </div>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-500 text-lg mb-4">{error || "Rapport introuvable"}</p>
          <Link to="/" className="text-blue-600 hover:underline">Retour au dashboard</Link>
        </div>
      </div>
    );
  }

  const isRunning = report.status === "running" || report.status === "pending";
  const lm = report.lighthouse_mobile;
  const ttfb = report.ttfb_data;
  const score = report.numos_score;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Back link */}
        <Link to="/" className="text-sm text-gray-400 hover:text-gray-600 mb-6 inline-block">
          &larr; Retour au dashboard
        </Link>

        {/* Header */}
        <header className="bg-white rounded-2xl border border-gray-200 p-8 mb-6">
          <div className="flex items-start gap-6">
            {report.screenshot_url && (
              <img
                src={report.screenshot_url}
                alt={`Capture de ${report.domain}`}
                className="w-64 rounded-lg border border-gray-200 shadow-sm flex-shrink-0"
              />
            )}
            <div>
              <p className="text-sm text-gray-400 uppercase tracking-wide mb-1">Audit de performance & SEO</p>
              <h1 className="text-3xl font-bold text-gray-900">{report.domain}</h1>
              <p className="text-gray-500 mt-1">Audit realise le {formatDate(report.created_at)}</p>
              {isRunning && (
                <div className="mt-3 flex items-center gap-2">
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600" />
                  <span className="text-blue-600 text-sm font-medium">Audit en cours...</span>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Score Numos */}
        {score && (
          <section className="bg-white rounded-2xl border border-gray-200 p-8 mb-6 text-center">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 mb-6">
              Score Numos
            </h2>
            <div className="relative inline-flex">
              <ScoreGauge score={score.global} size={200} />
            </div>
            <div className="flex justify-center gap-8 mt-8">
              {score.pillars.performance != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.performance} size={80} label="Performance" />
                </div>
              )}
              {score.pillars.crux != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.crux} size={80} label="CrUX" />
                </div>
              )}
              {score.pillars.ttfb != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.ttfb} size={80} label="TTFB" />
                </div>
              )}
              {score.pillars.seo != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.seo} size={80} label="SEO" />
                </div>
              )}
            </div>
          </section>
        )}

        {/* Performance */}
        {lm && (
          <section className="bg-white rounded-2xl border border-gray-200 p-8 mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Performance</h2>
            {lm.performance_score != null && (
              <p className="text-gray-500 mb-6">
                Google note votre site{" "}
                <span
                  className="font-bold"
                  style={{ color: getScoreColor(lm.performance_score * 100) }}
                >
                  {Math.round(lm.performance_score * 100)}/100
                </span>{" "}
                sur mobile
              </p>
            )}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <MetricCard metricKey="LCP" value={lm.lcp.value} />
              <MetricCard metricKey="CLS" value={lm.cls.value} />
              <MetricCard metricKey="TBT" value={lm.tbt.value} />
            </div>
          </section>
        )}

        {/* CrUX */}
        <section className="mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Donnees terrain (28 derniers jours)
          </h2>
          <div className="space-y-4">
            <CruxPanel data={report.crux_url} label="Cette page" />
            {report.crux_origin && (
              <CruxPanel data={report.crux_origin} label="Ensemble du domaine" />
            )}
          </div>
        </section>

        {/* TTFB */}
        {ttfb && (
          <section className="bg-white rounded-2xl border border-gray-200 p-8 mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Vitesse du serveur</h2>
            <p className="text-lg text-gray-700 mb-4">
              Votre serveur repond en{" "}
              <span
                className="font-bold text-2xl"
                style={{ color: getScoreColor(ttfb.ttfb_seconds <= 0.5 ? 90 : ttfb.ttfb_seconds <= 1.0 ? 60 : 20) }}
              >
                {formatSeconds(ttfb.ttfb_seconds)}
              </span>
            </p>

            {/* Comparative bars */}
            <div className="space-y-3 mb-4">
              <div>
                <div className="flex justify-between text-sm text-gray-500 mb-1">
                  <span>Votre site</span>
                  <span>{formatSeconds(ttfb.ttfb_seconds)}</span>
                </div>
                <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.min((ttfb.ttfb_seconds / 3) * 100, 100)}%`,
                      backgroundColor: getScoreColor(ttfb.ttfb_seconds <= 0.5 ? 90 : ttfb.ttfb_seconds <= 1.0 ? 60 : 20),
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-sm text-gray-500 mb-1">
                  <span>Site bien heberge</span>
                  <span>0.3s</span>
                </div>
                <div className="h-4 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-green-500"
                    style={{ width: `${(0.3 / 3) * 100}%` }}
                  />
                </div>
              </div>
            </div>

            {ttfb.ttfb_seconds > 0.5 && (
              <p className="text-gray-600">
                Votre serveur est{" "}
                <span className="font-bold">{Math.round(ttfb.ttfb_seconds / 0.3)}x plus lent</span>{" "}
                qu'un site WordPress sur un hebergement adapte.
              </p>
            )}
          </section>
        )}

        {/* Page Weight */}
        {report.page_weight && (
          <section className="mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">Poids de la page</h2>
            <PageWeightBreakdown data={report.page_weight} />
          </section>
        )}

        {/* SEO placeholder */}
        <section className="bg-white rounded-2xl border border-gray-200 p-8 mb-6">
          <h2 className="text-xl font-bold text-gray-900 mb-2">Sante SEO</h2>
          <p className="text-gray-400">Analyse SEO detaillee — bientot disponible.</p>
        </section>

        {/* Footer */}
        <footer className="text-center py-8 border-t border-gray-200 mt-8">
          <p className="text-gray-500">
            Audit realise par{" "}
            <a href="https://numos.fr" target="_blank" rel="noopener noreferrer" className="text-blue-600 font-medium hover:underline">
              Numos
            </a>
          </p>
          <a
            href="https://calendly.com/numos"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-3 rounded-lg bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition-colors"
          >
            Prendre rendez-vous
          </a>
        </footer>
      </div>
    </div>
  );
}
