# Distribution synchronization

Build upload-ready archives only after synchronization and verification:

```sh
python -X utf8 tools/build_release.py --out ../release-assets/v1.21.1
```

The builder uses the static manifests for both ZIPs, verifies archive entry bytes, writes SHA256SUMS.txt, preserves existing assets and performs no Git or network publishing. The full ZIP contains all declared tools; the smaller Skill ZIP is explicitly separate. Do not ZIP the working directory recursively.

`tools/sync_public.py` prepares a file-based distribution from explicit source directories. It does not install software, alter sources, overwrite site databases, or invoke Git/network publishing. Run against a separate target first.

```powershell
python -X utf8 tools/sync_public.py --skill-source "installed-skill" --video-source "video-source" --novel-source "novel-source" --target "distribution-copy"
python -X utf8 tools/sync_public.py --skill-source "installed-skill" --video-source "video-source" --novel-source "novel-source" --target "distribution-copy" --apply
python -X utf8 tools/verify_package.py --root "distribution-copy"
```

Without `--apply` it only plans and scans the proposed static payload. With `--apply`, it also verifies the actual destination and exits with a failure if validation fails. Identical repeated inputs do not rewrite existing static files. The destination must be separate from all source trees, outside installed Agent skill directories, and free of links that leave the destination. Runtime files are neither copied nor deleted; an existing site library remains untouched. Use a clean distribution target for release preparation.

## Release privacy and completeness gate

Privacy scanning runs when preparing or verifying a distribution; it adds no work to rating, research, writing or rendering. `tools/publication_guard.py` is shared by synchronization and verification. It checks:

- Credential/session filenames, runtime configuration, acquisition histories, credential literals, common provider key formats, authorization headers, credentialed or signed URLs, personal contact details and machine-specific paths. Reports contain relative locations and finding types, never matched values.
- Embedded image text and EXIF/GPS metadata. Install Pillow for this release check (`python -m pip install Pillow`); inability to inspect an asset fails validation. This is metadata inspection, not OCR or a replacement for visually checking published images.
- Every actual upload candidate, including files absent from the manifest. In a Git checkout, candidates are tracked files plus untracked files not ignored by Git. A tracked private file still fails even if a new ignore rule matches it. In a standalone distribution folder, all files outside dependency/build caches are checked; Git ignore rules do not make a ZIP safe.
- Complete manifest coverage and byte hashes. Only `docs/distribution-manifest.json` (the manifest itself) and generated `docs/sync-summary.json` are outside its file list; both are still privacy-scanned. Extra files, missing files, linked paths, invalid paths, unknown binary files and files above the scan limit fail validation.

The root `.gitignore` excludes user runtime/session files from ordinary Git additions. If a runtime file was already tracked, remove only that exact file from the index using `git rm --cached -- <path>`; preserve its on-disk configuration. Do not disable filtering to publish it. Build archives from a verified clean distribution or the explicit static manifest, never by archiving a working directory containing ignored runtime data.

Fixed loopback test credentials and public font attribution contacts have narrow exceptions bound to the exact relative file, finding type and value fingerprint. The test directory is not exempt: adding a new credential to the same approved test must fail. New exceptions require reviewing their purpose and provenance rather than suppressing a whole class of findings.

Run the focused regression tests after changing these release tools:

```powershell
python -X utf8 -m unittest discover -s tools -p "test_public*.py" -v
```

The gate is an offline check of current distribution files. It does not validate keys against services, inspect Git history or prove that an image contains no visually embedded private information. A suspected real credential must be removed from distribution; if it was exposed, revoke or rotate it with its provider.

## Included transformations

- Preserve executable rating/research logic, named rules, units, formulas, mathematical bridges, source fingerprints, synthetic tests and provenance/licensing notices.
- Include the original-project LICENSE in installable Skill/standalone tool directories, with separate upstream/component notices and license exceptions retained.
- Keep independently written `references/writing-experience.md` from this repository byte-for-byte, including edits already present; redirect retired example-index links to it. No story text or renamed substitute story is inserted.
- Follow the established handbook boundary: page locators stay, nonfunctional historical case dossiers are omitted, page inventory contains locator fields, and long redundant `short_quote/short_excerpt` metadata is omitted. Functional conditions and formulas are retained.
- Remove machine-specific source paths and links to excluded original images; historical locators become abstract identifiers rather than required directories.
- Derive the standalone novel tool's core module from the supplied Skill's `scripts/combat_refpack` as the single authority; obtain its wrapper/docs/independent tests and upstream license from the separate novel source. Keep core video code, nine timing/layout/effect parameter sets, reusable original VS/branding graphics, the unchanged OFL font and applicable notices.
- Register the production video composition without footage-dependent study compositions; initialize an empty media-import preview, never copy an active user project, and provide an explicit music-import command.

Music import, missing-audio guidance, bootstrap and empty-preview behavior are implemented in the video source itself. Synchronization copies these implementations; it does not maintain a second renderer/service implementation.

## Excluded

Site/access libraries, runtime configuration, credentials, full handbook OCR and `pages.jsonl`, source scans/screenshots, complete writing-example works, source music/video/character media, downloads, outputs, caches, environments, third-party source libraries and model weights are not copied. `public/projects`, `public/uploads`, `public/music` and reference collections are absent from the video payload. User-generated runtime files remain outside the static manifests.

`skills/battle-scaling/package-manifest.json` covers the Skill. `docs/distribution-manifest.json` covers the complete static distribution, including video/novel tools and licensing notices. These verify distributed bytes, not research semantics or media rights. Runtime creation, test execution and user imports are separate from the shipped file list.

SCP-derived benchmark excerpts/paraphrases retain per-source author, author-page and original-work links under CC BY-SA 3.0. Remotion is governed by its own license and the font by SIL OFL 1.1. See [third-party notices](../THIRD_PARTY_NOTICES.md).

The handbook reader is copied from the shared Skill implementation. Missing optional full OCR leaves `info` and reviewed `rule` access available; full-text operations ask for a matching locally supplied corpus. For transformed rule-index metadata, the distribution manifest binds the actual distributed index and retains the original index fingerprint separately. No new rule version or accepted research record is manufactured.
