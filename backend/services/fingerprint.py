"""Detection des technologies marketing et analytics d'un site.

Sert a qualifier un prospect avant de l'appeler : un site avec un tag Google Ads,
une CMP et un tunnel e-commerce investit dans son acquisition, un site sans aucun
tracking est une vitrine qui ne fait pas de business en ligne.

La detection croise deux sources :

- le log reseau du navigateur (les tags qui se chargent reellement)
- le DOM rendu (les tags presents mais neutralises par une CMP)

Ce croisement est ce qui permet de voir un tag derriere une CMP. Trois cas :

- Consent Mode v2 : le script se charge quand meme, en mode denied -> vu en reseau
- blocage dur (type="text/plain") : le script ne se charge pas mais l'ID reste
  dans le DOM -> vu en HTML
- tagging server-side : les URL tierces n'apparaissent jamais, on se rabat sur
  la detection d'un endpoint first-party (voir detect_server_side_tagging)

Un tag detecte prouve que le site a ete configure pour de l'acquisition payante,
pas qu'il depense aujourd'hui : un tag survit des annees au depart d'une agence.
"""

import re
from urllib.parse import urlparse

# Suffixes publics a deux niveaux les plus courants sur nos prospects.
# Une vraie Public Suffix List serait plus exacte mais disproportionnee ici.
MULTI_LABEL_SUFFIXES = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "net.au", "org.au",
    "co.jp", "com.br", "co.nz", "com.tr", "co.za", "com.es",
    # Plateformes multi-locataires : chaque sous-domaine est un site distinct,
    # sinon tout autre locataire de la plateforme compterait comme first-party.
    "vercel.app", "netlify.app", "github.io", "pages.dev", "web.app",
    "firebaseapp.com", "herokuapp.com", "wixsite.com", "webflow.io",
    "myshopify.com", "wordpress.com", "blogspot.com", "squarespace.com",
    "weebly.com", "jimdofree.com", "jimdosite.com", "e-monsite.com",
}

GOOGLE_TAG_HOSTS = (
    "googletagmanager.com",
    "google-analytics.com",
    "googleadservices.com",
    "doubleclick.net",
    "google.com",
)

# Chaque entree : patterns URL (log reseau), patterns HTML (DOM rendu),
# et optionnellement une regex de capture d'identifiant.
TRACKERS: dict[str, dict] = {
    "google_ads": {
        "label": "Google Ads",
        "category": "ads",
        "url": [
            r"googletagmanager\.com/gtag/js\?[^\s\"']*\bid=AW-",
            r"googleadservices\.com/pagead/conversion",
            r"googleads\.g\.doubleclick\.net/pagead/viewthroughconversion",
        ],
        "html": [r"\bAW-\d{9,11}\b"],
        "ids": r"\b(AW-\d{9,11})\b",
    },
    "google_tag_manager": {
        "label": "Google Tag Manager",
        "category": "tag_manager",
        "url": [r"googletagmanager\.com/gtm\.js\?[^\s\"']*\bid=GTM-"],
        "html": [r"\bGTM-[A-Z0-9]{6,8}\b"],
        "ids": r"\b(GTM-[A-Z0-9]{6,8})\b",
    },
    "google_analytics_4": {
        "label": "Google Analytics 4",
        "category": "analytics",
        "url": [
            r"googletagmanager\.com/gtag/js\?[^\s\"']*\bid=G-",
            r"google-analytics\.com/g/collect",
            r"analytics\.google\.com/g/collect",
        ],
        "html": [r"\bG-[A-Z0-9]{10}\b"],
        "ids": r"\b(G-[A-Z0-9]{10})\b",
    },
    "universal_analytics": {
        "label": "Universal Analytics (obsolete)",
        "category": "analytics",
        "url": [r"google-analytics\.com/(analytics|ga)\.js"],
        "html": [r"\bUA-\d{4,10}-\d{1,4}\b"],
        "ids": r"\b(UA-\d{4,10}-\d{1,4})\b",
    },
    "floodlight": {
        "label": "Campaign Manager / Floodlight",
        "category": "ads",
        "url": [r"fls\.doubleclick\.net", r"ad\.doubleclick\.net/activity"],
        "html": [],
    },
    "meta_pixel": {
        "label": "Meta Pixel",
        "category": "ads",
        "url": [r"connect\.facebook\.net/[^/]+/fbevents\.js", r"facebook\.com/tr\?"],
        "html": [r"fbq\s*\(\s*['\"]init['\"]"],
        "ids": r"fbq\s*\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})['\"]",
    },
    "linkedin_insight": {
        "label": "LinkedIn Insight Tag",
        "category": "ads",
        "url": [r"snap\.licdn\.com/li\.lms-analytics", r"px\.ads\.linkedin\.com"],
        "html": [r"_linkedin_partner_id"],
    },
    "microsoft_uet": {
        "label": "Microsoft Ads (UET)",
        "category": "ads",
        "url": [r"bat\.bing\.com/(bat\.js|action|p/insights)"],
        "html": [r"\buetq\b"],
    },
    "tiktok_pixel": {
        "label": "TikTok Pixel",
        "category": "ads",
        "url": [r"analytics\.tiktok\.com/i18n/pixel"],
        "html": [r"ttq\.load\s*\("],
    },
    "criteo": {
        "label": "Criteo",
        "category": "ads",
        "url": [r"static\.criteo\.net", r"sslwidget\.criteo\.com"],
        "html": [],
    },
    "hotjar": {
        "label": "Hotjar",
        "category": "behavior",
        "url": [r"static\.hotjar\.com", r"script\.hotjar\.com"],
        "html": [r"\bhjid\b"],
    },
    "microsoft_clarity": {
        "label": "Microsoft Clarity",
        "category": "behavior",
        "url": [r"\.clarity\.ms/tag/"],
        "html": [r"clarity\.ms/tag/"],
    },
    "matomo": {
        "label": "Matomo",
        "category": "analytics",
        "url": [r"/(matomo|piwik)\.js\b"],
        "html": [r"_paq\.push"],
    },
    "plausible": {
        "label": "Plausible",
        "category": "analytics",
        "url": [r"plausible\.io/js/"],
        "html": [],
    },
}

