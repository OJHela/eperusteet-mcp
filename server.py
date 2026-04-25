from __future__ import annotations

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from mcp.server.fastmcp import Icon
from starlette.requests import Request
from starlette.responses import PlainTextResponse

import eperusteet_client

INSTRUCTION_STRING = """
Olet yhteydessä ePerusteet-palveluun — Opetushallituksen opetussuunnitelmat ja tutkinnot.

TYÖNKULKU:
1. hae_perusteet — KÄYTÄ ENSIN kun käyttäjä kysyy kansallisista perusteista
   → Tuloksia löytyi? → kutsu hae_peruste_tiedot ID:llä
   → Lukion peruste (lops2019)? → kutsu hae_oppiaineet oppiainelistan saamiseksi
   → Ei tuloksia? → kokeile laajempaa hakua, poista suodattimet

2. hae_peruste_tiedot — KÄYTÄ kun sinulla on peruste-ID
   → Palauttaa rakenteen: oppiaineet, tutkinnonosat, vuosiluokkakokonaisuudet
   → Lukio? → kutsu hae_oppiaineet tarkemmalle oppiaineja moduulilistalle

3. hae_oppiaineet — KÄYTÄ lukion oppiaineiden listaamiseen (lops2019)
   → Palauttaa kaikki oppiaineet, moduulit ja laajuudet opintopisteinä

4. hae_oppiaine_tiedot — KÄYTÄ yksittäisen oppiaineen sisällön hakemiseen
   → Perusopetus: palauttaa tavoitteet, sisältöalueet ja arvioinnin vuosiluokittain
   → Lukio (lops2019): palauttaa moduulit kuvauksilla ja tehtävän
   → Käytä vuosiluokat-parametria rajaamiseen (esim. "7-9")

5. hae_paikalliset_opetussuunnitelmat — KÄYTÄ perusopetuksen ja lukion paikallisten OPS:ien hakuun
   → Suodata kunnan tai koulun nimellä (esim. "Tampere", "Helsinki")
   → Voit suodattaa koulutustyypillä: koulutustyyppi_16=perusopetus, koulutustyyppi_2=lukio

6. hae_paikallinen_opetussuunnitelma — KÄYTÄ kun sinulla on paikallisen OPS:n ID
   → Palauttaa OPS:n metatiedot: kunta, koulut, koulutustyyppi, julkaisuaika
   → HUOM: Sisältötekstit eivät saatavilla API:n kautta — ohjaa käyttäjä ePerusteet-sivustolle

HAKUVINKIT:
- Käytä suomenkielisiä termejä: "perusopetus", "lukio", "matematiikka", "ammatillinen"
- Koulutustyypit: koulutustyyppi_16=perusopetus, koulutustyyppi_2=lukio, koulutustyyppi_1=ammatillinen perustutkinto
- Tunnettuja ID:itä: 419550=perusopetus 2014, 6828810=lukio 2019

MITÄ TÄMÄ PALVELU EI VOI TEHDÄ:
- Paikallisten OPS:ien sisältötekstejä (API:n detail-endpoint poissa käytöstä — ohjaa ePerusteet-sivustolle)
- Ammatillisia paikallisia OPS:ja (ne ovat erillisessä AMOSAA-palvelussa)
- Reaaliaikainen tilastodata tai koulukohtainen vertailu

Datalähde: https://eperusteet.opintopolku.fi | Kieli: suomi
"""

@asynccontextmanager
async def lifespan(app):
    yield
    client = eperusteet_client._http_client
    if client and not client.is_closed:
        await client.aclose()


icon = Icon(src="https://www.oph.fi/themes/custom/ophfi/logo.svg")

mcp = FastMCP(
    name="ePerusteet MCP",
    instructions=INSTRUCTION_STRING,
    version="1.0.0",
    website_url="https://eperusteet.opintopolku.fi",
    icons=[icon],
)

from tools_eperusteet import (
    hae_perusteet,
    hae_peruste_tiedot,
    hae_paikalliset_opetussuunnitelmat,
    hae_paikallinen_opetussuunnitelma,
    hae_oppiaineet,
    hae_oppiaine_tiedot,
)

# meta={"requires_permission": False} is the Intric-specific field that disables
# the per-tool permission prompt. This is the correct field per the Intric template.
_no_perm = {"requires_permission": False}
mcp.tool(meta=_no_perm)(hae_perusteet)
mcp.tool(meta=_no_perm)(hae_peruste_tiedot)
mcp.tool(meta=_no_perm)(hae_paikalliset_opetussuunnitelmat)
mcp.tool(meta=_no_perm)(hae_paikallinen_opetussuunnitelma)
mcp.tool(meta=_no_perm)(hae_oppiaineet)
mcp.tool(meta=_no_perm)(hae_oppiaine_tiedot)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


app = mcp.http_app(lifespan=lifespan)
