"""
HTTP client for ePerusteet API.

Three backend services:
  eperusteet-service       → national frameworks (perusteet)
  eperusteet-ylops-service → local OPS for perusopetus + lukio (list works; detail endpoint returns 500)
  eperusteet-amosaa-service → vocational local OPS (paikalliset ammatilliset OPS)
"""
from __future__ import annotations

import asyncio
import html as _html
import re
import time
from typing import Any

import httpx

BASE_PERUSTEET = "https://eperusteet.opintopolku.fi/eperusteet-service/api/external"
BASE_YLOPS = "https://eperusteet.opintopolku.fi/eperusteet-ylops-service/api/external"
BASE_AMOSAA = "https://eperusteet.opintopolku.fi/eperusteet-amosaa-service/api/julkinen"
HEADERS = {"User-Agent": "intric-mcp/1.0 (ePerusteet MCP server)"}
TIMEOUT = 30.0
_RATE_LIMIT_DELAY = 0.5  # 2 req/s max
_CACHE_TTL = 3600.0  # 1 hour — peruste data rarely changes

_http_client: httpx.AsyncClient | None = None
_rate_lock = asyncio.Lock()
_last_request_time: float = 0.0
_cache: dict[str, tuple[float, Any]] = {}


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS)
    return _http_client


def _cache_key(url: str, params: dict | None) -> str:
    if params:
        pstr = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return f"{url}?{pstr}"
    return url


async def _rate_limited_get(url: str, params: dict | None = None) -> dict | list:
    global _last_request_time
    key = _cache_key(url, params)

    # Fast path: check cache without lock
    now = time.time()
    cached = _cache.get(key)
    if cached and now - cached[0] < _CACHE_TTL:
        return cached[1]

    async with _rate_lock:
        # Re-check under lock (another coroutine may have populated it)
        now = time.time()
        cached = _cache.get(key)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]

        elapsed = now - _last_request_time
        if elapsed < _RATE_LIMIT_DELAY:
            await asyncio.sleep(_RATE_LIMIT_DELAY - elapsed)
        _last_request_time = time.time()

    r = await _get_client().get(url, params=params)
    r.raise_for_status()
    data = r.json()
    _cache[key] = (time.time(), data)
    return data


def _fi(obj: dict | None) -> str:
    """Extract Finnish text from a multilingual object."""
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj
    return obj.get("fi") or obj.get("sv") or obj.get("en") or ""


