export function getScoreColor(score: number): string {
  if (score >= 90) return "#0cce6b";
  if (score >= 50) return "#ffa400";
  return "#ff4e42";
}

export function getVerdictLabel(score: number): string {
  if (score >= 90) return "Excellent";
  if (score >= 70) return "Correct";
  if (score >= 50) return "A ameliorer";
  return "Critique";
}

export function getVerdictColor(category: string): string {
  switch (category) {
    case "FAST":
      return "#0cce6b";
    case "AVERAGE":
      return "#ffa400";
    case "SLOW":
      return "#ff4e42";
    default:
      return "#888";
  }
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 o";
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function formatSeconds(s: number): string {
  return `${s.toFixed(1)} s`;
}

interface MetricConfig {
  name: string;
  explain: (val: number) => string;
  thresholds: { good: number; medium: number };
  format: (val: number) => string;
}

export const METRIC_LABELS: Record<string, MetricConfig> = {
  LCP: {
    name: "Temps d'affichage",
    explain: (val: number) =>
      `Votre page met ${(val / 1000).toFixed(1)} secondes a afficher son contenu principal.`,
    thresholds: { good: 2500, medium: 4000 },
    format: (val: number) => `${(val / 1000).toFixed(1)}s`,
  },
  CLS: {
    name: "Stabilite visuelle",
    explain: (val: number) =>
      val > 0.25
        ? "Les elements de votre page bougent pendant le chargement, ce qui gene vos visiteurs."
        : "Votre page est visuellement stable pendant le chargement.",
    thresholds: { good: 0.1, medium: 0.25 },
    format: (val: number) => val.toFixed(2),
  },
  INP: {
    name: "Reactivite",
    explain: (val: number) =>
      `Quand un visiteur clique, votre site met ${Math.round(val)}ms a reagir.`,
    thresholds: { good: 200, medium: 500 },
    format: (val: number) => `${Math.round(val)}ms`,
  },
  TTFB: {
    name: "Temps de reponse serveur",
    explain: (val: number) =>
      `Votre serveur met ${(val / 1000).toFixed(1)} secondes a commencer a repondre.`,
    thresholds: { good: 800, medium: 1800 },
    format: (val: number) => `${(val / 1000).toFixed(1)}s`,
  },
  TBT: {
    name: "Temps de blocage",
    explain: (val: number) =>
      `Le navigateur est bloque pendant ${Math.round(val)}ms lors du chargement.`,
    thresholds: { good: 200, medium: 600 },
    format: (val: number) => `${Math.round(val)}ms`,
  },
};

export function getMetricVerdict(
  value: number,
  thresholds: { good: number; medium: number },
): { label: string; color: string } {
  if (value <= thresholds.good) return { label: "Bon", color: "#0cce6b" };
  if (value <= thresholds.medium) return { label: "Moyen", color: "#ffa400" };
  return { label: "Lent", color: "#ff4e42" };
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
