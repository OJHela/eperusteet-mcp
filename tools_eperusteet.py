"""
Tools for ePerusteet MCP server.
All tools make real HTTP calls to the ePerusteet API.
"""
from __future__ import annotations

from eperusteet_client import (
    search_perusteet,
    get_peruste,
    get_lops2019_oppiaineet,
    get_lops2019_oppiaine,
    get_perusopetus_oppiaine,
    search_ylops_ops,
    extract_peruste_summary,
    extract_peruste_structure,
    extract_oppiaine_summary,
    extract_ylops_ops_summary,
    _fi,
    _ts_to_date,
    _strip_html,
)

MAX_ROWS = 20  # hard cap per CLAUDE.md Rule 1


async def hae_perusteet(
    nimi: str | None = None,
    koulutustyyppi: str | None = None,
    voimassa: bool | None = None,
) -> str:
    """
    Hae kansallisia opetussuunnitelman perusteita nimellä ja/tai koulutustyypillä.

    USE THIS TOOL WHEN:
    - Käyttäjä kysyy mitä kansallisia perusteita on olemassa
    - Käyttäjä haluaa listata perusopetuksen, lukion tai ammatillisia tutkintoja
    - Käyttäjä kysyy "Onko voimassa olevia perusteita koulutukselle X?"
    - Käyttäjä haluaa etsiä perusteita nimellä (esim. "matematiikka", "tieto- ja viestintätekniikka")
    - Käyttäjä kysyy "Mikä on perusopetuksen OPS:n ID?"

    THEN CALL:
    → Löytyykö tuloksia? → kutsu hae_peruste_tiedot löydetyllä ID:llä
    → Ei tuloksia? → kokeile laajempaa hakua ilman koulutustyyppisuodatinta
    → Lukion oppiaineet? → kutsu hae_oppiaineet lukion perusteen ID:llä

    DO NOT USE WHEN:
    - Käyttäjällä on jo peruste-ID → käytä hae_peruste_tiedot suoraan
    - Käyttäjä kysyy paikallisista OPS:ista → käytä hae_paikalliset_opetussuunnitelmat

    Parameters:
    - nimi: Hakusana suomeksi. Esimerkkejä: "perusopetus", "lukio", "tieto- ja viestintätekniikka", "autoala"
    - koulutustyyppi: Koulutustyypin koodi. Arvot:
        koulutustyyppi_16  = perusopetus
        koulutustyyppi_2   = lukiokoulutus
        koulutustyyppi_1   = ammatillinen perustutkinto
        koulutustyyppi_11  = ammatillinen ammattitutkinto
        koulutustyyppi_12  = ammatillinen erikoisammattitutkinto
        koulutustyyppi_10  = vapaa sivistystyö
        koulutustyyppi_22  = TUVA (tutkintoon valmentava)
        koulutustyyppi_0   = varhaiskasvatus
    - voimassa: True = vain voimassa olevat, False = kaikki, None = kaikki
    """
    data = await search_perusteet(
        nimi=nimi,
        koulutustyyppi=koulutustyyppi,
        voimassa=voimassa,
        sivukoko=MAX_ROWS,
    )
    items = data.get("data", [])
    total = data.get("kokonaismäärä", len(items))

    if not items:
        tips = []
        if koulutustyyppi:
            tips.append("poista koulutustyyppisuodatin")
        if nimi:
            tips.append("kokeile lyhyempää hakusanaa")
        tip_str = " tai ".join(tips) if tips else "kokeile eri hakusanoja"
        return f"Ei löydetty perusteita. Vinkki: {tip_str}."

    lines = [
        f"Löytyi {total} perustetta (näytetään {min(len(items), MAX_ROWS)}):\n"
    ]
    for item in items[:MAX_ROWS]:
        lines.append(extract_peruste_summary(item))
        lines.append("")

    if total > MAX_ROWS:
        lines.append(
            f"[Näytetään {MAX_ROWS}/{total} — tarkenna hakua saadaksesi spesifimmät tulokset]"
        )
    return "\n".join(lines)


