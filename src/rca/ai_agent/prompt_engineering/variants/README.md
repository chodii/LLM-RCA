# Prompt variants (thesis appendix, "Prompt Optimization")

Selected with `DESExperiments --preset NAME`; `--prompts`, `--tools` and
`--reported-time-hint`/`--no-reported-time-hint` override single parts.

| Preset | Prompts / tools | Reported-time hint | Provenance |
|---|---|---|---|
| `before-po` | `variants/before-po/` | off | Appendix E of the thesis. |
| `after-po` | `variants/after-po/` | on | Appendix F of the thesis, including the anonymized illustrative RCA report. |
| `extended` (default) | `DESAI-prompts.json`, `DESAI-tools.json` | on | Appendices F and F.1 of the thesis, including the anonymized illustrative RCA report and the extended retrieval limits. |

The reported-time hint is the text `This incident occured around (yyyy-mm-dd):<date>`
prepended to the incident description (added during prompt optimization).

The `limit` maximum and the tool-call counts are soft instructions to the
model; `--max-records` sets a hard cap.
