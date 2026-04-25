from __future__ import annotations

from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

import eperusteet_client

INSTRUCTION_STRING = """
Olet yhteydessä ePerusteet-palveluun — Opetushallituksen opetussuunnitelmat ja tutkinnot.

TYÖNKULKU:
1. hae_perusteet — KÄYTÄ ENSIN kun käyttäjä kysyy kansallisista perusteista
   → Tuloksia löytyi? → kutsu hae_peruste_tiedot ID:llä
   → Ei tuloksia? → kokeile laajempaa hakua, poista suodattimet

2. hae_peruste_tiedot — KÄYTÄ kun sinulla on peruste-ID
   → Palauttaa rakenteen: oppiaineet, tutkinnonosat, vuosiluokkakokonaisuudet
   → Lukio (lops2019): palauttaa automaattisesti kaikki oppiaineet moduuleineen
     — erillistä hae_oppiaineet-kutsua EI tarvita

3. hae_oppiaineet — KÄYTÄ vain jos tarvitset lukion oppiaineet erikseen ilman perusteen muita tietoja

4. hae_paikalliset_opetussuunnitelmat — KÄYTÄ ammatillisten paikallisten OPS:ien hakuun
   → Suodata nimellä tai perusteId:llä
   → HUOM: Vain ammatilliset OPS:t — perusopetuksen/lukion paikalliset OPS:t eivät saatavilla

5. hae_paikallinen_opetussuunnitelma — KÄYTÄ kun sinulla on paikallisen OPS:n ID
   → Palauttaa OPS:n kuvauksen ja rakenteen

HAKUVINKIT:
- Käytä suomenkielisiä termejä: "perusopetus", "lukio", "matematiikka", "ammatillinen"
- Koulutustyypit: koulutustyyppi_16=perusopetus, koulutustyyppi_2=lukio, koulutustyyppi_1=ammatillinen perustutkinto
- Tunnettuja ID:itä: 419550=perusopetus 2014, 6828810=lukio 2019

MITÄ TÄMÄ PALVELU EI VOI TEHDÄ:
- Perusopetuksen tai lukion paikallisia OPS:ja (vain kansalliset perusteet)
- Reaaliaikainen tilastodata tai koulukohtainen vertailu

Datalähde: https://eperusteet.opintopolku.fi | Kieli: suomi
"""


@asynccontextmanager
async def lifespan(app):
    yield
    # Close persistent HTTP client on shutdown
    client = eperusteet_client._http_client
    if client and not client.is_closed:
        await client.aclose()


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
)

# CRITICAL: requires_permission=False on every tool so Intric does not prompt user
# fastmcp 2.3.4 uses annotations= (not meta=); ToolAnnotations has extra="allow"
_no_perm = {"requires_permission": False}
mcp.tool(annotations=_no_perm)(hae_perusteet)
mcp.tool(annotations=_no_perm)(hae_peruste_tiedot)
mcp.tool(annotations=_no_perm)(hae_paikalliset_opetussuunnitelmat)
mcp.tool(annotations=_no_perm)(hae_paikallinen_opetussuunnitelma)
mcp.tool(annotations=_no_perm)(hae_oppiaineet)


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


# No-auth server
app = mcp.http_app(lifespan=lifespan)
