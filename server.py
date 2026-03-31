from __future__ import annotations

from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import PlainTextResponse

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

5. hae_paikallinen_opetussuunnitelma — KÄYTÄ kun sinulla on paikallisen OPS:n ID
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

mcp = FastMCP(
    name="ePerusteet MCP",
    instructions=INSTRUCTION_STRING,
    version="1.0.0",
    website_url="https://eperusteet.opintopolku.fi",
)

from tools_eperusteet import (
    hae_perusteet,
    hae_peruste_tiedot,
    hae_paikalliset_opetussuunnitelmat,
    hae_paikallinen_opetussuunnitelma,
    hae_oppiaineet,
    hae_oppiaine_tiedot,
)

# readOnlyHint=True is the standard MCP annotation that tells clients (incl. Intric)
# that these tools only read data and do not need user permission prompts.
_read_only = ToolAnnotations(readOnlyHint=True)
mcp.tool(annotations=_read_only)(hae_perusteet)
mcp.tool(annotations=_read_only)(hae_peruste_tiedot)
mcp.tool(annotations=_read_only)(hae_paikalliset_opetussuunnitelmat)
mcp.tool(annotations=_read_only)(hae_paikallinen_opetussuunnitelma)
mcp.tool(annotations=_read_only)(hae_oppiaineet)
mcp.tool(annotations=_read_only)(hae_oppiaine_tiedot)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


# No-auth server
# Starlette Mount("/mcp") expects /mcp/ (trailing slash).
# Some MCP clients (e.g. Intric) POST to /mcp and don't re-POST after a 307 redirect.
# This ASGI middleware silently rewrites /mcp → /mcp/ before routing so no redirect happens.
class _RewriteMcpPath:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http" and scope.get("path") == "/mcp":
            scope = {**scope, "path": "/mcp/", "raw_path": b"/mcp/"}
        await self.app(scope, receive, send)


app = _RewriteMcpPath(mcp.http_app())