async def hae_peruste_tiedot(peruste_id: int) -> str:
    """
    Hae yksittäisen kansallisen perusteen täydelliset tiedot numerisella ID:llä.

    USE THIS TOOL WHEN:
    - Käyttäjällä on peruste-ID (numeerinen) ja haluaa tietää mitä se sisältää
    - Käyttäjä kysyy "Mitä tavoitteita perusopetuksen OPS 2014 asettaa matematiikalle?"
    - Käyttäjä haluaa tietää lukion oppiaineet tai ammatillisen tutkinnon osat
    - Käyttäjä kysyy perusteen voimassaolosta, laajuudesta tai rakenteesta
    - Jatko hae_perusteet-haun jälkeen, kun ID on saatu

    HUOM: Lukion (lops2019) perusteille tämä palauttaa automaattisesti myös
    kaikki oppiaineet moduuleineen — erillistä hae_oppiaineet-kutsua ei tarvita.

    THEN CALL:
    → Paikallinen OPS? → kutsu hae_paikalliset_opetussuunnitelmat perusteId:llä

    DO NOT USE WHEN:
    - ID:tä ei tiedetä → käytä ensin hae_perusteet
    - Halutaan paikallinen OPS → käytä hae_paikalliset_opetussuunnitelmat

    Parameters:
    - peruste_id: Perusteen numerinen ID (esim. 419550 = perusopetus 2014, 6828810 = lukio 2019)

    Tunnettuja ID:itä:
      419550   = Perusopetuksen OPS:n perusteet 2014
      6828810  = Lukion OPS:n perusteet 2019
      1372910  = Lukion OPS:n perusteet 2015
    """
    d = await get_peruste(peruste_id)

    if "syy" in d:
        return f"Virhe: {d.get('syy', 'Tuntematon virhe')} — perusteId {peruste_id} ei löydy."

    result = extract_peruste_structure(d, max_chars=8000)

    # For lops2019, automatically include full oppiaineet — saves the model an extra tool call
    is_lops2019 = bool(d.get("lops2019")) or d.get("toteutus") == "lops2019"
    if is_lops2019:
        oppiaineet = await get_lops2019_oppiaineet(peruste_id)
        if oppiaineet:
            result += f"\n\n## Oppiaineet ({len(oppiaineet)} kpl) — moduulit ja laajuudet\n"
            for oa in oppiaineet[:MAX_ROWS]:
                result += "\n" + extract_oppiaine_summary(oa)
                result += "\n"
            if len(oppiaineet) > MAX_ROWS:
                remaining = oppiaineet[MAX_ROWS:]
                result += f"\n[Lisää oppiaineita ({len(remaining)} kpl):]"
                for oa in remaining:
                    result += f"\n  - {_fi(oa.get('nimi'))} (ID: {oa.get('id')})"

    return result


async def hae_paikalliset_opetussuunnitelmat(
    nimi: str | None = None,
    koulutustyyppi: str | None = None,
    sivukoko: int = 20,
) -> str:
    """
    Hae paikallisia opetussuunnitelmia (perusopetus, lukio) kunnittain tai kouluittain.

    USE THIS TOOL WHEN:
    - Käyttäjä kysyy "Onko Tampereen kaupungilla julkaistu paikallinen OPS?"
    - Käyttäjä haluaa listata tietyn kunnan tai koulun paikallisia OPS:ja
    - Käyttäjä kysyy "Mitä lukion paikallisia OPS:ja on julkaistu?"
    - Käyttäjä etsii kunnan tai koulun nimeä paikallisista OPS:ista

    THEN CALL:
    → Löytyi OPS? → käytä hae_paikallinen_opetussuunnitelma yksityiskohtien hakemiseen

    DO NOT USE WHEN:
    - Käyttäjä etsii kansallista perustetta → käytä hae_perusteet
    - Käyttäjä etsii ammatillisia paikallisia OPS:ja (ammatilliset eivät ole tässä palvelussa)

    Parameters:
    - nimi: Hakusana (kunnan tai koulun nimi). Esim. "Tampere", "Helsinki", "Jyväskylä"
    - koulutustyyppi: Suodata koulutustyypin mukaan (sovelletaan asiakaspuolella):
        koulutustyyppi_16 = perusopetus
        koulutustyyppi_2  = lukiokoulutus
    - sivukoko: Tulosten määrä (1–20, oletus 20)
    """
    sivukoko = min(sivukoko, MAX_ROWS)
    # Fetch more if client-side koulutustyyppi filtering is needed
    fetch_size = min(100, sivukoko * 5) if koulutustyyppi else sivukoko

    # Finnish city names inflect in the database (e.g. Helsinki→Helsingin, Turku→Turun).
    # If no results with the given nimi, retry dropping the last 2 chars as a stem fallback.
    search_nimi = nimi
    data = await search_ylops_ops(nimi=search_nimi, sivukoko=fetch_size)
    if nimi and not data.get("data") and len(nimi) > 4:
        search_nimi = nimi[:-2]
        data = await search_ylops_ops(nimi=search_nimi, sivukoko=fetch_size)

    items = data.get("data", [])
    total = data.get("kokonaism\u00e4\u00e4r\u00e4", len(items))

    # Client-side koulutustyyppi filter (server ignores this param)
    if koulutustyyppi:
        items = [i for i in items if i.get("koulutustyyppi") == koulutustyyppi]

    if not items:
        tips = []
        if nimi:
            tips.append("kokeile lyhyempää hakusanaa tai kunnan nimeä")
        if koulutustyyppi:
            tips.append("kokeile ilman koulutustyyppisuodatinta")
        tip_str = " tai ".join(tips) if tips else "kokeile eri hakusanoja"
        return f"Ei löydetty paikallisia OPS:ja. Vinkki: {tip_str}."

    shown = items[:sivukoko]
    lines = [f"Löytyi paikallisia OPS:ja (näytetään {len(shown)}):\n"]
    for item in shown:
        lines.append(extract_ylops_ops_summary(item))
        lines.append("")

    if len(items) > sivukoko:
        lines.append(
            f"[Lisää tuloksia saatavilla — tarkenna hakua kunnan nimellä]"
        )
    elif not koulutustyyppi and total > fetch_size:
        lines.append(
            f"[Näytetään {fetch_size}/{total} — tarkenna hakua nimellä]"
        )
    return "\n".join(lines)


