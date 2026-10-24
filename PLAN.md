# flyconn-bench — fly-connectome datasets and an ML benchmark on Hugging Face (plan and handoff)

Written 2026-10-24 at the end of a brainstorming session in the `flyconn` repo
(`/Users/moizp/google-fly`, github.com/moiz-lakkadkutta/flyconn, v0.4.0 on PyPI).
A new session starts here. Read this file, then flyconn's `CLAUDE.md`, `docs/DATA_SOURCES.md`
and `docs/caveats.md`.

## What and why

Two deliverables, in order:

1. **Official-quality harmonized snapshots on Hugging Face.** flyconn's Parquet stores (neurons
   plus weighted edges) for each public connectome, published with dataset cards that carry
   provenance, licence, citation and the NT-prediction caveats. One line loads them:
   `load_dataset("flyconn/malecns-v1.0")` or `flyconn` itself.
2. **FlyGraphBench:** a small set of ML tasks with fixed **cross-animal** splits (train on one fly,
   test on another), honest baselines, and a leaderboard Space.

Owner goals: (1) learn and build skills (dataset engineering, GNNs, benchmark design, HF Hub),
(2) lots of people using it. HF is where ML researchers already are.

Evidence from the 2026-10-24 research pass:
- On HF only unofficial re-uploads exist, with unlabelled versions, and they still get downloads:
  SLOP011/flywire-fafb-connectome 311, svgmediabills/malecns-connectome 232,
  fernandofernandes/fly-connectome-malecns-166k 220, nosuchstudios/fruit-fly-brain-runtime 625.
  ConnectomeBench2 (an LLM proofreading benchmark, a different task) has 3,366. There is also
  `Emulated-Inc/sci-connectome-cell-typing-new-brain` (68), so check what it is before designing
  the cell-typing task. HF API, read 2026-10-24.
- No fly graph-ML benchmark with fixed splits was found. The closest template is the C. elegans
  GNN benchmark (arXiv 2603.02241). FlyWire challenges (2024) were one-offs. NTAC (Nat Commun
  2025, connectivity-only cell typing) is the natural baseline to beat.
- Lesson from the human-fMRI NeuroGraph benchmark: GNNs kept their accuracy with all edges
  removed. So every task needs **feature-only** and **edge-ablated** baselines.
- flyconn already has the hard parts: harmonized schema, provenance, cross-dataset type matching,
  and a calibrated zero-shot classifier. Measured group top-1 accuracy: MaleCNS → FlyWire 0.909,
  BANC → FlyWire 0.657 (`docs/GOLDEN_RESULTS.md` 6i). That is a ready-made baseline.
- The HF org name `flyconn` returned 404 on 2026-10-24 (likely free). `flyconn-bench` was free on
  PyPI and GitHub.

## Decisions already made

- The owner picked this direction (HF dataset or benchmark) as one of the projects to plan.
- **2026-10-24: snapshots first.** Publish the HF snapshots (M0–M1) as their own launch; the
  benchmark (M2+) follows later. The open questions about a paper and the leaderboard are deferred
  to the start of M2. First uploads: MaleCNS v1.0 and BANC v888 (both clearly CC BY 4.0); FlyWire,
  hemibrain and MANC wait on their licence checks (see flyconn `docs/DATA_SOURCES.md`).

## Defaults (my calls; owner can override)

- **The snapshots come first.** They are cheap, useful on their own, and the course
  (`flyconn-course`) loads its data from them.
- **HF org `flyconn`**, one dataset repo per `dataset@version`:
  `flyconn/malecns-v1.0`, `flyconn/flywire-783`, `flyconn/banc-888`, `flyconn/manc-1.2.1`,
  `flyconn/hemibrain-1.2.1`. The flyconn store is the source of truth; the HF repo is a mirror,
  and the card records the flyconn version, checksums and git SHA.
- **Licence: re-host only what the source licence allows, with attribution in every card.** The
  flyconn registry lists CC-BY-4.0 for MaleCNS, FlyWire and BANC. Check hemibrain and MANC
  terms before uploading them, and check whether any upstream asks not to be mirrored. Code is
  Apache-2.0.
- **Small "slices" too**, for Colab and teaching: weights thresholded at `min_weight=5` and
  type-aggregated graphs, each a few MB to tens of MB.
- **Benchmark code in the standalone repo/package `flyconn-bench`**, which depends on flyconn.
  It provides PyG `Dataset` loaders, task definitions, split files, metrics and baselines.
  Leaderboard as an HF Space that reads submitted prediction files (no code execution).
- **Starting tasks** (fewer, done well):
  1. **Cross-animal cell typing:** train with FlyWire labels, predict MaleCNS / BANC types. Also
     a group-level task. Metrics: top-1, top-5, calibration (ECE).
  2. **Link / weight prediction** within a dataset, using held-out edges.
  3. **NT from connectivity.** Labels are *predictions* (Eckstein 2024), so evaluate on the
     ground-truth subset only, e.g. the `flyconnectome/drosophila_neurotransmitters` table, after
     checking its licence. Say this on the card.
- **Baselines for every task:** a feature-only MLP, an edge-ablated GNN, a standard GNN
  (GraphSAGE/GAT), flyconn `classify` (task 1), and NTAC if it can be run.
- **Leakage guard.** MaleCNS's FlyWire cross-references may themselves have used connectivity,
  which would inflate cross-animal scores. This is an open question in flyconn's PROGRESS
  (M12). Document it on the task card and offer a split that avoids it if possible.

## flyconn API to build on (verified 2026-10-24, flyconn 0.4.0)

- `flyconn.data.registry.list_datasets`, `get_dataset`; `flyconn.data.store.Store.open(ref)`.
  The store layout is `$FLYCONN_CACHE/store/<name>/<version>/` (Parquet plus
  `provenance.json`). CLI: `flyconn data pull <ref> --level weights`.
- `flyconn.graph.ConnectivityMatrix.from_store`, `aggregate` (type-level graphs).
- `flyconn.compare.build_atlas`, `classify`, `match_types`, `partner_labels`.
- `flyconn.provenance.run_environment`, `git_sha`.

## Milestones (one branch each, tests green per commit)

1. **M0:** repo, uv, CI, ADR in flyconn. One script exports a flyconn store to an HF-ready folder
   with a generated dataset card. Offline unit test on the synthetic fixture.
2. **M1 snapshots:** publish MaleCNS v1.0 and BANC v888 (plus slices) after the licence check.
   Verify `load_dataset` round-trips to identical checksums. Then FlyWire 783, MANC, hemibrain.
3. **M2 task 1 (cross-animal typing):** splits, loader, metrics, baselines; results table in the
   repo with numbers produced by code.
4. **M3 tasks 2–3:** link/weight prediction and NT on the ground-truth subset.
5. **M4 launch:** leaderboard Space, paper-style README, posts to the HF community and ML
   Twitter/Bluesky, link from awesome-fly and flyconn's README. Consider a short arXiv
   datasets-track write-up.

## Risks

- Redistribution terms differ per dataset. Getting this wrong is the main reputational risk, so
  check before every upload.
- Snapshot size: MaleCNS weights are about 1.1 GB raw (flyconn's store is smaller). HF handles
  this, but Colab users need the slices.
- Benchmarks get gamed or leak. Fixed split files, a hidden test set for the leaderboard, and
  edge-ablation baselines help.

## Open questions for the owner (ask early, one at a time)

- Snapshots only first (fast), or snapshots and benchmark together for a single launch?
- Is a short paper (datasets track) a goal? It changes how rigorous the baselines need to be.
- Should the leaderboard be HF Space self-reporting, or a hidden test set we score?
