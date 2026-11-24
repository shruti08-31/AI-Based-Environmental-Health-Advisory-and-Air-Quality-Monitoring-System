from dataclasses import dataclass
from urllib.parse import urlparse

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover
    DDGS = None  # type: ignore[assignment]


TRUSTED_WEB_SOURCES: dict[str, str] = {
    "cpcb.nic.in": "Central Pollution Control Board (CPCB India - Gov)",
    "moef.gov.in": "Ministry of Environment, Forest and Climate Change (MoEFCC India - Gov)",
    "mohfw.gov.in": "Ministry of Health and Family Welfare (MoHFW India - Gov)",
    "safar.tropmet.res.in": "SAFAR - Ministry of Earth Sciences (Gov of India)",
    "who.int": "World Health Organization (WHO)",
    "epa.gov": "U.S. Environmental Protection Agency (US EPA - Gov)",
    "airnow.gov": "AirNow (U.S. Gov Air Quality Portal)",
    "cdc.gov": "Centers for Disease Control and Prevention (CDC - Gov)",
    "eea.europa.eu": "European Environment Agency (EEA - Gov)",
    "unep.org": "United Nations Environment Programme (UNEP)",
    "aqicn.org": "World Air Quality Index Project (WAQI / AQICN)",
    "iqair.com": "IQAir Global Air Quality Information",
}


@dataclass(frozen=True)
class WebSourceSnippet:
    site_name: str
    domain: str
    title: str
    url: str
    snippet: str
    is_official_gov_or_un: bool


def _extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower().strip()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _match_trusted_source(domain: str) -> tuple[str, bool] | None:
    if not domain:
        return None
    for trusted_dom, label in TRUSTED_WEB_SOURCES.items():
        if domain == trusted_dom or domain.endswith("." + trusted_dom):
            is_gov = any(
                tag in trusted_dom
                for tag in (".gov", ".nic.in", ".res.in", "who.int", "unep.org", "europa.eu")
            )
            return label, is_gov
    if domain.endswith(".gov") or domain.endswith(".gov.in") or domain.endswith(".nic.in"):
        return f"Official Government Portal ({domain})", True
    return None


def search_trusted_environmental_websites(
    user_query: str,
    max_sources: int = 4,
) -> list[WebSourceSnippet]:
    """
    Search multiple trusted government and well-known environmental/health websites
    for up-to-date context and return structured snippets with source attribution.
    """
    cleaned = (user_query or "").strip()
    if not cleaned or DDGS is None:
        return []

    site_filter = (
        "(site:who.int OR site:epa.gov OR site:cpcb.nic.in OR site:airnow.gov "
        "OR site:cdc.gov OR site:eea.europa.eu OR site:unep.org OR site:aqicn.org OR site:iqair.com)"
    )
    targeted_query = f"{cleaned} air quality {site_filter}"

    raw_hits: list[dict[str, str]] = []
    try:
        with DDGS() as ddgs:
            raw_hits = list(ddgs.text(targeted_query, max_results=max_sources * 3))
    except Exception:
        raw_hits = []

    # Fallback broader query if strict site-filter returns too few items
    if len(raw_hits) < 2:
        try:
            with DDGS() as ddgs:
                extra = list(
                    ddgs.text(
                        f"{cleaned} air quality WHO EPA CPCB guidelines",
                        max_results=max_sources * 2,
                    )
                )
                raw_hits.extend(extra)
        except Exception:
            pass

    results: list[WebSourceSnippet] = []
    seen_domains: set[str] = set()

    for hit in raw_hits:
        url = str(hit.get("href") or hit.get("url") or "").strip()
        title = str(hit.get("title") or "").strip()
        body = str(hit.get("body") or hit.get("snippet") or "").strip()
        if not url or not body:
            continue

        domain = _extract_domain(url)
        matched = _match_trusted_source(domain)
        if matched is None:
            continue

        site_label, is_gov = matched
        # Prefer diverse websites (one primary result per trusted domain)
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        results.append(
            WebSourceSnippet(
                site_name=site_label,
                domain=domain,
                title=title or site_label,
                url=url,
                snippet=body[:450],
                is_official_gov_or_un=is_gov,
            )
        )
        if len(results) >= max_sources:
            break

    # Rank official government / WHO / UN sources ahead of general portals
    results.sort(key=lambda item: (0 if item.is_official_gov_or_un else 1, item.site_name))
    return results