CMP_VENDORS: dict[str, dict] = {
    "onetrust": {
        "label": "OneTrust",
        "url": [r"cdn\.cookielaw\.org", r"optanon"],
        "html": [r"OptanonWrapper|onetrust"],
    },
    "cookiebot": {
        "label": "Cookiebot",
        "url": [r"consent\.cookiebot\.(com|eu)"],
        "html": [r"Cookiebot"],
    },
    "axeptio": {
        "label": "Axeptio",
        "url": [r"static\.axept\.io"],
        "html": [r"axeptio(Settings|_authorized)"],
    },
    "didomi": {
        "label": "Didomi",
        "url": [r"(sdk|api)\.privacy-center\.org"],
        "html": [r"\bDidomi\b|didomiConfig"],
    },
    "iubenda": {
        "label": "Iubenda",
        "url": [r"cdn\.iubenda\.com"],
        "html": [r"_iub\b|iubenda"],
    },
    "cookieyes": {
        "label": "CookieYes",
        "url": [r"cdn-cookieyes\.com"],
        "html": [r"cookieyes"],
    },
    "complianz": {
        "label": "Complianz",
        "url": [r"/plugins/complianz"],
        "html": [r"complianz|cmplz-"],
    },
    "tarteaucitron": {
        "label": "Tarteaucitron",
        "url": [r"tarteaucitron"],
        "html": [r"tarteaucitron"],
    },
    "borlabs": {
        "label": "Borlabs Cookie",
        "url": [r"borlabs-cookie"],
        "html": [r"borlabs-cookie|BorlabsCookie"],
    },
    "sirdata": {
        "label": "Sirdata",
        "url": [r"cmp\.sirdata\.com", r"choices\.consentframework\.com"],
        "html": [r"sddan|sirdata"],
    },
}

CMS_SIGNATURES: dict[str, dict] = {
    "wordpress": {
        "label": "WordPress",
        "url": [r"/wp-content/", r"/wp-includes/"],
        "html": [r"/wp-content/", r"/wp-includes/", r'content=["\']WordPress'],
    },
    "shopify": {
        "label": "Shopify",
        "url": [r"cdn\.shopify\.com"],
        "html": [r"Shopify\.shop|cdn\.shopify\.com"],
    },
    "prestashop": {
        "label": "PrestaShop",
        "url": [r"/modules/ps_"],
        "html": [r'content=["\']PrestaShop|prestashop'],
    },
    "wix": {
        "label": "Wix",
        "url": [r"static\.parastorage\.com", r"static\.wixstatic\.com"],
        "html": [r"wix-?(site|code)|X-Wix"],
    },
    "squarespace": {
        "label": "Squarespace",
        "url": [r"static1\.squarespace\.com"],
        "html": [r"squarespace"],
    },
    "webflow": {
        "label": "Webflow",
        "url": [r"assets\.website-files\.com", r"cdn\.prod\.website-files\.com"],
        "html": [r'content=["\']Webflow|data-wf-'],
    },
    "drupal": {
        "label": "Drupal",
        "url": [r"/sites/default/files/"],
        "html": [r'content=["\']Drupal|drupal-settings-json'],
    },
    "joomla": {
        "label": "Joomla",
        "url": [r"/media/jui/"],
        "html": [r'content=["\']Joomla'],
    },
}

ECOMMERCE_SIGNATURES: dict[str, dict] = {
    "woocommerce": {
        "label": "WooCommerce",
        "url": [r"/plugins/woocommerce/"],
        "html": [r"woocommerce"],
    },
    "shopify_checkout": {
        "label": "Shopify",
        "url": [r"cdn\.shopify\.com"],
        "html": [r"Shopify\.checkout|shopify-payment-button"],
    },
    "stripe": {
        "label": "Stripe",
        "url": [r"js\.stripe\.com"],
        "html": [],
    },
    "paypal": {
        "label": "PayPal",
        "url": [r"paypal\.com/sdk/js", r"paypalobjects\.com"],
        "html": [],
    },
}

