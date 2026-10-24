# Licences and redistribution terms (upload gate)

**No dataset is uploaded unless its row says `cleared` and the owner has said yes to that
upload.** Read 2026-10-24 from the URLs below. Exact quotes and the full research notes were
collected by a research pass on the same day; the FlyWire, Zenodo and MaleCNS statements were
re-fetched and checked by hand. This is not legal advice.

| Dataset | Licence (as stated by the source) | Source URLs | Mirroring / access terms | Status |
|---|---|---|---|---|
| MaleCNS v1.0 | CC BY 4.0: "The Male CNS dataset is licensed under CC-BY." (links to the 4.0 deed) | https://male-cns.janelia.org (footer) | No mirroring restriction found. neuPrint needs a Google login (not used: our store is built from the public GCS flat files, whose SHA-256s match flyconn's registry). | **cleared** |
| BANC v888 | CC BY 4.0, no extra terms of use (Dataverse v3.0, 2026-07-01) | https://doi.org/10.7910/DVN/7WTH1N (API: `license.name = "CC BY 4.0"`); bucket `README.txt` has no licence text and asks to cite the Dataverse DOI | None found. Cite Bates et al. 2026 and the Dataverse DOI. Our store uses `compiled_data/banc_888/` from the public bucket (sjcabs: "Licensed under CC-BY by the respective dataset creators"). | **cleared** |
| FlyWire / FAFB v783 | **Conflict.** Zenodo deposit: CC BY 4.0. FlyWire itself: "FlyWire's public release data is made available under license CC BY-NC 4.0"; Principles: "Published versions of FlyWire's data are available under CC BY-NC 4.0 license." | https://zenodo.org/records/10676866 · https://flywire.ai/guidelines · https://edit.flywire.ai/principles.html · https://flywire.ai/tos | No explicit no-mirroring clause. Codex downloads need a Google sign-in, which means accepting the FlyWire ToS; the Codex FAQ asks people to use the static downloads rather than scraping. `flyconnectome/flywire_annotations` (source of some annotations) has no LICENSE file. | **blocked**: ask flywire@princeton.edu which licence governs a harmonized mirror; or publish as CC BY-NC 4.0 |
| hemibrain v1.2.1 | CC BY 4.0: "Hemibrain is licensed under CC-BY." (links to 4.0). Paper: data "available without restriction, with only the requirement to cite the source." | https://www.janelia.org/project-team/flyem/hemibrain · https://doi.org/10.7554/eLife.57443 | neuPrint needs a Google login. The figshare record the paper cites (v1.0 data, https://doi.org/10.25378/janelia.11676099.v2) is labelled **CC BY-NC 4.0**; HHMI's generic site terms (https://www.hhmi.org/terms-of-use) defer to page-specific terms. | **review**: confirm the NC label on figshare does not cover v1.2 |
| MANC v1.2.1 | CC BY 4.0: "The MANC is licensed under CC-BY." (links to 4.0) | https://www.janelia.org/project-team/flyem/manc-connectome | neuPrint needs a Google login. Our store is built from the sjcabs compiled files (data "CC-BY by the respective dataset creators"; code MIT). MANC v1.2.3 now exists on neuPrint. | **review**: likely fine; confirm the sjcabs-derived build is acceptable and decide 1.2.1 vs 1.2.3 |

## UNVERIFIED

1. MaleCNS: the release page (https://male-cns.janelia.org/release/) and the Cell paper's
   data-availability text were not read.
2. FlyWire: which licence governs (Zenodo CC BY 4.0 vs flywire.ai CC BY-NC 4.0); Codex's
   per-dataset citation requirements (behind sign-in).
3. BANC: whether FlyWire's NC statement or ToS apply to BANC data downloaded through Codex (we do
   not use Codex for BANC); banc.community terms not checked.
4. hemibrain: scope of the CC BY-NC 4.0 label on the v1.0 figshare record.
5. MANC: Marin et al. 2024 licence text not extracted; no v1.2.1 flat export exists.
6. neuPrint: site-level terms not readable (the page needs JavaScript).

## Consequences

- flyconn's registry lists `CC-BY-4.0` for FlyWire, so a generated FlyWire card would currently
  state CC BY 4.0. Do not publish a FlyWire export until this row is resolved (noted in
  `upstream-notes.md`).
- First uploads, when approved: MaleCNS v1.0 and BANC v888.
