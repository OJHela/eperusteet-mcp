from __future__ import annotations

from fastmcp import FastMCP
from mcp.server.fastmcp import Icon
from starlette.requests import Request
from starlette.responses import PlainTextResponse

INSTRUCTION_STRING = """
Olet yhteydessä ePerusteet-palveluun — Opetushallituksen opetussuunnitelmat ja tutkinnot.

TYÖNKULKU:
1. hae_perusteet — KÄYTÄ ENSIN kun käyttäjä kysyy kansallisista perusteista
   → Tuloksia löytyi? → kutsu hae_peruste_tiedot ID:llä
   → Ei tuloksia? → kokeile laajempaa hakua, poista suodattimet

2. hae_peruste_tiedot — KÄYTÄ kun sinulla on peruste-ID
   → Palauttaa rakenteen: oppiaineet, tutkinnonosat, vuosiluokkakokonaisuudet
   → Lukio (lops2019): sisältää AUTOMAATTISESTI kaikki oppiaineet moduuleineen — EI erillisiä lisäkutsuja

3. hae_oppiaine_tiedot — KÄYTÄ yksittäisen oppiaineen SISÄLLÖN hakemiseen (tavoitteet, arviointi)
   → Perusopetus: tavoitteet, sisältöalueet ja arviointi vuosiluokittain
   → Lukio (lops2019): moduulit kuvauksilla ja tehtävä
   → vuosiluokat-parametri rajaamiseen: "1-2", "3-6" tai "7-9"
   → Workflow: hae oppiaine-ID ensin hae_peruste_tiedot-kutsulla

4. hae_paikalliset_opetussuunnitelmat — KÄYTÄ perusopetuksen ja lukion paikallisten OPS:ien hakuun
   → Suodata kunnan tai koulun nimellä (esim. "Tampere", "Helsinki")
   → Voit suodattaa koulutustyypillä: koulutustyyppi_16=perusopetus, koulutustyyppi_2=lukio

5. hae_paikallinen_opetussuunnitelma — KÄYTÄ kun sinulla on paikallisen OPS:n ID
   → Palauttaa metatiedot + suoran linkin OPS:n sisältöön ePerusteet-sivustolla
   → HUOM: API ei palauta sisältötekstejä — linkki ohjaa käyttäjän oikeaan paikkaan

6. hae_oppiaineet — KÄYTÄ vain kun tarvitaan PELKKÄ lukion oppiainelista ilman perusteen muita tietoja
   → Normaalisti hae_peruste_tiedot riittää — tämä on erikoistapauksia varten

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


app = mcp.http_app()
