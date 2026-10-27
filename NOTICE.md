# 来源与许可 / Provenance and licensing

原创软件与原创文档按根目录 [MIT](LICENSE) 许可；第三方内容不因此被重新授权。详细依赖、上游 GitHub、作者署名、适用条款及改编边界见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

Original software and original documentation use the root [MIT license](LICENSE). Third-party content is not relicensed by it. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependencies, upstream repositories, attribution, terms and adaptation boundaries.

- VSB 改编资料 `skills/battle-scaling/references/vsb-*.md` 与 `skills/battle-scaling/rulesets/vsb-current-*.json`：CC BY-SA 3.0，署名 VS Battles Wiki contributors；独立程序仍为 MIT。
- novel-refpack：保留上游 MIT 通知，真实来源为 https://github.com/scp3500/novel-refpack 。
- 可选 Cited Feats 数据：普通行 CC BY 4.0，SCP 行 CC BY-SA 3.0；不在包内预置全库。
- PyMuPDF：独立安装的 AGPL／商业双许可组件，不以本项目 MIT 覆盖其义务。
- 原作全文、参考册 PDF／完整 OCR、第三方截图、模型权重和私人运行数据不随公开包分发。

本次审计只覆盖当前发布包，不覆盖 Git 历史，也不构成无侵权保证。/ This audit covers the current distribution, not Git history, and is not a warranty of non-infringement.

## Video dependencies and reusable assets

Battle Video Studio uses [Remotion 4.0.539](https://github.com/remotion-dev/remotion/blob/main/LICENSE.md) under the Remotion License, with Free/Company eligibility conditions; it is not MIT. Its installed-version notice is retained in `tools/battle-video-studio/licenses/Remotion-LICENSE.md`. The unchanged Smiley Sans font is copyright atelierAnchor (2022–2024), under [SIL OFL 1.1](https://github.com/atelier-anchor/smiley-sans/blob/main/LICENSE), including reserved font names; the notice accompanies the font. Original reusable VS/branding graphics use the project MIT license. No underlying reference audio, source footage or character art is included.

## SCP-derived semantic benchmark material

The short excerpts, Chinese paraphrases and adapted questions/rubrics for SCP cases in `skills/battle-scaling/benchmarks/semantic-boundaries/` are based on [SCP-3143](https://scp-wiki.wikidot.com/scp-3143) by [The Great Hippo](https://www.wikidot.com/user:info/the-great-hippo) and [SCP-3812](https://scp-wiki.wikidot.com/scp-3812) by [djkaktus](https://scp-wiki.wikidot.com/djkaktus). These SCP-derived portions and their adaptations use [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/), not MIT. Changes: short selection, Chinese paraphrase, contextual summaries, adversarial inferences and review criteria. Authors, source URLs and license declarations remain with the source records. No complete SCP story or associated image is bundled.

## Optional DEATH BATTLE! cover variant

`skills/battle-scaling/assets/media/pk-cover/variants/cosmic-death-battle/template-1920x1080.png` is an optional generated layout example bearing the **DEATH BATTLE!** wording. Its generation instructions are preserved in the adjacent `template-prompt.txt`; it was generated with that text, rather than supplied as an official brand asset. The underlying show/brand is [DEATH BATTLE](https://deathbattle.gg/en-usd). The brand wording and any associated trademark rights are **not** represented as project-owned or granted under MIT. This package has no affiliation, sponsorship or endorsement from DEATH BATTLE. No license to a third-party brand is granted by this example. The default original cover designs and the video's silver VS remain available independently.
