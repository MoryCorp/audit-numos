import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getReport, type AuditReport } from "../lib/api";
import {
  formatDate,
  getScoreColor,
} from "../lib/formatting";
import ScoreGauge from "../components/ScoreGauge";
import MetricCard from "../components/MetricCard";
import CruxPanel from "../components/CruxPanel";
import PageWeightBreakdown from "../components/PageWeightBreakdown";
import CrawlProgress from "../components/CrawlProgress";
import SeoSummary from "../components/SeoSummary";

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
  const score = report.numos_score;

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
        {/* Back link */}
        <Link to="/" className="text-sm text-gray-400 hover:text-gray-600 mb-4 sm:mb-6 inline-block">
          &larr; Retour au dashboard
        </Link>

        {/* Header */}
        <header className="bg-white rounded-2xl border border-gray-200 p-5 sm:p-8 mb-4 sm:mb-6">
          <div className="flex flex-col sm:flex-row items-start gap-4 sm:gap-6">
            {report.screenshot_url && (
              <img
                src={report.screenshot_url}
                alt={`Capture de ${report.domain}`}
                className="w-full sm:w-64 rounded-lg border border-gray-200 shadow-sm flex-shrink-0"
              />
            )}
            <div>
              <p className="text-sm text-gray-400 uppercase tracking-wide mb-1">Audit de performance & SEO</p>
              <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">{report.domain}</h1>
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
          <section className="bg-white rounded-2xl border border-gray-200 p-5 sm:p-8 mb-4 sm:mb-6 text-center">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-400 mb-6">
              Score Numos
            </h2>
            <div className="relative inline-flex">
              <ScoreGauge score={score.global} size={180} />
            </div>
            <div className="flex flex-wrap justify-center gap-4 sm:gap-8 mt-6 sm:mt-8">
              {score.pillars.performance != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.performance} size={70} label="Performance" />
                </div>
              )}
              {score.pillars.crux != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.crux} size={70} label="CrUX" />
                </div>
              )}
              {score.pillars.ttfb != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.ttfb} size={70} label="Serveur" />
                </div>
              )}
              {score.pillars.seo != null && (
                <div className="text-center">
                  <ScoreGauge score={score.pillars.seo} size={70} label="SEO" />
                </div>
              )}
            </div>
          </section>
        )}

        {/* Performance */}
        {lm && (
          <section className="bg-white rounded-2xl border border-gray-200 p-5 sm:p-8 mb-4 sm:mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-1">Performance</h2>
            {lm.performance_score != null && (
              <p className="text-gray-500 mb-4 sm:mb-6">
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
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
              <MetricCard metricKey="LCP" value={lm.lcp.value} />
              <MetricCard metricKey="CLS" value={lm.cls.value} />
              <MetricCard metricKey="TBT" value={lm.tbt.value} />
            </div>
          </section>
        )}

        {/* CrUX - domaine uniquement */}
        {report.crux_origin && (
          <section className="mb-4 sm:mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-3 sm:mb-4">
              Donnees terrain (28 derniers jours)
            </h2>
            <CruxPanel data={report.crux_origin} label="Ensemble du domaine" />
          </section>
        )}
        {!report.crux_origin && report.crux_url && (
          <section className="mb-4 sm:mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-3 sm:mb-4">
              Donnees terrain (28 derniers jours)
            </h2>
            <CruxPanel data={report.crux_url} label="Donnees terrain" />
          </section>
        )}
        {!report.crux_origin && !report.crux_url && (
          <section className="mb-4 sm:mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-3 sm:mb-4">
              Donnees terrain (28 derniers jours)
            </h2>
            <CruxPanel data={null} label="Donnees terrain" />
          </section>
        )}

        {/* Page Weight */}
        {report.page_weight && (
          <section className="mb-4 sm:mb-6">
            <h2 className="text-xl font-bold text-gray-900 mb-3 sm:mb-4">Poids de la page</h2>
            <PageWeightBreakdown data={report.page_weight} />
          </section>
        )}

        {/* SEO */}
        {report.crawl_status === "running" && (
          <section className="mb-4 sm:mb-6">
            <CrawlProgress progress={report.crawl_progress} />
          </section>
        )}
        {report.crawl_summary && (
          <section className="mb-4 sm:mb-6">
            <SeoSummary data={report.crawl_summary} />
          </section>
        )}

        {/* Footer */}
        <footer className="text-center py-6 sm:py-8 border-t border-gray-200 mt-6 sm:mt-8">
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
