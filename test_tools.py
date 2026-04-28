"""
Live verification — calls real ePerusteet API. Must exit 0 before server is done.
Run: python3 test_tools.py
"""
from __future__ import annotations

import asyncio
import sys
import traceback
import time

from tools_eperusteet import (
    hae_perusteet,
    hae_peruste_tiedot,
    hae_paikalliset_opetussuunnitelmat,
    hae_paikallinen_opetussuunnitelma,
    hae_oppiaineet,
    hae_oppiaine_tiedot,
)

results = []


def test(name: str, coro, *args, expected_min_chars: int = 50, **kwargs):
    print(f"\n{'='*55}")
    print(f"TEST: {name}")
    t0 = time.time()
    try:
        result = asyncio.run(coro(*args, **kwargs))
        elapsed = time.time() - t0
        output = str(result) if not isinstance(result, str) else result
        size_kb = len(output.encode()) / 1024
        print(f"  Time: {elapsed:.1f}s | Size: {size_kb:.1f}KB")
        print(f"  Preview: {output[:300]}")
        if elapsed > 20:
            raise TimeoutError(f"Tool took {elapsed:.1f}s (limit: 20s)")
        if size_kb > 20:
            print(f"  ⚠️  WARNING: Response is {size_kb:.1f}KB — check row cap")
        if len(output) < expected_min_chars:
            raise ValueError(f"Response too short: {len(output)} chars")
        results.append((name, True, None))
        print("  ✅ PASS")
    except Exception as e:
        elapsed = time.time() - t0
        traceback.print_exc()
        results.append((name, False, str(e)))
        print(f"  ❌ FAIL ({elapsed:.1f}s): {e}")


# ── Tests ────────────────────────────────────────────────────────────────────

# 1. Search by education type (perusopetus)
test(
    "hae_perusteet — koulutustyyppi_16 (perusopetus)",
    hae_perusteet,
    koulutustyyppi="koulutustyyppi_16",
    expected_min_chars=100,
)

# 2. Search by name (lukio)
test(
    "hae_perusteet — nimi='lukio'",
    hae_perusteet,
    nimi="lukio",
    expected_min_chars=100,
)

# 3. Search vocational
test(
    "hae_perusteet — koulutustyyppi_1 (ammatillinen perustutkinto)",
    hae_perusteet,
    koulutustyyppi="koulutustyyppi_1",
    expected_min_chars=100,
)

# 4. Get perusopetus 2014 full details
test(
    "hae_peruste_tiedot — 419550 (perusopetus 2014)",
    hae_peruste_tiedot,
    419550,
    expected_min_chars=200,
)

# 5. Get lukio 2019 full details
test(
    "hae_peruste_tiedot — 6828810 (lukio 2019)",
    hae_peruste_tiedot,
    6828810,
    expected_min_chars=200,
)

# 6. Hae lukio 2019 subjects
test(
    "hae_oppiaineet — 6828810 (lukio 2019)",
    hae_oppiaineet,
    6828810,
    expected_min_chars=200,
)

# 7. List local OPS (perusopetus + lukio) — no filter
test(
    "hae_paikalliset_opetussuunnitelmat — no filter",
    hae_paikalliset_opetussuunnitelmat,
    expected_min_chars=100,
)

# 8. List local OPS by municipality name
test(
    "hae_paikalliset_opetussuunnitelmat — nimi='Tampere'",
    hae_paikalliset_opetussuunnitelmat,
    nimi="Tampere",
    expected_min_chars=100,
)

# 8b. List local OPS filtered by koulutustyyppi (client-side)
test(
    "hae_paikalliset_opetussuunnitelmat — koulutustyyppi_16 (perusopetus)",
    hae_paikalliset_opetussuunnitelmat,
    koulutustyyppi="koulutustyyppi_16",
    expected_min_chars=100,
)

# 9. Get specific local OPS by ID (24106564 = Turun lukiokoulutuksen paikallinen LOPS2021)
test(
    "hae_paikallinen_opetussuunnitelma — 24106564",
    hae_paikallinen_opetussuunnitelma,
    24106564,
    expected_min_chars=50,
)

# 10. Search currently valid only
test(
    "hae_perusteet — voimassa=True",
    hae_perusteet,
    voimassa=True,
    expected_min_chars=50,
)

# 11. Perusopetus oppiaine — matematiikka vuosiluokat 7-9
test(
    "hae_oppiaine_tiedot — matematiikka (466344) vuosiluokat 7-9",
    hae_oppiaine_tiedot,
    419550,
    466344,
    vuosiluokat="7-9",
    expected_min_chars=300,
)

# 12. Lukio oppiaine — biologia (lops2019, has moduulit directly)
test(
    "hae_oppiaine_tiedot — biologia lukio (6832790)",
    hae_oppiaine_tiedot,
    6828810,
    6832790,
    expected_min_chars=300,
)

# 13. Lukio oppiaine with oppimaarat — äidinkieli (6828950) lists sub-syllabuses
test(
    "hae_oppiaine_tiedot — äidinkieli lukio (6828950, oppimaarat)",
    hae_oppiaine_tiedot,
    6828810,
    6828950,
    expected_min_chars=100,
)

# ── Summary ──────────────────────────────────────────────────────────────────

print(f"\n{'='*55}")
print("VERIFICATION SUMMARY")
for name, ok, err in results:
    mark = "✅" if ok else "❌"
    print(f"  {mark} {name}" + (f" — {err}" if err else ""))

passed = sum(1 for _, ok, _ in results if ok)
print(f"\n{passed}/{len(results)} passed")

if passed < len(results):
    print("\n❌ NOT DONE — fix failing tools and re-run")
    sys.exit(1)
else:
    print("\n🎉 ALL PASSED — server ready for Intric")
    sys.exit(0)
