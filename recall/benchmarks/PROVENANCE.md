# Data provenance and licensing

The `recall/benchmarks/` tree contains third-party material. The MIT license at the root
of this repository covers the code in it — **not** the material described here, which
remains under its upstream terms.

## Where the benchmark data comes from

PR instances (metadata, base/head commits, and the human reviewers' comment text) are
sampled — seeded, so reproducibly — from
[AACR-Bench](https://github.com/alibaba/aacr-bench) (Apache-2.0), which collects and
itself redistributes them. Committed `.diff` files are the corresponding PR diffs fetched
from the public GitHub repositories below. Result JSONs contain model-generated review
text plus short excerpts of, and line references into, that upstream code. No GitHub
usernames or reviewer identities are stored anywhere in this tree (verified by scan; the
comment text is unattributed).

## Upstream repositories and their licenses

Code excerpts and diffs remain under the license of the repository they came from
(SPDX IDs queried from the GitHub API, 2026-08-31):

| License                            | Repositories                                                                                                                                                                                                                                                                  |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Apache-2.0                         | ClickHouse/ClickHouse, alibaba/spring-ai-alibaba, cline/cline, dbeaver/dbeaver, google-gemini/gemini-cli, infiniflow/ragflow, kestra-io/kestra, keycloak/keycloak, linera-io/linera-protocol, microsoft/typescript-go, opencv/opencv, vllm-project/vllm, wavetermdev/waveterm |
| MIT                                | dotnet/aspnetcore, electron/electron, facebook/react, filamentphp/filament, laravel/framework, lvgl/lvgl, microsoft/semantic-kernel, mrdoob/three.js, ollama/ollama, symfony/symfony                                                                                          |
| BSD-3-Clause                       | appwrite/appwrite, valkey-io/valkey                                                                                                                                                                                                                                           |
| AGPL-3.0                           | CherryHQ/cherry-studio, bluewave-labs/Checkmate, immich-app/immich                                                                                                                                                                                                            |
| GPL-3.0                            | comfyanonymous/ComfyUI                                                                                                                                                                                                                                                        |
| LGPL-2.1                           | FreeCAD/FreeCAD                                                                                                                                                                                                                                                               |
| Zlib                               | libsdl-org/SDL                                                                                                                                                                                                                                                                |
| GPL-2.0-or-later (parts LGPL-2.1+) | mpv-player/mpv                                                                                                                                                                                                                                                                |
| See notes below                    | elastic/elasticsearch, n8n-io/n8n, timescale/timescaledb                                                                                                                                                                                                                      |

## The source-available cases, specifically

- **elastic/elasticsearch** — triple-licensed (Elastic License 2.0 / SSPL-1.0 /
  AGPL-3.0, per the repository's LICENSE.txt); some of the committed diff hunks touch
  `x-pack/` paths, which are Elastic License 2.0. ELv2's grant expressly permits
  copying and distribution provided its three limitations are respected (no managed
  service offering, no license-key circumvention, no removal of notices) — none of
  which redistributing PR diffs for benchmarking implicates. License notices in the
  diffs are preserved verbatim.
- **n8n-io/n8n** (Sustainable Use License) and **timescale/timescaledb** (Timescale
  License / Apache-2.0 mix) — **no code diff from either repo is committed here.**
  They appear only inside result JSONs as human/model review-comment text with file
  and line references.

If you are an upstream maintainer and want material from your project removed from this
benchmark data, open an issue and it will be taken out.

## Machine-local pointers

Result-pointer JSONs record the absolute `rundir` path of the panel run that produced
them (under the producing machine's `~/.cache/llm-panel/runs/`). Those directories exist
only on that machine: the pointers are provenance records, not portable inputs.
Re-deriving a results directory from its rundirs (`aacr-upstream reextract`) therefore
only works where the runs were made; scoring the committed result JSONs with
`aacr-score` works anywhere.
