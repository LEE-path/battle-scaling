[简体中文](README.md) | [English](README.en.md)

# battle-scaling

**An Agent Skill for evidence-based power scaling and versus analysis · 1.7.4**

Turn “How strong is this character, what supports that rating, and how could they win this matchup?” into traceable evidence and conclusions. The host Agent searches, reads, interprets images, and makes semantic judgments. Python tools handle source locations, calculations, constraint checks, and records. No models from other projects need to be downloaded.

## What it does

- **Character ratings:** Fix the work, continuity, edition, period, state, and equipment; assess attack output, bodily durability, intelligence, battle IQ, experience, special abilities, destructive capacity, speed, and size separately.
- **Evidence and counterevidence:** Consult the original work, official material, and community leads; record chapters, pages, timestamps, exact quotations, or image locations. Investigate failures, limits, state changes, and conflicting feats as well.
- **Individual feat reviews:** Distinguish demonstrated results, reasonable estimates, and established full-power or upper-limit claims. Check causality, materials, fatigue, injuries, intent, equipment, and outside assistance.
- **Physics and scaling chains:** Preserve formulas, parameter sources, units, assumptions, and intermediate results. Check multipliers, circular arguments, and whether an attribute transfers between characters or states.
- **Higher-order structures and special abilities:** Evaluate infinity, mathematical structures, narrative levels, and related claims under a named ruleset. Review each ability's demonstrated limits, activation, valid targets, resistance, and counters separately.
- **Duels and team matchups:** Analyze feasible win paths, counters, and reversal conditions. Provide a complete hypothetical battle with evidence and state changes when requested.
- **Novel dossiers:** Create snapshots and ending-first reading tasks from TXT, MD, EPUB, or DOCX. Preserve exact quotations, feats and anti-feats, state timelines, encounters, gaps across the nine attributes, and a candidate CASE.

An index, matching hash, or passing test does not establish that the software understands the original work or that a character rating is correct. The host Agent must still review cross-universe interactions, model applicability, and the final verdict.

## Default ratings and three evidence modes

The default is **normal**. The response begins with one concrete normal-mode tier for the specified character and version, followed by a **nine-attribute normal-mode card**. Each attribute includes a judgment, source location, and scaling rationale. Highest and lowball interpretations follow in the analysis. An explicit request for another mode or a side-by-side comparison takes precedence.

| Mode | Evidence policy |
|---|---|
| `normal` | Feats take precedence over conflicting statements. Within the same version and state, use the strongest result supported by the prevailing body of credible feats, favoring repeated support. Sparse evidence yields a provisional rating. |
| `highest` | Consider extreme or isolated feats, strongest/equality statements, and strong readings of descriptive language. Make every extension and assumption explicit. |
| `lowball` | Actively investigate weakened states, injuries, breached defenses, unusually low output, and losses to lower-ranked opponents. Preserve the conditions and derive the lowest defensible branch. |

Each mode has its own evidence selection and reasoning. Mutually exclusive peak configurations cannot be combined. An overall tier does not automatically determine durability or speed; intelligence, battle IQ, and experience use descriptions supported by feats rather than invented energy-based tiers.

## Research and evidence quality

Prefer the original-language work and official material. Distinguish events, narration, character dialogue, verified author commentary, community interpretations, and research assumptions. Search snippets are discovery leads. Unsupported secondhand descriptions of feats cannot support a rating in any mode until original evidence is found.

When online research is allowed, community research starts with character indexes and relevant posts in **汪峰在吧** (Wangba). If coverage is insufficient, consult **抖音论战吧** as a supplementary source while continuing to verify the original work.

| Material | Default confidence and use |
|---|---|
| Ratings or scaling from verified assessment groups in either forum, with attribution checked | **Medium:** External rating references, candidate arguments, and research leads. Specific feats still require original evidence. |
| Ordinary tier discussions, personal speculation, or unverified claims of assessment-group status | **Low:** Leads only; tier labels or repeated claims do not establish a rating. |
| Original-work images actually read and checked against the work, version, state, and surrounding context | **High:** Evidence for the event or statement shown. This does not validate the entire post, its calculations, or its tier assignment. |
| Text-only retellings without original evidence | **Unverified, lead only:** Not admitted as rating anchors or scaling links. |

Verified novel text, official text, and checked transcriptions can be primary evidence without screenshots. Evidence confidence is not a win probability. Successfully fetching a page does not mean its content has been read or verified.