def _ts_to_date(ms: int | None) -> str | None:
    """Convert Unix millisecond timestamp to YYYY-MM-DD."""
    if not ms:
        return None
    from datetime import datetime, timezone
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def _strip_html(text: str) -> str:
    """Strip HTML tags, decode HTML entities, and collapse whitespace."""
    return " ".join(_html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


# ── National frameworks (perusteet) ──────────────────────────────────────────

async def search_perusteet(
    nimi: str | None = None,
    koulutustyyppi: str | None = None,
    voimassa: bool | None = None,
    sivukoko: int = 20,
    sivu: int = 0,
) -> dict:
    params: dict = {"sivukoko": sivukoko, "sivu": sivu}
    if nimi:
        params["nimi"] = nimi
    if koulutustyyppi:
        params["koulutustyyppi"] = koulutustyyppi
    if voimassa is not None:
        params["voimassa"] = "true" if voimassa else "false"
    return await _rate_limited_get(f"{BASE_PERUSTEET}/perusteet", params)


async def get_peruste(peruste_id: int) -> dict:
    return await _rate_limited_get(f"{BASE_PERUSTEET}/peruste/{peruste_id}")


async def get_lops2019_oppiaineet(peruste_id: int) -> list:
    result = await _rate_limited_get(
        f"{BASE_PERUSTEET}/peruste/{peruste_id}/lops2019/oppiaineet"
    )
    if isinstance(result, list):
        return result
    return []


async def get_lops2019_oppiaine(peruste_id: int, oppiaine_id: int) -> dict:
    return await _rate_limited_get(
        f"{BASE_PERUSTEET}/peruste/{peruste_id}/lops2019/oppiaineet/{oppiaine_id}"
    )


async def get_perusopetus_oppiaine(peruste_id: int, oppiaine_id: int) -> dict:
    return await _rate_limited_get(
        f"{BASE_PERUSTEET}/peruste/{peruste_id}/perusopetus/oppiaineet/{oppiaine_id}"
    )


# ── Local OPS for perusopetus + lukio (ylops) ────────────────────────────────
# Note: /external/opetussuunnitelmat list works; /{id} detail endpoint returns 500.
# Server-side filters koulutustyyppi/kunta/perusteId are accepted but ignored —
# filtering must be done client-side.

async def search_ylops_ops(
    nimi: str | None = None,
    sivukoko: int = 20,
    sivu: int = 0,
) -> dict:
    params: dict = {"sivukoko": sivukoko, "sivu": sivu}
    if nimi:
        params["nimi"] = nimi
    return await _rate_limited_get(f"{BASE_YLOPS}/opetussuunnitelmat", params)


def _ylops_kunta(organisaatiot: list) -> str:
    """Extract municipality name from an organisaatiot list."""
    for org in organisaatiot:
        if isinstance(org, dict) and "Kunta" in org.get("tyypit", []):
            return _fi(org.get("nimi")) or "–"
    return "–"


def _ylops_koulut(organisaatiot: list) -> list[str]:
    """Extract school names from an organisaatiot list."""
    return [
        _fi(org.get("nimi"))
        for org in organisaatiot
        if isinstance(org, dict) and "Oppilaitos" in org.get("tyypit", [])
    ]


def extract_ylops_ops_summary(item: dict) -> str:
    lines = []
    nimi = _fi(item.get("nimi", {}))
    ops_id = item.get("id")
    lines.append(f"**{nimi}**")
    lines.append(f"  ID: {ops_id}")
    lines.append(f"  Koulutustyyppi: {item.get('koulutustyyppi', '–')}")
    orgs = item.get("organisaatiot") or []
    kunta = _ylops_kunta(orgs)
    if kunta != "–":
        lines.append(f"  Kunta: {kunta}")
    koulut = _ylops_koulut(orgs)
    if koulut:
        koulut_str = ", ".join(koulut[:3])
        if len(koulut) > 3:
            koulut_str += f" (+{len(koulut) - 3} muuta)"
        lines.append(f"  Koulut: {koulut_str}")
    julkaistu = _ts_to_date(item.get("julkaisuaika"))
    if julkaistu:
        lines.append(f"  Julkaistu: {julkaistu}")
    if ops_id:
        lines.append(f"  Sisältö verkossa: https://eperusteet.opintopolku.fi/eperusteet-app/#/fi/ops/{ops_id}/tiedot")
    return "\n".join(lines)


# ── Vocational local OPS (AMOSAA) ─────────────────────────────────────────────

async def search_amosaa_ops(
    nimi: str | None = None,
    peruste_id: int | None = None,
    sivukoko: int = 20,
    sivu: int = 0,
) -> dict:
    params: dict = {"sivukoko": sivukoko, "sivu": sivu}
    if nimi:
        params["nimi"] = nimi
    if peruste_id:
        params["perusteId"] = peruste_id
    return await _rate_limited_get(f"{BASE_AMOSAA}/opetussuunnitelmat", params)


# ── Data extraction helpers ───────────────────────────────────────────────────

def extract_peruste_summary(d: dict) -> str:
    """Return a concise text summary of a peruste dict."""
    lines = []
    lines.append(f"**{_fi(d.get('nimi'))}**")
    lines.append(f"  ID: {d.get('id')}")
    lines.append(f"  Koulutustyyppi: {d.get('koulutustyyppi', '–')}")
    lines.append(f"  Diaarinumero: {d.get('diaarinumero', '–')}")
    alku = _ts_to_date(d.get("voimassaoloAlkaa"))
    loppu = _ts_to_date(d.get("voimassaoloLoppuu"))
    if alku:
        lines.append(f"  Voimassa: {alku} – {loppu or 'toistaiseksi'}")
    toteutus = d.get("toteutus")
    if toteutus:
        lines.append(f"  Toteutus: {toteutus}")
    return "\n".join(lines)


def extract_peruste_structure(d: dict, max_chars: int = 8000) -> str:
    """
    Extract structural information from a full peruste response without
    returning raw multi-megabyte JSON.
    """
    lines = []
    lines.append(f"**{_fi(d.get('nimi'))}**")
    lines.append(f"ID: {d.get('id')}")
    lines.append(f"Koulutustyyppi: {d.get('koulutustyyppi', '–')}")
    lines.append(f"Diaarinumero: {d.get('diaarinumero', '–')}")
    alku = _ts_to_date(d.get("voimassaoloAlkaa"))
    loppu = _ts_to_date(d.get("voimassaoloLoppuu"))
    if alku:
        lines.append(f"Voimassa: {alku} – {loppu or 'toistaiseksi'}")
    toteutus = d.get("toteutus", "")
    if toteutus:
        lines.append(f"Toteutus: {toteutus}")
    kuvaus = _fi(d.get("kuvaus"))
    if kuvaus and len(kuvaus) > 10:
        lines.append(f"\nKuvaus:\n{kuvaus[:500]}")

    # Perusopetus structure
    po = d.get("perusopetus")
    if po and isinstance(po, dict):
        lines.append("\n## Oppiaineet (perusopetus)")
        oppiaineet = po.get("oppiaineet", [])
        if isinstance(oppiaineet, list):
            for oa in oppiaineet[:30]:
                oa_nimi = _fi(oa.get("nimi"))
                oa_id = oa.get("id")
                lines.append(f"  - {oa_nimi} (ID: {oa_id})")
        vuosiluokat = po.get("vuosiluokkakokonaisuudet", [])
        if isinstance(vuosiluokat, list) and vuosiluokat:
            lines.append("\n## Vuosiluokkakokonaisuudet")
            for vl in vuosiluokat[:5]:
                nimi = _fi(vl.get("nimi"))
                tunniste = vl.get("tunniste", "")
                lines.append(f"  - {nimi} ({tunniste})")

    # Lukio lops2019: brief note — full oppiaineet are fetched separately by the tool
    lops = d.get("lops2019")
    if lops and isinstance(lops, dict):
        oppiaineet = lops.get("oppiaineet", [])
        if oppiaineet:
            lines.append(f"\n## Lukio (lops2019): {len(oppiaineet)} oppiainetta")
            lines.append("Täydet tiedot moduuleineen listattu alla.")

    # Vocational tutkinnonosat
    tutkinnonosat = d.get("tutkinnonOsat")
    if tutkinnonosat and isinstance(tutkinnonosat, list):
        lines.append("\n## Tutkinnon osat")
        for tosa in tutkinnonosat[:30]:
            nimi = _fi(tosa.get("nimi"))
            laajuus = tosa.get("laajuus")
            la_str = f" ({laajuus} osp)" if laajuus else ""
            lines.append(f"  - {nimi}{la_str}")

    # Suoritustavat for vocational
    suoritustavat = d.get("suoritustavat")
    if suoritustavat and isinstance(suoritustavat, list):
        lines.append("\n## Suoritustavat")
        for st in suoritustavat:
            koodi = st.get("suoritustapakoodi", "")
            lines.append(f"  - {koodi}")
            tutkinnonosat_st = st.get("tutkinnonOsat", [])
            if isinstance(tutkinnonosat_st, list):
                for tosa in tutkinnonosat_st[:20]:
                    nimi = _fi(tosa.get("nimi"))
                    laajuus = tosa.get("laajuus")
                    la_str = f" ({laajuus} osp)" if laajuus else ""
                    pak = " [pakollinen]" if tosa.get("pakollinen") else ""
                    lines.append(f"    • {nimi}{la_str}{pak}")

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "\n\n[Sisältöä katkaistu]"
    return result


def extract_oppiaine_summary(oa: dict) -> str:
    """Extract a readable summary from a lops2019 oppiaine dict."""
    lines = []
    nimi = _fi(oa.get("nimi"))
    oa_id = oa.get("id")
    koodi = oa.get("koodi", {})
    koodi_arvo = koodi.get("arvo", "") if isinstance(koodi, dict) else ""
    lines.append(f"**{nimi}** (ID: {oa_id}, koodi: {koodi_arvo})")

    lao = oa.get("laajaalaisetosaamiset", {})
    if isinstance(lao, dict):
        kuvaus_fi = _fi(lao.get("kuvaus"))
        if kuvaus_fi and len(kuvaus_fi) > 10:
            clean = _strip_html(kuvaus_fi)[:600]
            lines.append(f"\nLaaja-alainen osaaminen:\n{clean}")

    oppimaarat = oa.get("oppimaarat", [])
    if isinstance(oppimaarat, list) and oppimaarat:
        lines.append("\nOppimäärät:")
        for om in oppimaarat[:10]:
            lines.append(f"  - {_fi(om.get('nimi'))} (ID: {om.get('id')})")

    moduulit = oa.get("moduulit")
    if moduulit and isinstance(moduulit, list):
        lines.append(f"\nModuulit ({len(moduulit)} kpl):")
        for m in moduulit[:15]:
            koodi_m = m.get("koodi", {})
            koodi_str = koodi_m.get("arvo", "") if isinstance(koodi_m, dict) else ""
            pakollinen = " [pakollinen]" if m.get("pakollinen") else " [valinnainen]"
            laajuus = m.get("laajuus")
            la_str = f" {laajuus} op" if laajuus else ""
            lines.append(
                f"  - {_fi(m.get('nimi'))} ({koodi_str}){la_str}{pakollinen}"
            )

    return "\n".join(lines)
