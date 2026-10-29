# Battle Video Studio

Editable Remotion battle-comparison videos with nine music-timing presets, user-supplied character media, Smiley Sans, reusable VS/branding graphics and H.264/AAC export.

## Install and run

Requires Node.js 22.18+ (tested with 26.3), npm, FFmpeg/ffprobe and Chrome or Edge. Install these separately. Dependencies are pinned in package-lock.json.

```powershell
npm ci
npm start
```

Open <http://127.0.0.1:3210>. The workbench imports character images/videos, edits names and comparison results, prepares an editable project and previews/exports it. No music, reference footage, character images or generated comparison video is bundled. The initial preview explains what to import.

## Music and templates

Pick V01—V09 first, then obtain audio you have permission to use and match the chosen preset's exact edit and cut timings. Presets contain timing observations, not the underlying song or an audio license. A similar BPM or sufficient file duration does not establish a match.

```powershell
node scripts/select-template.mjs
node scripts/import-music.mjs --template V05 --file "your-audio.wav"
```

The importer uses FFmpeg to create the preset's AAC audio file under public/music/. It refuses an existing file unless --replace is supplied. Alternatively, specify `audio.path` in a job JSON to use your own file directly. A different song/edit needs a newly calibrated timing template.

Import character media through the workbench, or add local paths to `characters.a/b.clips`. Prepare actual source intervals and assign intro, plate, highlight and finish roles. Candidate quality, excitement, cropping and continuity come from the person/Agent who watched the media. The compiler plans playback intervals and speed; it does not recognize characters, judge copyright or semantically understand footage. See [candidate planning API](../battle-video-studio/docs/media-planning-api.md).

```powershell
npm run prepare-job -- your-job.json
npm run studio
npm run render -- --job your-project --range 0:90 --out preview-output
```

Keep the entire project folder, its projects/ files and referenced public/ user media to continue editing. Same-project preparation preserves the selected template. Render outputs use distinct filenames, with the prior successful export retained on failure. The format is a Remotion project, not a Jianying/Premiere native project.

## Footage review before delivery

Follow the [media review and rework rules](../../skills/battle-scaling/references/media-review.md), including when using another editor or custom FFmpeg scripts. Watch the complete chosen source interval, inspect it in its actual split-screen or portrait layout with text and effects, and review the exported cuts. A clear reveal does not certify the comparison plate. For very short source clips, inspect the entire frame sequence; midpoint screenshots miss hidden cuts.

Comparison plates and reveal slots use one sufficiently long, continuous shot. Known internal cuts are excluded even at S quality; short footage is not looped or automatically slowed to fill these slots. A plate can still be reused across different attributes. New long-display planning defaults to original speed; only an individually selected `allowSlowdown:true` candidate may be slowed, never below 0.5x. Rejected footage must be replaced or recropped, not approved through metadata. Unmarked legacy continuity remains a prompt to inspect, not a visual certificate.

When a winner display needs letterbox space, the default uses the same synchronized footage enlarged, blurred and dimmed behind a complete sharp foreground. The branding outro remains as designed. Keep poster content to the requested names, versions, VS, selected divider and small project watermark unless the user requests more.

## Results and limitations

Production videos consume an upstream researched winner, difficulty and comparison results. The editor does not decide winners by vote counts. A media demonstration must be labelled as such. Templates preserve independent timing/layout/effect parameters; they do not recreate source actors' expressions, character actions or all effects in an unseen reference.

```powershell
npm test
npm run typecheck
```

Local template-motion studies that require reference footage are not registered in this distribution. The nine reusable production presets and their effects remain available through BattleEdit.

## Licenses

Original project code and reusable project graphics use the included MIT license. [Remotion](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) uses its own Remotion License, not MIT; review its Free/Company eligibility for your actual organization. A copy matching the installed 4.0.539 dependency is in [licenses/Remotion-LICENSE.md](../battle-video-studio/licenses/Remotion-LICENSE.md). [Smiley Sans](https://github.com/atelier-anchor/smiley-sans) by atelierAnchor is supplied unchanged under [SIL OFL 1.1](../battle-video-studio/public/fonts/SmileySans-OFL.txt), including its reserved font names and copyright. React/React DOM are MIT; TypeScript is Apache-2.0. FFmpeg builds have their own LGPL/GPL conditions. See [third-party notices](THIRD_PARTY_NOTICES.md).
## Exported-frame review

After rendering, run `node scripts/review-video.mjs --job project-id --final final.mp4 --out review-new` in the Studio directory. It creates a clickable frame viewer for every comparison/reveal and adjacent cut frames from the actual exported video. It does not classify faces, judge excitement or certify quality. Review the full video at normal speed as well. Preserve original source IDs and time ranges when importing renamed, trimmed or re-encoded clips; different filenames do not make repeated footage new.