# Endpoints exposes par un conteneur GTM server-side heberge en first-party.
SERVER_SIDE_PATHS = re.compile(
    r"/(gtm|gtag)\.js\b|/g/collect\b|/gtm/|/gc/|/metrics/collect\b", re.IGNORECASE
)

WP_VERSION = re.compile(r'content=["\']WordPress\s+([0-9.]+)', re.IGNORECASE)


def registrable_domain(host: str) -> str:
    """Domaine enregistrable approximatif : les deux derniers labels, trois si
    le suffixe est un suffixe public a deux niveaux connu."""
    host = (host or "").lower().strip().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _matches(patterns: list[str], blob: str) -> bool:
    return any(re.search(p, blob, re.IGNORECASE) for p in patterns)


def _scan(signatures: dict[str, dict], urls_blob: str, html: str) -> dict[str, dict]:
    found = {}
    for key, cfg in signatures.items():
        via = []
        if _matches(cfg.get("url", []), urls_blob):
            via.append("network")
        if _matches(cfg.get("html", []), html):
            via.append("html")
        if not via:
            continue
        entry = {"label": cfg["label"], "detected_via": via}
        if "category" in cfg:
            entry["category"] = cfg["category"]
        if cfg.get("ids"):
            # Pas de re.IGNORECASE : la casse fait partie du format des identifiants.
            ids = sorted(set(re.findall(cfg["ids"], urls_blob + "\n" + html)))
            if ids:
                entry["ids"] = ids[:5]
        found[key] = entry
    return found


def detect_server_side_tagging(requests_log: list[dict], base_url: str) -> dict:
    """Repere un conteneur GTM server-side servi depuis le domaine du prospect.

    Personne ne met en place un sGTM sans depenser reellement en acquisition,
    donc c'est un signal de maturite fort meme quand on ne peut plus attribuer
    les tags individuellement.
    """
    base = registrable_domain(urlparse(base_url).netloc)
    for entry in requests_log:
        url = entry.get("url", "")
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        if "stape.io" in host:
            return {"detected": True, "host": host, "provider": "stape"}
        if any(host.endswith(g) for g in GOOGLE_TAG_HOSTS):
            continue
        if registrable_domain(host) != base:
            continue
        if SERVER_SIDE_PATHS.search(url):
            return {"detected": True, "host": host, "provider": "self-hosted"}
    return {"detected": False, "host": None, "provider": None}


def detect_technologies(requests_log: list[dict], html: str, base_url: str) -> dict:
    """Analyse le log reseau et le DOM rendu, retourne les technologies detectees
    plus un resume booleen directement exploitable pour trier des prospects."""
    urls_blob = "\n".join(entry.get("url", "") for entry in (requests_log or []))
    html = html or ""

    trackers = _scan(TRACKERS, urls_blob, html)
    cmp_found = _scan(CMP_VENDORS, urls_blob, html)
    cms_found = _scan(CMS_SIGNATURES, urls_blob, html)
    ecommerce_found = _scan(ECOMMERCE_SIGNATURES, urls_blob, html)
    server_side = detect_server_side_tagging(requests_log or [], base_url)

    ads = [k for k, v in trackers.items() if v.get("category") == "ads"]
    analytics = [k for k, v in trackers.items() if v.get("category") == "analytics"]
    behavior = [k for k, v in trackers.items() if v.get("category") == "behavior"]

    wp_version = None
    if "wordpress" in cms_found:
        match = WP_VERSION.search(html)
        if match:
            wp_version = match.group(1)
            cms_found["wordpress"]["version"] = wp_version

    # Un tag vu uniquement dans le DOM signale un blocage par la CMP : le site
    # est bien equipe, le tag ne s'execute simplement pas sans consentement.
    blocked_by_cmp = sorted(
        key for key, value in trackers.items() if value["detected_via"] == ["html"]
    )

    return {
        "trackers": trackers,
        "cmp": cmp_found,
        "cms": cms_found,
        "ecommerce": ecommerce_found,
        "server_side_tagging": server_side,
        "blocked_by_cmp": blocked_by_cmp,
        "summary": {
            "is_wordpress": "wordpress" in cms_found,
            "wordpress_version": wp_version,
            "has_google_ads": "google_ads" in trackers,
            "has_ads_tag": bool(ads),
            "has_analytics": bool(analytics),
            "has_behavior_analytics": bool(behavior),
            "has_tag_manager": "google_tag_manager" in trackers,
            "has_ecommerce": bool(ecommerce_found),
            "has_cmp": bool(cmp_found),
            "has_server_side_tagging": server_side["detected"],
            "ads_platforms": sorted(ads),
            "cmp_vendors": sorted(cmp_found),
            "tracking_stack_size": len(trackers),
        },
    }
