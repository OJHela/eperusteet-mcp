# ePerusteet MCP

MCP server for the Finnish National Agency for Education's (OPH) curriculum and qualification framework API.

## What it does

Lets municipal education officials, school principals, and curriculum planners instantly query, compare, and verify both national curriculum frameworks and vocational local curriculum documents.

**Data source:** https://eperusteet.opintopolku.fi
**Authentication:** None required
**Language:** Finnish

## Tools

| Tool | Description |
|------|-------------|
| `hae_perusteet` | Search national curriculum frameworks by name and/or education type |
| `hae_peruste_tiedot` | Get full structured content of a national framework by ID |
| `hae_oppiaineet` | List all subjects in a lukio (lops2019) framework |
| `hae_paikalliset_opetussuunnitelmat` | List local vocational curriculum implementations |
| `hae_paikallinen_opetussuunnitelma` | Get full content of a specific local curriculum plan |

## Example questions

- "Mitä matematiikan tavoitteita perusopetuksen OPS:n perusteissa 2014 on vuosiluokille 7–9?"
- "Mitä pakollisia oppiaineita lukion OPS:n perusteet 2019 edellyttää?"
- "Onko Tampereen kaupungilla julkaistu paikallinen perusopetuksen OPS?"
- "Listaa Helsingin lukioiden paikalliset opetussuunnitelmat."

## Known education type codes

| Code | Type |
|------|------|
| `koulutustyyppi_16` | Perusopetus (basic education) |
| `koulutustyyppi_2` | Lukiokoulutus (upper secondary) |
| `koulutustyyppi_1` | Ammatillinen perustutkinto (vocational) |
| `koulutustyyppi_11` | Ammatillinen ammattitutkinto |
| `koulutustyyppi_12` | Ammatillinen erikoisammattitutkinto |
| `koulutustyyppi_10` | Vapaa sivistystyö (liberal adult education) |
| `koulutustyyppi_22` | TUVA (tutkintoon valmentava) |
| `koulutustyyppi_0` | Varhaiskasvatus (early childhood education) |

## Known IDs

| ID | Framework |
|----|-----------|
| 419550 | Perusopetuksen OPS:n perusteet 2014 |
| 6828810 | Lukion OPS:n perusteet 2019 |
| 1372910 | Lukion OPS:n perusteet 2015 |

## Local development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 test_tools.py      # must exit 0
uvicorn server:app --port 8000
curl http://localhost:8000/health  # → OK
```

## Connect to Intric

1. Deploy to Railway (see Procfile)
2. URL: `https://{your-domain}.railway.app/mcp`
3. No token needed (no-auth server)

## Notes

- **eperusteet-ylops-service** `/external/opetussuunnitelmat` list endpoint works (1,241+ documents). The per-ID detail endpoint (`/{id}`) returns 500 — tools return list-level metadata only and direct users to the web UI for full content.
- Server-side filters `koulutustyyppi`, `kunta`, `perusteId` are ignored by the ylops API — `koulutustyyppi` is applied client-side in the tool.
- Local vocational OPS (ammatilliset) are in a separate **eperusteet-amosaa-service** — not covered by this server.
- Full peruste responses can be 9MB — tools extract structured summaries.
