"""Regression sur la detection des technologies.

Les patterns evoluent (nouvelles CMP, nouveaux tags) : ces cas verrouillent les
deux regimes qui comptent pour la qualification, tag charge et tag bloque par
une CMP, ainsi que l'absence de faux positif sur un site vitrine.

    cd backend && python -m pytest tests/
"""

from services.fingerprint import detect_technologies, registrable_domain


def net(*urls):
    return [{"url": u, "status": 200, "size": 100, "type": "script"} for u in urls]


def test_registrable_domain():
    assert registrable_domain("www.exemple.fr") == "exemple.fr"
    assert registrable_domain("cdn.exemple.fr") == "exemple.fr"
    assert registrable_domain("exemple.fr") == "exemple.fr"
    # Un endswith naif classait faux-exemple.fr comme first-party.
    assert registrable_domain("faux-exemple.fr") != registrable_domain("exemple.fr")
    assert registrable_domain("shop.exemple.co.uk") == "exemple.co.uk"


def test_consent_mode_tag_charge_en_denied():
    """Consent Mode v2 : le script se charge meme sans consentement."""
    result = detect_technologies(
        net(
            "https://www.googletagmanager.com/gtag/js?id=AW-11223344556",
            "https://static.axept.io/sdk.js",
        ),
        "<html><body></body></html>",
        "https://exemple.fr",
    )
    assert result["summary"]["has_google_ads"] is True
    assert result["trackers"]["google_ads"]["ids"] == ["AW-11223344556"]
    assert result["trackers"]["google_ads"]["detected_via"] == ["network"]
    assert result["summary"]["cmp_vendors"] == ["axeptio"]
    assert result["blocked_by_cmp"] == []


def test_blocage_dur_tag_present_dans_le_dom():
    """Blocage dur : le script ne part jamais mais l'ID reste dans le DOM."""
    result = detect_technologies(
        net("https://exemple.fr/wp-content/plugins/complianz-gdpr/cookiebanner.js"),
        """<script type="text/plain" data-service="google-ads"
                   src="https://www.googletagmanager.com/gtag/js?id=AW-987654321"></script>
           <script type="text/plain">fbq('init', '123456789012345');</script>""",
        "https://exemple.fr",
    )
    assert result["summary"]["has_google_ads"] is True
    assert result["trackers"]["google_ads"]["detected_via"] == ["html"]
    assert result["trackers"]["meta_pixel"]["ids"] == ["123456789012345"]
    assert result["blocked_by_cmp"] == ["google_ads", "meta_pixel"]
    assert result["summary"]["cmp_vendors"] == ["complianz"]


def test_tagging_server_side_first_party():
    result = detect_technologies(
        net("https://sgtm.exemple.fr/gtm.js?id=GTM-XYZ9876"),
        "",
        "https://www.exemple.fr",
    )
    assert result["summary"]["has_server_side_tagging"] is True
    assert result["server_side_tagging"]["host"] == "sgtm.exemple.fr"


def test_gtm_officiel_nest_pas_du_server_side():
    result = detect_technologies(
        net("https://www.googletagmanager.com/gtm.js?id=GTM-XYZ9876"),
        "",
        "https://exemple.fr",
    )
    assert result["summary"]["has_server_side_tagging"] is False
    assert result["summary"]["has_tag_manager"] is True


def test_wordpress_woocommerce_ga4():
    result = detect_technologies(
        net(
            "https://exemple.fr/wp-content/plugins/woocommerce/assets/js/cart.min.js",
            "https://www.googletagmanager.com/gtag/js?id=G-ABCDE12345",
        ),
        '<meta name="generator" content="WordPress 6.4.2" />',
        "https://exemple.fr",
    )
    assert result["summary"]["is_wordpress"] is True
    assert result["summary"]["wordpress_version"] == "6.4.2"
    assert result["summary"]["has_ecommerce"] is True
    assert result["trackers"]["google_analytics_4"]["ids"] == ["G-ABCDE12345"]
    # GA4 est de l'analytics, pas une regie : ne doit pas compter comme tag pub.
    assert result["summary"]["has_ads_tag"] is False


def test_vitrine_sans_tracking():
    result = detect_technologies(
        net("https://exemple.fr/style.css", "https://fonts.gstatic.com/s/x.woff2"),
        "<html><body><h1>Garage Martin</h1></body></html>",
        "https://exemple.fr",
    )
    assert result["trackers"] == {}
    assert result["summary"]["has_ads_tag"] is False
    assert result["summary"]["has_cmp"] is False
    assert result["summary"]["tracking_stack_size"] == 0


def test_entrees_vides():
    result = detect_technologies([], None, "https://exemple.fr")
    assert result["summary"]["tracking_stack_size"] == 0
    assert result["summary"]["has_server_side_tagging"] is False


def test_plateformes_multi_locataires():
    # Deux sites sur la meme plateforme ne sont pas le meme domaine.
    assert registrable_domain("debouchage69330.vercel.app") == "debouchage69330.vercel.app"
    assert registrable_domain("a.vercel.app") != registrable_domain("b.vercel.app")
    # Un asset servi par la plateforme n'est pas first-party pour autant.
    result = detect_technologies(
        net("https://autre-locataire.vercel.app/gtm.js?id=GTM-AAAA111"),
        "",
        "https://monsite.vercel.app",
    )
    assert result["summary"]["has_server_side_tagging"] is False