The optional [Tieba reader](skills/battle-scaling/references/tieba-reading.md) supports anonymous search, paginated posts, nested replies, image URLs, snapshots, hashes, and resumable collection through a separate `aiotieba` environment. An image URL is not an image inspection; collecting every currently visible page does not recover deleted or hidden content.

## Physics, higher tiers, and two ceilings for special abilities

The default named tier rules come from the Wangba reference handbook dated **2026.7.30** on its title page, with a versioned configuration and source fingerprints. Finite-tier assessments check energy, scale, release mechanism, and conditions for repeated attacks. Force, energy, power, and affected area remain distinct, as do bodily durability, shields, and resistances. Higher-tier analysis separates cosmological structure, access, actual influence, and combat attributes under the selected profile, including 新标, 道标, or 力标 where applicable. Reaching or observing a higher structure does not by itself establish the ability to destroy it.

This Skill applies **two ceilings to special abilities in all three modes**:

1. The default limit is the ability's own demonstrated, evidence-supported scope of influence.
2. Its maximum cannot exceed the tier **already attained** by the strongest character in its original setting.

The height of a cosmology cannot replace evidence of a character's attainment, and the strongest character's tier does not automatically raise every ability to that tier. The wielder's bodily attack output does not directly cap their special abilities either. Target eligibility, cross-universe compatibility, activation, resistance, and counters still require separate checks. Assumptions cannot bypass a known ceiling or established failure. See the [two-ceiling protocol](skills/battle-scaling/references/hax-ceiling.md).

## How matchups are presented

The default is `overview`: likely outcome, decisive win paths, conditions, and a defensible coarse win-rate estimate or range. If a number cannot reasonably be justified, explain the advantage and unresolved conditions instead.

An explicit request for a detailed battle uses `process`. The default response order is:

1. Both sides' configurations, starting conditions, and essential assumptions.
2. **One complete battle won by the overall favored side:** action → activation/hit → defense/counter → injury and state change → next action, until the victory conditions are met.
3. **Overall win rate or degree of advantage and its reasons**, separate from the illustrated battle.
4. **The other side's chances and reversal conditions**, followed by sources and key assumptions.

The Agent assesses the matchup before choosing a plausible winning sequence; the opponent must respond competently. If neither side can reasonably be favored, a sequence can only be a clearly labeled conditional example. The process tool resolves actions and mechanism judgments supplied by the host. It does not predict moves or simulate real-world combat physics. A selected battle or a count of authored branches cannot establish win probability or become a new canonical feat. See the [combat-process protocol](skills/battle-scaling/references/combat-process.md).

## Install and use

Clone or download this repository and install the **entire** `skills/battle-scaling` folder into your Agent's skill directory. A typical Codex location is `~/.codex/skills/battle-scaling`; other Agents supporting `SKILL.md` use their own installation conventions. Compare or back up an existing installation first and preserve local runtime data.

Tools that install skills from GitHub paths can use:

```text
https://github.com/LEE-path/battle-scaling/tree/main/skills/battle-scaling
```

Requires **Python 3.11+**. Core tools and the novel pipeline use the standard library. The host supplies working search and visual capabilities. Video tasks use ffmpeg/ffprobe as needed; image, OCR, PDF, or scientific tasks may use Pillow, PyMuPDF, or other optional tools. The external projects studied by this repository are not mandatory model installations.

Ask the host Agent to perform a task, such as “Rate this version of the character across the nine normal-mode attributes, with sources and counterevidence” or “Compare their ending states, show a detailed battle, then explain the overall odds and reversal conditions.” The Agent follows [SKILL.md](skills/battle-scaling/SKILL.md), gathers evidence, prepares a CASE, runs reviews, and delivers a report. The CLI is not a standalone conversational model.

Analysis outputs include `report.md`, the complete `analysis.json`, a CASE copy, sources, derivations, special-ability checks, and a run ledger, so conclusions can be traced to evidence and calculations.

## Quick checks

