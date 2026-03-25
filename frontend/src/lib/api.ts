const API_BASE = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || res.statusText);
  }
  return res.json();
}

export interface AuditListItem {
  id: string;
  url: string;
  domain: string;
  status: string;
  created_at: string;
  numos_score: { global: number; pillars: Record<string, number | null> } | null;
}

export interface LighthouseMetric {
  score: number | null;
  value: number | null;
  display: string | null;
}

export interface LighthouseMetrics {
  performance_score: number | null;
  seo_score: number | null;
  lcp: LighthouseMetric;
  cls: LighthouseMetric;
  tbt: LighthouseMetric;
  speed_index: LighthouseMetric;
  tti: LighthouseMetric;
  ttfb: LighthouseMetric;
}

export interface CruxMetric {
  percentile: number;
  distributions: { min: number; max?: number; proportion: number }[];
  category: string;
}

export interface CruxData {
  overall_category: string;
  metrics: Record<string, CruxMetric>;
}

export interface TtfbData {
  ttfb_seconds: number;
  samples: number[];
  verdict: string;
}

export interface PageWeightData {
  total_requests: number;
  total_size_bytes: number;
  by_type: Record<string, { count: number; size_bytes: number }>;
  third_party_count: number;
  third_party_size_bytes: number;
  unoptimized_images: {
    count: number;
    total_size_bytes: number;
    images: { url: string; size_bytes: number }[];
  };
}

export interface CrawlIssue {
  key: string;
  count: number;
  severity: "critical" | "warning" | "info";
  label: string;
}

export interface CrawlSummary {
  total_crawled: number;
  total_errors: number;
  pages_ok: number;
  pages_404: number;
  pages_500: number;
  pages_301: number;
  missing_titles: number;
  missing_descriptions: number;
  missing_h1: number;
  multiple_h1: number;
  images_without_alt: number;
  deep_pages: number;
  noindex_pages: number;
  broken_internal_links: number;
  sitemap_urls: number;
  sitemap_errors: number;
  issues: CrawlIssue[];
}

export interface AuditReport {
  id: string;
  url: string;
  domain: string;
  status: string;
  created_at: string;
  screenshot_url: string | null;
  numos_score: { global: number; pillars: Record<string, number | null>; weights_used: Record<string, number> } | null;
  lighthouse_mobile: LighthouseMetrics | null;
  lighthouse_desktop: LighthouseMetrics | null;
  crux_url: CruxData | null;
  crux_origin: CruxData | null;
  ttfb_data: TtfbData | null;
  page_weight: PageWeightData | null;
  crawl_status: string | null;
  crawl_progress: { crawled: number; queued: number; errors: number } | null;
  crawl_summary: CrawlSummary | null;
}

export function createAudit(url: string) {
  return request<{ id: string; url: string; domain: string; status: string }>(
    "/api/audits",
    { method: "POST", body: JSON.stringify({ url }) },
  );
}

export function getAudits() {
  return request<AuditListItem[]>("/api/audits");
}

export function getAuditProgress(id: string) {
  return request<{ id: string; status: string }>(`/api/audits/${id}/progress`);
}

export function getReport(id: string) {
  return request<AuditReport>(`/api/audits/${id}/report`);
}

export function deleteAudit(id: string) {
  return request<{ ok: boolean }>(`/api/audits/${id}`, { method: "DELETE" });
}