async def hae_paikallinen_opetussuunnitelma(ops_id: int) -> str:
    """
    Hae yksittäisen paikallisen OPS:n tiedot ID:n perusteella (perusopetus, lukio).

    USE THIS TOOL WHEN:
    - Käyttäjällä on paikallisen OPS:n ID (saatu hae_paikalliset_opetussuunnitelmat-hausta)
    - Käyttäjä haluaa tietää OPS:n tiedot: kunta, koulut, koulutustyyppi, julkaisuaika
    - Käyttäjä kysyy "Mitä tietoja tästä paikallisesta OPS:sta on saatavilla?"

    HUOM: OPS:n sisältötekstit eivät ole saatavilla API:n kautta tällä hetkellä
    (yksityiskohtainen sisältö vaatisi toimivan detail-endpointin, joka on poissa käytöstä).
    Voit ohjata käyttäjän ePerusteet-palvelun web-käyttöliittymään tarkempaa sisältöä varten.

    THEN CALL:
    → Tarvitaan kansallinen peruste? → kutsu hae_peruste_tiedot peruste_id:llä

    DO NOT USE WHEN:
    - OPS:n ID:tä ei tiedetä → käytä ensin hae_paikalliset_opetussuunnitelmat
    - Kysytään kansallisesta perusteesta → käytä hae_peruste_tiedot

    Parameters:
    - ops_id: Paikallisen OPS:n numerinen ID (saatu hae_paikalliset_opetussuunnitelmat-hausta)
    """
    # Detail endpoint returns 500 — scan the list to find the item by ID.
    # Items appear to be ordered by ID desc; scan pages until found or exhausted.
    sivukoko = 100
    data = await search_ylops_ops(sivukoko=sivukoko, sivu=0)
    total = data.get("kokonaism\u00e4\u00e4r\u00e4", 0)
    total_pages = max(1, -(-total // sivukoko))  # ceiling division

    for item in data.get("data", []):
        if item.get("id") == ops_id:
            return extract_ylops_ops_summary(item)

    for page in range(1, min(total_pages, 13)):
        data = await search_ylops_ops(sivukoko=sivukoko, sivu=page)
        for item in data.get("data", []):
            if item.get("id") == ops_id:
                return extract_ylops_ops_summary(item)

    return (
        f"OPS:a ID:llä {ops_id} ei löydy. "
        "Varmista ID hae_paikalliset_opetussuunnitelmat-haulla."
    )


async def hae_oppiaineet(peruste_id: int) -> str:
    """
    Listaa lukion opetussuunnitelman oppiaineet (lops2019) peruste-ID:n perusteella.

    USE THIS TOOL WHEN:
    - Käyttäjä kysyy "Mitä oppiaineita lukiossa on OPS 2019:n mukaan?"
    - Käyttäjä haluaa listata lukion pakolliset ja valinnaiset oppiaineet
    - Käyttäjä kysyy oppiaineiden laajuuksista (opintopisteet) lukiossa
    - Käyttäjä haluaa tietää tietyn oppiaineen moduulit tai oppimäärät
    - Jatko hae_peruste_tiedot-kutsun jälkeen, kun toteutus=lops2019

    THEN CALL:
    → Tarvitaan tarkemmat tiedot oppiaineesta? → kutsu hae_peruste_tiedot
      oppiaineen ID:llä (ei saatavilla tällä hetkellä) tai lue moduulit tästä vastauksesta

    DO NOT USE WHEN:
    - Peruste ei ole lukion peruste (lops2019) → käytä hae_peruste_tiedot
    - Etsitään ammatillisia tutkinnon osia → käytä hae_peruste_tiedot

    Parameters:
    - peruste_id: Lukion perusteen numerinen ID
      Tunnetut lukion perusteet:
        6828810 = Lukion OPS:n perusteet 2019
        1372910 = Lukion OPS:n perusteet 2015

    Hakuohjeet:
    - Jos et tiedä ID:tä, hae ensin: hae_perusteet(koulutustyyppi="koulutustyyppi_2")
    """
    oppiaineet = await get_lops2019_oppiaineet(peruste_id)

    if not oppiaineet:
        return (
            f"Ei löydetty oppiaineita perusteelle {peruste_id}. "
            "Varmista, että ID on lukion peruste (lops2019). "
            "Hae perusteita: hae_perusteet(koulutustyyppi='koulutustyyppi_2')"
        )

    lines = [f"**Lukion oppiaineet** (peruste ID: {peruste_id})\n"]
    lines.append(f"Yhteensä {len(oppiaineet)} oppiainetta:\n")

    for oa in oppiaineet[:MAX_ROWS]:
        lines.append(extract_oppiaine_summary(oa))
        lines.append("")

    if len(oppiaineet) > MAX_ROWS:
        remaining = oppiaineet[MAX_ROWS:]
        lines.append(f"[Lisää oppiaineita ({len(remaining)} kpl):]")
        for oa in remaining:
            nimi = _fi(oa.get("nimi"))
            oa_id = oa.get("id")
            lines.append(f"  - {nimi} (ID: {oa_id})")

    return "\n".join(lines)


# ── Grade-level mapping ───────────────────────────────────────────────────────
_VUOSILUOKKA_GROUPS = {
    "1-2": {"vuosiluokka_1", "vuosiluokka_2"},
    "3-6": {"vuosiluokka_3", "vuosiluokka_4", "vuosiluokka_5", "vuosiluokka_6"},
    "7-9": {"vuosiluokka_7", "vuosiluokka_8", "vuosiluokka_9"},
}


async def hae_oppiaine_tiedot(
    peruste_id: int,
    oppiaine_id: int,
    vuosiluokat: str | None = None,
) -> str:
    """
    Hae yksittäisen oppiaineen täydelliset tavoitteet, sisältöalueet ja arviointi.

    USE THIS TOOL WHEN:
    - Käyttäjä kysyy "Mitä tavoitteita matematiikalle on vuosiluokille 7–9?"
    - Käyttäjä haluaa tietää oppiaineen sisältöalueet tai arviointikriteerit
    - Käyttäjä kysyy "Mitä äidinkielen opetuksen pitää sisältää?"
    - Käyttäjä haluaa lukion oppiaineen moduulien kuvaukset

    WORKFLOW:
    → Hae ensin oppiaine-ID: kutsu hae_peruste_tiedot tai hae_oppiaineet
    → Sitten kutsu tämä työkalu halutuilla parametreilla

    Parameters:
    - peruste_id: Perusteen numerinen ID (esim. 419550 = perusopetus 2014)
    - oppiaine_id: Oppiaineen numerinen ID (saatu hae_peruste_tiedot tai hae_oppiaineet -kutsuista)
    - vuosiluokat: Rajaa perusopetuksessa vuosiluokkaryhmään: "1-2", "3-6" tai "7-9"
      (ei käytetä lukiossa)
    """
    def _clean(html: str | None) -> str:
        return _strip_html(html) if html else ""

    # ── Try perusopetus endpoint first ────────────────────────────────────────
    try:
        d = await get_perusopetus_oppiaine(peruste_id, oppiaine_id)
    except Exception:
        d = {}

    vlk_list = d.get("vuosiluokkakokonaisuudet", [])

    if vlk_list:
        # Perusopetus oppiaine
        nimi = _fi(d.get("nimi"))
        lines = [f"**{nimi}** — tavoitteet ja sisältö (perusopetus, peruste {peruste_id})\n"]

        # Filter by requested grade group
        if vuosiluokat and vuosiluokat in _VUOSILUOKKA_GROUPS:
            wanted = _VUOSILUOKKA_GROUPS[vuosiluokat]
            vlk_list = [
                v for v in vlk_list
                if set(v.get("vuosiluokat", [])) & wanted
            ]

        for vlk in vlk_list:
            luokat = vlk.get("vuosiluokat", [])
            luokat_str = ", ".join(sorted(l.replace("vuosiluokka_", "") for l in luokat))
            lines.append(f"## Vuosiluokat {luokat_str}\n")

            # Tavoitteet
            tavoitteet = vlk.get("tavoitteet", [])
            if tavoitteet:
                lines.append(f"### Tavoitteet ({len(tavoitteet)} kpl)")
                for t in tavoitteet:
                    tavoite = _clean(_fi(t.get("tavoite")))
                    if tavoite:
                        lines.append(f"- {tavoite}")
                lines.append("")

            # Sisältöalueet
            sisaltoalueet = vlk.get("sisaltoalueet", [])
            if sisaltoalueet:
                lines.append(f"### Sisältöalueet ({len(sisaltoalueet)} kpl)")
                for s in sisaltoalueet:
                    s_nimi = _clean(_fi(s.get("nimi")))
                    s_kuvaus = _clean(_fi(s.get("kuvaus")))
                    if s_nimi:
                        lines.append(f"**{s_nimi}**")
                    if s_kuvaus:
                        lines.append(f"{s_kuvaus[:400]}")
                lines.append("")

            # Arviointi
            arviointi = vlk.get("arviointi", {})
            if arviointi:
                arv_teksti = _clean(_fi(arviointi.get("arvioinninKuvaus") or arviointi.get("kuvaus")))
                if arv_teksti:
                    lines.append("### Arviointi")
                    lines.append(arv_teksti[:600])
                    lines.append("")

        result = "\n".join(lines)
        if len(result) > 10000:
            result = result[:10000] + "\n\n[Sisältöä katkaistu — rajaa vuosiluokat-parametrilla]"
        return result

    # ── Try lukio lops2019 endpoint ───────────────────────────────────────────
    try:
        d = await get_lops2019_oppiaine(peruste_id, oppiaine_id)
    except Exception:
        return (
            f"Oppiainetta ID {oppiaine_id} ei löydy perusteesta {peruste_id}. "
            "Tarkista ID hae_peruste_tiedot- tai hae_oppiaineet-kutsulla."
        )

    nimi = _fi(d.get("nimi"))
    lines = [f"**{nimi}** — moduulit ja tavoitteet (lukio lops2019, peruste {peruste_id})\n"]

    tehtava = _clean(_fi(d.get("tehtava")))
    if tehtava:
        lines.append(f"### Oppiaineen tehtävä\n{tehtava[:600]}\n")

    tavoitteet = d.get("tavoitteet", {})
    if isinstance(tavoitteet, dict):
        tav_teksti = _clean(_fi(tavoitteet))
        if tav_teksti:
            lines.append(f"### Tavoitteet\n{tav_teksti[:600]}\n")

    moduulit = d.get("moduulit") or []
    oppimaarat = d.get("oppimaarat") or []

    if moduulit:
        lines.append(f"### Moduulit ({len(moduulit)} kpl)\n")
        for m in moduulit:
            m_nimi = _fi(m.get("nimi"))
            koodi = m.get("koodi", {}).get("arvo", "") if isinstance(m.get("koodi"), dict) else ""
            pak = "[pakollinen]" if m.get("pakollinen") else "[valinnainen]"
            laajuus = m.get("laajuus")
            la_str = f" {laajuus} op" if laajuus else ""
            lines.append(f"**{m_nimi}** ({koodi}){la_str} {pak}")
            kuvaus = _clean(_fi(m.get("kuvaus")))
            if kuvaus:
                lines.append(f"{kuvaus[:400]}")
            lines.append("")
    elif oppimaarat:
        # This oppiaine has sub-syllabuses (oppimäärät) — list them with IDs
        # so the caller can drill into a specific oppimäärä
        lines.append(f"### Oppimäärät ({len(oppimaarat)} kpl)\n")
        lines.append("Tämä oppiaine jakautuu oppimääriin. Hae tarkemmat tiedot kutsumalla")
        lines.append("hae_oppiaine_tiedot uudelleen alla olevalla oppimäärä-ID:llä:\n")
        for om in oppimaarat:
            om_nimi = _fi(om.get("nimi"))
            om_id = om.get("id")
            lines.append(f"  - {om_nimi} (ID: {om_id})")

    result = "\n".join(lines)
    if len(result) > 10000:
        result = result[:10000] + "\n\n[Sisältöä katkaistu]"
    return result