Run from the repository root:

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py doctor
python -X utf8 tools/verify_package.py
python -X utf8 skills/battle-scaling/scripts/battle.py physics --input skills/battle-scaling/assets/cases/physics-earth-binding.json
```

Use new output directories to run the synthetic fixture in both presentation modes:

```powershell
python -X utf8 skills/battle-scaling/scripts/battle.py analyze --input skills/battle-scaling/assets/cases/pk-dual-presentation-synthetic.json --mode all --pk overview --output runs/demo-overview
python -X utf8 skills/battle-scaling/scripts/battle.py analyze --input skills/battle-scaling/assets/cases/pk-dual-presentation-synthetic.json --mode all --pk process --output runs/demo-process
```

`--mode` selects the evidence policy; `--pk` selects the presentation. They are independent. Synthetic fixtures check tool behavior and are not real character assessments.

## Novels: build a dossier before rating or matching

Novel characters default to their ending state: after the final time skip in a completed novel, or the latest verified chapter in an ongoing work. A user-specified period takes precedence. Characters without a completed assessment or a qualified dossier first receive an ending-state ability and feat dossier, then a rating or matchup. Existing dossiers can be reused after checking edition, coverage, receipts, and host acceptance, with updates as needed. Scattered chapter lookups do not replace the initial full dossier workflow.

The workflow is: **verify source and edition → snapshot and chapter tasks → actually read from the ending backward → JSON reading receipts → sequential acceptance by the main Agent → build and verify → host review of abilities, feats, and state inheritance → rating/VS**. Track each ability's acquisition, upgrades, retention or loss, successes, failures, limits, resistances, and canonical combinations. Hypothetical combinations retain explicit assumptions.

The following uses the standalone library. Replace the source, title, edition, and receipt paths with real inputs. The `prepare` output must be a new or empty directory:

```powershell
python -X utf8 tools/combat-novel-refpack/refpack.py prepare --source book.txt --output runs/book-bundle --work "Book title" --edition "Specific edition"
python -X utf8 tools/combat-novel-refpack/refpack.py tasks --bundle runs/book-bundle
python -X utf8 tools/combat-novel-refpack/refpack.py search --bundle runs/book-bundle --query "Original ability term"
# After the Agent reads a task and writes its receipt, accept receipts sequentially.
python -X utf8 tools/combat-novel-refpack/refpack.py accept --bundle runs/book-bundle --input runs/reviews/actual-review.json
python -X utf8 tools/combat-novel-refpack/refpack.py build --bundle runs/book-bundle
python -X utf8 tools/combat-novel-refpack/refpack.py verify --bundle runs/book-bundle
```

The Skill's bundled `skills/battle-scaling/scripts/novel_refpack.py` provides the same six commands, so a Skill-only installation can use the workflow. For non-UTF-8 text, supply a verified encoding explicitly, for example `prepare --encoding gb18030`.

The current Agent reads and writes receipts by default; users do not need to fill them out manually. The library includes no LLM or paid API client. `tasks` does not read the book, and `complete` only means that the receipts declare full coverage: the program still reports `semantic_read_verified:false`. Unread material remains `partial`; blocked access to the full text permits only a partial dossier and provisional conclusions. `CASE.candidate.json` still needs feat, physics, special-ability, and tier reviews. See the [standalone library](tools/combat-novel-refpack/README.md) and [full novel pipeline](skills/battle-scaling/references/novel-refpack-pipeline.md).

## Layout and public distribution

```text
skills/battle-scaling/           Skill, rules, tools, templates, and tests
tools/combat-novel-refpack/      Standalone novel evidence library
tools/import_handbook_corpus.py  Import optional handbook OCR from a local directory
tools/verify_package.py          Verify the public Skill's static file fingerprints
docs/public-distribution.md      Public material scope and optional dependencies
NOTICE.md                       Sources and licensing boundaries
```

The public package includes code, rule tables, required source fingerprints, templates, synthetic/conditional cases, tests, and license notices. **It does not include full novel texts, the handbook PDF or complete OCR, original-work screenshots, model weights, private site runtime databases, secrets, or personal tool-path configuration.** Historical source records in documentation are not local path dependencies.

Default finite- and higher-tier calculations can run without the complete handbook corpus. Full-text handbook search, page reading, and original-page inspection require separately supplied local material matching the source fingerprints. The importer neither downloads material nor relaxes hash checks. Missing material must not be reported as already read. See [public distribution details](docs/public-distribution.md).

## Tests and licensing

```powershell
python -X utf8 -m unittest discover -s skills/battle-scaling/tests -v
python -X utf8 -m unittest discover -s tools/combat-novel-refpack/tests -v
```

Tests cover calculations, source locations, constraints, state resolution, and records for specific inputs. They do not guarantee complete research of a new work, accurate visual measurements, or statistically calibrated win rates. Tests skipped for missing optional local material do not count as validated functionality.

See [external-idea boundaries](skills/battle-scaling/references/external-ideas.md) for what was adopted and excluded; upstream models are not part of the runtime. The repository has not assigned a single open-source license covering all original content. Existing third-party licenses apply to their respective material, including the preserved original `novel-refpack` MIT notice. Software licenses do not grant rights to the works being analyzed. See [NOTICE](NOTICE.md).
