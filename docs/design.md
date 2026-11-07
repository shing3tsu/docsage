# docsage design

| | |
|---|---|
| Author | [name] |
| Date | 2026-11-07 |
| Status | Draft |
| Repository | https://github.com/shing3tsu/docsage |
| Code license | MIT, copyright 2026 Sina Ghaffari |

## Overview

docsage is a self-hosted retrieval assistant over the public Kubernetes, Docker, and Prometheus documentation. It runs from Docker Compose on a Windows 11 laptop with WSL2, an RTX 4070 Laptop (8 GB VRAM), and 16 GB RAM. The running stack is six services on the Compose bridge network `internal-net`: vLLM serving `Qwen/Qwen3-4B-AWQ` on the GPU, Text Embeddings Inference (TEI) serving `BAAI/bge-small-en-v1.5` on the CPU, Qdrant, Redis, Postgres 18, and LiteLLM. LiteLLM is the only client entry. The only client-facing model names are `chat` and `embed`.

Ingest, the NestJS `POST /ask` and `GET /health` API, and the static chat UI are not built. They have no Compose service and no published port. Qdrant has no collection yet. The product goal, also not implemented, is that every answer includes the source, its license, and a link to the exact page. A chat through the LiteLLM proxy measured about 63 completion tokens per second. That is the only performance figure in this design. No latency target, QPS target, or embedding throughput is defined.

## Background & Motivation

The operator wants a local system for CKA study. The documents are chosen, licensed, and pinned, and a local model writes the answer from the retrieved pages. Hosted chat products are the wrong tool: they do not pin the docs revision, they do not keep the corpus on the laptop, and they do not force the license and the page link into the answer.

The repository started as license, README, and ignore rules. Git history then added the Compose services. Two model moves matter, and neither superseded choice is what runs now. The stack moved to a pinned 3B Qwen so the 8 GB GPU had room for a KV cache (`c8ffc4f`). It then moved to `Qwen/Qwen3-4B-AWQ` so the public repo stays on an Apache 2.0 license (`49b7951`). The process that `compose.yaml` starts is `Qwen/Qwen3-4B-AWQ` at revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3` only.

`README.md` is behind the tree. Its Status section still says Compose is future work ("Compose (vLLM, then TEI and LiteLLM), ingestion, and the API come next"). `compose.yaml` already defines vLLM, TEI, Qdrant, Redis, Postgres, and LiteLLM. Ingest, the API, and the chat UI are still future work. `LICENSE` still has a stale sentence naming `Qwen2.5-7B-Instruct-AWQ`. That sentence is not the served model. This design does not edit `LICENSE`.

## Goals & Non-Goals

### Goals

- Answer questions about Kubernetes, Docker, and Prometheus from the official docs listed in the README source table.
- Pin images by tag and digest, and pin the chat and embedding model revisions, so a later run uses the same weights and the same containers.
- Keep the GPU inside the flags already set in `compose.yaml`: `gpu-memory-utilization` 0.80, `max-model-len` 4096, `max-num-seqs` 4, thinking disabled.
- Expose generation and embedding only through LiteLLM names `chat` and `embed`, declared in `config/litellm.yaml`.
- Publish service ports on `127.0.0.1` only.
- When ingest and the API exist, attach source, license, and an exact page link to every answer, and do not create duplicate vectors on a second ingest run.
- Keep the vector index able to filter by source (for example Kubernetes only), which is the Qdrant goal stated in the README.

### Non-Goals

- Lens. Out of scope. Not a service in this design.
- A semantic cache. Rejected. Redis is an exact-match response cache.
- A 7B model, an FP16 4B, or any second GPU-resident service. Ruled out by the 8 GB card and the 0.80 cap.
- Designing the MCP server. vLLM has the Hermes tool parser enabled for a later MCP server. That server is not built, and this design does not specify it.
- Changing `compose.yaml`, `config/litellm.yaml`, or `.env`. In particular, this design does not change `general_settings.store_model_in_db`.
- Assigning a port to NestJS or the static UI.
- Naming a Qdrant collection. None exists. The unbuilt ingest job creates it later.
- A metrics or alerting stack. Prometheus in this project is a documentation corpus, not a scraper for this stack.
- Chunk size, overlap, batch size, or an ingest framework. The README does not choose them. NestJS is the only application framework named, and it is only for the unbuilt API.
- Multi-user deployment, a public bind address, or a feature-flag service. This is one laptop.

## Proposed Design

### Running Compose topology

Project name in `compose.yaml` is `docsage`. The network is `internal-net` with `driver: bridge`. It is not Docker `internal: true`. The bridge does not block egress. Containers can reach the internet, which is how the chat and embedding weights download on first start.

`litellm` waits until `postgres` and `redis` are healthy. It does not wait on `vllm` or `tei`. Nothing in the running graph calls Qdrant. The unbuilt ingest job and the unbuilt API are the future Qdrant clients, and they are not on this diagram.

```mermaid
flowchart TB
  subgraph internal-net [internal-net bridge]
    vllm[vllm]
    tei[tei]
    qdrant[qdrant]
    redis[redis]
    postgres[postgres]
    litellm[litellm]
  end
  hf-cache[(hf-cache)] --- vllm
  hf-cache --- tei
  qdrant-data[(qdrant-data)] --- qdrant
  redis-data[(redis-data)] --- redis
  postgres-data[(postgres-data)] --- postgres
  litellm -->|"api_base http://vllm:8000/v1"| vllm
  litellm -->|"api_base http://tei:80/v1"| tei
  litellm -->|depends_on healthy| redis
  litellm -->|depends_on healthy| postgres
```

Published ports are loopback only. These are the only host ports. NestJS and the static UI are not in this list because they are not built.

| Service | Host publish | Container port | Image |
|---|---|---|---|
| vllm | `127.0.0.1:8000` | 8000 | `vllm/vllm-openai:v0.33.0@sha256:d825baf9ce4b1b6bfc5ecc7b79880c7e6748c65a72d697ce3d47607aafa84c6e` |
| tei | `127.0.0.1:8080` | 80 | `ghcr.io/huggingface/text-embeddings-inference:cpu-1.9@sha256:2538ea1c9640d3763b15af668039d24172d063b42337b0c27796fc2be180c78d` |
| qdrant | `127.0.0.1:6333` | 6333 | `qdrant/qdrant:v1.20.0@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2` |
| redis | `127.0.0.1:6379` | 6379 | `redis:8.10.3@sha256:f245f4c83b84a9e9a0588da1c9456e579455310f0945d5db52cd2ba27f2000cc` |
| postgres | `127.0.0.1:15432` | 5432 | `postgres:18.6@sha256:e923a22ac074261dd73970c57edf659475bf0497cb9456f17d98ed7cdd3ca913` |
| litellm | `127.0.0.1:4000` | 4000 | `ghcr.io/berriai/litellm:v1.108.1@sha256:562251f032a0075a5e5a775b8f44aa9f9f1e93d16562892565f29bfa23fbf2f6` |

Qdrant gRPC is not published. The host mapping is REST port 6333 only. The Compose file does not publish 6334. This design does not claim that gRPC is disabled inside the container.

Named volumes:

| Volume | Mounted by | Mount path |
|---|---|---|
| `hf-cache` | `vllm` and `tei` | `/cache/huggingface` (`HF_HOME`) |
| `qdrant-data` | `qdrant` | `/qdrant/storage` |
| `redis-data` | `redis` | `/data` |
| `postgres-data` | `postgres` | `/var/lib/postgresql` |

`vllm` also sets `gpus: all`, `shm_size: 4g`, and `stop_grace_period: 120s`. Its logging driver is `json-file` with `max-size` 10m and `max-file` 3. No other service sets a logging block. No service sets a `restart` policy.

### vLLM

`vllm` serves the chat model on the GPU through the OpenAI-compatible image `vllm/vllm-openai`. The command in `compose.yaml` is the full flag set:

- `--model Qwen/Qwen3-4B-AWQ`
- `--revision 74d4bd2bd4bff9cafc9345221320bffb08b406a3`
- `--default-chat-template-kwargs '{"enable_thinking": false}'`
- `--port 8000`
- `--host 0.0.0.0` (inside the container network namespace; the published port is still `127.0.0.1:8000`)
- `--max-model-len 4096`
- `--gpu-memory-utilization 0.80`
- `--max-num-seqs 4`
- `--enable-auto-tool-choice`
- `--tool-call-parser hermes`

The model license is Apache 2.0. The README states that AWQ 4-bit weights keep the 4B model near 2.5 GB. Thinking mode is off, so an answer is the reply itself. Hermes is enabled for a later MCP server. That server is not built, and this document does not design it. `0.80` of the 8 GB card is 6.4 GB. That is the cap vLLM is configured to use.

`HF_TOKEN` and `VLLM_API_KEY` are passed from the environment. This document does not record their values. `.env.example` marks `HF_TOKEN` as optional.

### TEI

`tei` uses the CPU image above. The command sets `--model-id BAAI/bge-small-en-v1.5`, `--revision 5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, `--api-key` from `TEI_API_KEY`, and `--json-output`. The model license is MIT. Vectors are 384-dimensional. The container listens on port 80. The host publish is `127.0.0.1:8080:80`. TEI is on CPU because the GPU is already taken by vLLM. The same model is what the README assigns to both chunk embeddings and question embeddings.

### Qdrant

`qdrant` is v1.20.0. Storage is the named volume `qdrant-data`. REST is published on `127.0.0.1:6333`. The service reads `QDRANT_API_KEY` into `QDRANT__SERVICE__API_KEY` and `QDRANT_LOG_LEVEL` into `QDRANT__LOG_LEVEL`. `.env.example` sets the log-level placeholder to `INFO` and leaves the key empty. No collection exists yet. The unbuilt ingest job creates the collection later. Vectors stored there are 384-dimensional, matching `bge-small-en-v1.5`. This design does not name the collection.

### Redis

`redis` is 8.10.3. It is the exact-match response cache for LiteLLM (`cache: true`, `cache_params.type: redis` in `config/litellm.yaml`). It is not a semantic cache. The container requires a password via `--requirepass` from `REDIS_PASSWORD`. The host publish is `127.0.0.1:6379:6379`. On `internal-net` the service DNS name is `redis`. That DNS name is not the same fact as the operator's `REDIS_HOST`.

LiteLLM receives `REDIS_HOST`, `REDIS_PORT`, and `REDIS_PASSWORD` from the environment. `compose.yaml` passes those variables through. It does not set them to the service DNS name. `.env.example` leaves `REDIS_HOST` and `REDIS_PORT` empty. This design does not fill them in and does not print a password.

### Postgres

`postgres` is image tag `postgres:18.6` (Postgres 18). It holds LiteLLM admin UI data, not the vector index. The named volume is `postgres-data`, mounted at `/var/lib/postgresql`. The host port is `127.0.0.1:15432` because Windows has reserved 5432. Inside `internal-net` the port is still 5432. The `DATABASE_URL` set on the `litellm` service points at `postgres:5432`:

```yaml
DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

`POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` come from the environment. `.env.example` leaves them empty. No credential is recorded here.

### LiteLLM

`litellm` is v1.108.1. It is the only supported client entry. The host publish is `127.0.0.1:4000`. The config file `config/litellm.yaml` is mounted read-only at `/app/config.yaml`. The process is started with `--config /app/config.yaml`.

The only client-facing names are `chat` and `embed`:

```yaml
model_list:
  - model_name: chat
    litellm_params:
      model: openai/Qwen/Qwen3-4B-AWQ
      api_base: http://vllm:8000/v1
      api_key: os.environ/VLLM_API_KEY
  - model_name: embed
    litellm_params:
      model: openai/BAAI/bge-small-en-v1.5
      api_base: http://tei:80/v1
      api_key: os.environ/TEI_API_KEY
```

There are no other model names. The project rule is that these definitions stay in `config/litellm.yaml`, not as models managed in Postgres. The same file also sets `general_settings.store_model_in_db` to `true`. Both facts stand. This design does not claim the flag is false, and it does not propose changing it. Callers still use the names declared in the mounted yaml. The flag being true means LiteLLM is also allowed to store model configuration in Postgres. The supported names remain the two entries above.

Other settings in that file, recorded so the privacy section does not drift from the config: `cache: true` with `cache_params.type: redis`; `allow_dynamic_callback_disabling: false`; `turn_off_message_logging: false`; `redact_user_api_key_info: false`; `master_key: os.environ/LITELLM_MASTER_KEY`; `database_url: os.environ/DATABASE_URL`; `disable_env_credential_login: true`; `disable_spend_logs: false`; `disable_requester_ip_address_logging: false`; `store_prompts_in_spend_logs: true`.

`litellm` is also given `LITELLM_SALT_KEY`, `TEI_API_KEY`, and `VLLM_API_KEY` from the environment. Values are not recorded here.

### Why each running component was chosen

**vLLM serving `Qwen/Qwen3-4B-AWQ`, not Ollama and not a 7B or an FP16 4B.** Ollama is the obvious laptop default. It is not what this repo runs. The running server is an OpenAI-compatible vLLM process with a pinned Hugging Face revision, AWQ weights the README puts near 2.5 GB, `gpu-memory-utilization` 0.80 (a 6.4 GB cap on this 8 GB card), `max-model-len` 4096, `max-num-seqs` 4, thinking disabled, and the Hermes tool parser for a later MCP server. The public-repo constraint is Apache 2.0, which is why the served model is `Qwen3-4B-AWQ` and not the model named in the stale `LICENSE` sentence. A 7B was not given room on this GPU. An FP16 4B is ruled out because the weights alone would consume the card and leave no KV cache under the 0.80 cap. No benchmark beyond the single chat measurement (about 63 completion tokens per second through the LiteLLM proxy) is cited.

**TEI with `bge-small-en-v1.5` on CPU, not a GPU embedder and not a larger embedder.** The GPU is already taken by vLLM. A second GPU-resident service does not fit. The CPU image (`text-embeddings-inference:cpu-1.9`), the pinned revision, the MIT license, and 384 dimensions are the embedder that is actually configured. A larger embedder is not in the Compose file and is not introduced here.

**Qdrant, not pgvector in the Postgres instance that already exists for LiteLLM.** Postgres is the LiteLLM admin store. The docs index is a different life cycle: its own named volume (`qdrant-data`), REST on `127.0.0.1:6333`, and the README requirement to filter by source. No collection exists yet, so there is nothing to migrate out of Postgres. Putting vectors in the LiteLLM database would tie the index to that admin volume and to Postgres major-version upgrades. That trade is rejected.

**Redis exact-match response cache, not a semantic cache.** A semantic cache was rejected. The config is `cache: true` and `type: redis` only. Exact match does not add a second retrieval path and does not need another model. The cost is that only repeated identical requests hit the cache. That is the accepted trade.

**Postgres 18, not SQLite, for LiteLLM admin UI data.** The running proxy is wired to Postgres (`database_url`, `depends_on` healthy `postgres`, volume `postgres-data`). SQLite would remove a container. It would also drop the healthcheck gate LiteLLM already waits on, and it is not the store this Compose file uses. The host port is 15432, not 5432, because Windows has reserved 5432. Inside the network, `DATABASE_URL` still uses `postgres:5432`.

**LiteLLM as the only client entry, not callers talking to vLLM and TEI directly.** Direct calls are possible in the sense that `127.0.0.1:8000` and `127.0.0.1:8080` are published. They are not the supported entry. LiteLLM is the place that holds the stable names `chat` and `embed`, the Redis response cache, and the admin UI backed by Postgres. One measured chat through that proxy produced about 63 completion tokens per second. This design does not split that figure into proxy overhead versus GPU time.

### What the 8 GB VRAM budget rules out

Ruled out as extra GPU work:

- A second GPU-resident service. TEI stays on the CPU image.
- A 7B model.
- An FP16 4B. The weights alone would consume the card and leave no KV cache under the 0.80 cap.

Ruled out by the current vLLM flags, not by adding services:

- Context above 4096 (`max-model-len` is 4096).
- More than 4 concurrent sequences (`max-num-seqs` is 4).
- Thinking mode (`enable_thinking` is false).

This design does not add any of those.

### Future ingest path (not built)

Ingest is not built. There is no ingest service in `compose.yaml`. The README is the whole specification used here: shallow-clone each docs repo at a pinned tag or commit, clean Markdown, split each page into chunks by heading, and store vectors plus metadata in Qdrant. A second run does not create duplicates. Metadata the product needs is source, license, and a link to the exact page. Filter by source (for example Kubernetes only) is the Qdrant goal in the README. Chunk size, overlap, batch size, point identity, and the job's language are not specified. This design does not invent them.

The job, once written, calls the existing LiteLLM name `embed`. LiteLLM forwards that to TEI at `http://tei:80/v1`. Vectors are 384-dimensional. The job is what writes Qdrant. TEI does not open a Qdrant client. The diagram keeps the required node order. The last arrow is the store of those vectors, not a TEI-to-Qdrant protocol.

```mermaid
flowchart LR
  Docs[docs repo] --> Clean[clean and chunk]
  Clean --> Embed[LiteLLM embed]
  Embed --> TEI[TEI]
  TEI --> Qdrant[Qdrant]
```

The collection is created later by this job. It has no name in this design. Because the planned pull requests do not edit `compose.yaml`, the job is not added as a seventh Compose service here. It is future work that talks to the ports already published on `127.0.0.1` (`4000` for LiteLLM, `6333` for Qdrant). Packaging beyond that is left to the ingest change itself, still without a Compose edit in the plan below.

### Future ask path (not built)

The API is not built. The static UI is not built. Neither has a port.

The README behavior for `POST /ask` is: embed the question, search Qdrant, and ask the model to answer only from those chunks. `GET /health` is the other route. The static page calls `/ask` and shows the answer and its sources. Every answer includes the source, its license, and a link to the exact page. That citation rule is the product goal. It is not implemented.

The required ask diagram is only client, NestJS, Qdrant, LiteLLM `chat`, and vLLM. TEI is not on it. Redis is not on it. When the API is built, embedding the question uses the existing name `embed`. That hop is real in the README behavior and is omitted from the diagram on purpose.

```mermaid
flowchart LR
  Client[client] --> NestJS[NestJS]
  NestJS --> Qdrant[Qdrant]
  NestJS --> Chat[LiteLLM chat]
  Chat --> vLLM[vLLM]
```

NestJS to Qdrant is the search. NestJS to LiteLLM `chat` to vLLM is the generation step. `chat` is `openai/Qwen/Qwen3-4B-AWQ` at `http://vllm:8000/v1`. No request body, response schema, or host port is defined beyond those routes and that behavior.

## API / Interface Changes

### What runs today

There is no NestJS interface. The supported client interface is the LiteLLM proxy on `127.0.0.1:4000`, with the model name set to `chat` or `embed`. Those names resolve only to the `api_base` values in `config/litellm.yaml`:

| Client name | Upstream model string | api_base |
|---|---|---|
| `chat` | `openai/Qwen/Qwen3-4B-AWQ` | `http://vllm:8000/v1` |
| `embed` | `openai/BAAI/bge-small-en-v1.5` | `http://tei:80/v1` |

Authentication material is the environment variables named in that file and in `compose.yaml`: `LITELLM_MASTER_KEY` for the proxy, `VLLM_API_KEY` for the chat upstream, `TEI_API_KEY` for the embedding upstream. Qdrant is configured with `QDRANT_API_KEY` but has no collection and no client in the repo yet.

vLLM's in-container bind is `0.0.0.0:8000`. Docker still publishes that port only on `127.0.0.1`.

### What is not built

| Interface | State | Port |
|---|---|---|
| `POST /ask` | Not built. Embeds the question through `embed`, searches Qdrant, asks `chat` to answer only from those chunks. Returns the answer with source, license, and exact page link. | None assigned |
| `GET /health` | Not built. NestJS health route from the README. | None assigned |
| Static chat page | Not built. Calls `/ask` and shows the answer and its sources. | None assigned |
| MCP server | Not built. Hermes is enabled on vLLM for later. Not designed here. | None |

No before/after schema is committed for `/ask`. The change from today is the addition of those routes in a later pull request, not a change to the LiteLLM names.

## Data Model Changes

No migration runs as part of this design. No custom SQL schema is defined.

**Postgres.** LiteLLM owns the tables it creates in `POSTGRES_DB` on `postgres-data`. That database is admin UI data (and, because `store_model_in_db` is true and spend logs are on, whatever LiteLLM persists there, including prompts when `store_prompts_in_spend_logs` is true). It is not the docs index. This design does not name LiteLLM's tables and does not add a migration.

**Redis.** Exact-match response cache entries in `redis-data`. Not vectors. Not a semantic index.

**Qdrant.** Volume `qdrant-data` is mounted. No collection has been created. The unbuilt ingest job creates the collection later. Points are 384-dimensional. The only metadata this design specifies is what the README already requires: the source, the license, and a link to the exact page. Field names are not chosen here. A second ingest run does not create duplicates. How the point identity is computed is not specified, because the job does not exist. Filter by source is required by the README once that metadata exists. Dropping the index means removing the `qdrant-data` volume. That is not a planned step.

**Weights cache.** `hf-cache` holds the runtime downloads for the pinned Qwen revision and the pinned bge revision. The README figure for the AWQ weights is near 2.5 GB. This design does not estimate the rest of the cache, the docs corpus on disk, or the Qdrant volume size. Those measurements are not in the repo.

**Corpora.** Not stored in the repo. The future ingest job shallow-clones the upstream repos. Versions are whatever tag or commit that job pins. No pin is chosen in this document.

## License

Repo code is MIT (copyright 2026 Sina Ghaffari). That MIT license does not cover weights downloaded at runtime and does not cover the documentation corpora.

`LICENSE` still says "`Qwen2.5-7B-Instruct-AWQ` is Apache 2.0, and `bge-small-en-v1.5` is MIT." The bge clause matches the running embedder. The Qwen sentence is stale. The served chat model is `Qwen/Qwen3-4B-AWQ`, Apache 2.0. Do not read the stale sentence as permission to add a 7B service.

| Item | Identifier | Repository or docs | Path | License |
|---|---|---|---|---|
| Qwen3-4B-AWQ | `Qwen/Qwen3-4B-AWQ`, revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3` | Hugging Face weights, downloaded at runtime, not in this repo | — | Apache 2.0 |
| bge-small-en-v1.5 | `BAAI/bge-small-en-v1.5`, revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a` | Hugging Face weights, downloaded at runtime, not in this repo | — | MIT |
| Kubernetes docs | https://kubernetes.io/docs/ | https://github.com/kubernetes/website | `content/en/docs` | CC BY 4.0 |
| Docker docs | https://docs.docker.com/ | https://github.com/docker/docs | `content/` | Apache 2.0 |
| Prometheus docs | https://prometheus.io/docs/ | https://github.com/prometheus/docs and https://github.com/prometheus/prometheus | `content/docs` and `docs/` | Apache 2.0 |

Answers are required to carry the source license and the page link once `/ask` exists. Until ingest and the API exist, nothing in the running stack emits that citation.

## Alternatives Considered

### vLLM + Qwen3-4B-AWQ versus Ollama, a 7B, and an FP16 4B

| Option | Result | Trade-off |
|---|---|---|
| vLLM, `Qwen/Qwen3-4B-AWQ`, revision pinned in `compose.yaml` | Chosen. Running. | OpenAI-compatible API, Apache 2.0, AWQ weights near 2.5 GB, 6.4 GB utilization cap, context 4096, 4 sequences, thinking off, Hermes parser present for later. More moving parts than a laptop model runner. |
| Ollama | Rejected. | The usual laptop default. It is not this Compose file, and it does not provide the pinned revision and the flag set above. |
| A 7B, including the model named in the stale `LICENSE` line | Rejected. | Does not fit the decision already made for this 8 GB GPU. Not a service to add. |
| FP16 4B | Rejected. | Weights alone would consume the card and leave no KV cache under the 0.80 cap. |

The earlier pinned 3B (`c8ffc4f`) was a step so the 8 GB GPU had KV-cache room. It is not the current model. The current model is the AWQ 4B from `49b7951`.

### CPU TEI versus a GPU embedder or a larger embedder

The GPU budget is spent on vLLM. Moving `bge-small-en-v1.5` onto the GPU, or swapping in a larger embedder, would be a second model resident on an 8 GB card that is already capped at 0.80 for the chat model. TEI on `cpu-1.9` keeps embedding off that card. The cost is CPU embedding on a 16 GB RAM laptop that is also running vLLM, Postgres, Redis, Qdrant, and LiteLLM. No embedding tokens-per-second figure is available, so this design does not claim the CPU choice is faster or slower than a GPU embedder. It claims only that the GPU is taken.

### Qdrant versus pgvector

pgvector would reuse Postgres 18, which is already healthy before LiteLLM starts. That is one less process. It was rejected so the index volume, the REST port, and the source filter stay off the LiteLLM admin database. Qdrant v1.20.0 is the store in `compose.yaml`. The index is empty until ingest exists. That is accepted.

### Redis exact-match versus a semantic cache

A semantic cache would sit beside `type: redis` and would cache by meaning. It was rejected. Exact match only. The cache then helps only when the same request is repeated. It does not change retrieval quality, and it does not add a model. `REDIS_HOST` and `REDIS_PORT` are still operator-supplied. The example file does not set them. See the Redis section.

### Postgres 18 versus SQLite

SQLite would be a single file and no 15432 mapping. The running admin store is Postgres 18 on `postgres-data`, with `pg_isready` as the health gate and `DATABASE_URL` aimed at `postgres:5432`. Host 15432 exists because Windows reserved 5432. Keeping SQLite out avoids a second, unused admin backend.

### LiteLLM versus direct vLLM and TEI clients

Calling `127.0.0.1:8000` and `127.0.0.1:8080` from ingest and from NestJS would skip the proxy. It would also skip the stable names, the Redis cache, and the admin UI. The supported entry stays `127.0.0.1:4000` with `chat` and `embed`. The published upstream ports remain for healthchecks and for debugging. They are not a second supported API.

## Security & Privacy Considerations

**Threat model.** One operator on one Windows 11 laptop, Compose running under WSL2. The assets are the `.env` file, the weight cache, the Qdrant volume (empty today), the Redis cache, and the Postgres volume that holds LiteLLM admin data and spend logs. The attacker who matters is another process or user on that machine, or anything that can reach the WSL loopback. This is not a multi-tenant service. Every published port in `compose.yaml` is bound to `127.0.0.1`. There is no LAN bind in the file.

**Secrets.** Names only. The operator copies `.env.example` to `.env` and fills values locally. `.gitignore` ignores `.env*` except `.env.example`, and also ignores `compose.override.yaml`, `*.pem`, `*.key`, and `kubeconfig*`. Variable names in play: `HF_TOKEN`, `VLLM_API_KEY`, `QDRANT_API_KEY`, `QDRANT_LOG_LEVEL`, `REDIS_PASSWORD`, `REDIS_HOST`, `REDIS_PORT`, `TEI_API_KEY`, `LITELLM_MASTER_KEY`, `LITELLM_SALT_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. `DATABASE_URL` is composed inside `compose.yaml` from the Postgres variables and the in-network host `postgres`. No value from any of these belongs in git or in this document.

**Auth that exists today.** LiteLLM expects `LITELLM_MASTER_KEY`. `disable_env_credential_login` is true. vLLM and TEI keys are the env vars above. TEI takes its key as a Compose-interpolated `--api-key` argument, so the value is visible to `docker inspect` and to the container process list. vLLM takes `VLLM_API_KEY` as an environment variable. Qdrant takes `QDRANT__SERVICE__API_KEY`. The unbuilt ingest job and NestJS API will have to present the Qdrant and LiteLLM credentials. This design does not invent a new auth scheme or a header name for them.

**What the current LiteLLM file logs.** `turn_off_message_logging` is false. `disable_spend_logs` is false. `store_prompts_in_spend_logs` is true. `disable_requester_ip_address_logging` is false. `redact_user_api_key_info` is false. Study questions sent to `chat` or `embed` can be stored in Postgres, and key material can show up in logs. `allow_dynamic_callback_disabling` is false, so a request cannot turn callbacks off. This design does not propose editing those flags. The mitigation that exists today is the laptop boundary: loopback binds, a gitignored `.env`, and volumes that stay on that machine. vLLM log files rotate at 10m with 3 files. Other services do not set rotation in Compose.

**Egress.** `internal-net` is a bridge. It does not block model download. `HF_TOKEN` is optional in `.env.example`. Weights are fetched from Hugging Face into `hf-cache` on first start.

**Unbuilt API.** `POST /ask` has no port and no auth design in this document. It must not be described as already bound or already authenticated. The citation requirement (source, license, exact page) is a product requirement on the answer, not a security control.

**Data leaving the machine.** The corpora are public upstream docs. The running stack does not phone a hosted LLM. Generation stays on vLLM and embeddings stay on TEI, both reached through LiteLLM inside `internal-net`.

## Observability

There is no metrics stack and no alerting stack. Prometheus here is a corpus (`prometheus/docs`, `prometheus/prometheus`), not a scraper. Observability is the Compose healthchecks as written, plus Docker logs.

| Service | Check | Interval | Timeout | Retries | Start period |
|---|---|---|---|---|---|
| vllm | Python `urlopen` of `http://127.0.0.1:8000/health` | 30s | 10s | 3 | 120s |
| qdrant | bash `/dev/tcp` `GET /readyz` on `127.0.0.1:6333`, expect `HTTP/1.1 200` | 10s | 5s | 5 | 10s |
| tei | bash `/dev/tcp` `GET /health` on `127.0.0.1:80`, expect `HTTP/1.1 200` | 10s | 5s | 5 | 90s |
| redis | `redis-cli ping` (`REDISCLI_AUTH` from `REDIS_PASSWORD`) | 10s | 5s | 3 | 10s |
| postgres | `pg_isready -U ${POSTGRES_USER}` | 10s | 5s | 3 | 10s |
| litellm | Python `urlopen` of `http://127.0.0.1:4000/health/liveliness` | 10s | 5s | 3 | 10s |

The LiteLLM path is spelled `liveliness` in `compose.yaml`. That spelling is the check. Do not "correct" it in this design.

Logs: only `vllm` sets `json-file` with `max-size` 10m and `max-file` 3. The other services use the Docker daemon's default logging. `QDRANT_LOG_LEVEL` is passed through; the example placeholder is `INFO`.

The only performance number: a chat through the LiteLLM proxy measured about 63 completion tokens per second. There is no latency SLO, no QPS target, no embedding rate, and no alert threshold. `max-num-seqs` 4 is a concurrency cap, not a measured load.

## Rollout Plan

The six services are already the Compose project. Rollout of this design is not a new cluster and not a feature flag. Nothing in the repo defines a flag, and this design does not add one.

**Startup today.** `postgres` and `redis` must pass their healthchecks before `litellm` starts. `vllm` and `tei` start in parallel and are not dependencies of `litellm`. vLLM's healthcheck waits a 120s start period. TEI waits 90s. A cold start also downloads weights across the bridge into `hf-cache`. The AWQ weights are near 2.5 GB by the README figure. That download can outlast the 120s start period. The healthcheck then uses its retries. No `restart` policy is set, so an unhealthy container is not restarted by Compose. The operator looks at `docker compose ps` and the service logs.

**Operator start.** The documented commands, which the README pull request below must state, are `cp .env.example .env` then `docker compose up -d`. `.env.example` is placeholders only. `REDIS_HOST` and `REDIS_PORT` are empty there. This design does not supply values. The copied file is where the operator sets those variables. It is not committed.

**Staged code, after this draft.** Ingest lands before the API so `/ask` is not the first client of an empty Qdrant. The API lands before the static page that calls it. None of those pull requests edit `compose.yaml`, `config/litellm.yaml`, or `.env`.

**Rollback.** `docker compose down` stops the six containers and leaves `hf-cache`, `qdrant-data`, `redis-data`, and `postgres-data` in place. Bringing the stack back is `docker compose up -d` on the pinned images. Unbuilt work rolls back by reverting its git change. There is no traffic shift. Image pins mean a container change is a git change of `compose.yaml`, and this plan does not make that change.

**Failure domain.** If `vllm` is down, `chat` fails and `embed` can still work. If `tei` is down, `embed` fails and `chat` can still work. If `redis` or `postgres` is down, `litellm` does not start, so both names are unavailable even when vLLM and TEI are healthy. If Qdrant is down, the running proxy is unaffected, and the future ingest and `/ask` paths fail.

## Risks

| Risk | Severity | Mitigation |
|---|---|---|
| The 8 GB card is already capped at 6.4 GB for vLLM, with context 4096, 4 sequences, and thinking off. A 7B, an FP16 4B, a second GPU service, a longer context, more sequences, or thinking mode blows that budget. | High | Do not add them. TEI stays on the CPU image. The flags in `compose.yaml` stay as they are. |
| `litellm` does not wait for `vllm` or `tei`. Early `chat` or `embed` calls fail while weights load. vLLM start period is 120s, TEI is 90s, and a cold download can take longer. No restart policy is configured. | Medium | Operator waits on the healthchecks. Not fixed by a Compose edit in this plan. |
| `store_model_in_db` is true while the supported names are the yaml mounted read-only at `/app/config.yaml`. An admin-UI edit can diverge from `chat` and `embed`. | Medium | Project rule: the definitions stay in `config/litellm.yaml`. Callers use those two names. This design does not change the flag. |
| Message logging and spend logs are on, prompts are stored, requester IP logging is not disabled, and user API key info is not redacted. Questions and possibly key material land in Postgres and in container logs. | Medium | Single-operator laptop, `127.0.0.1` binds, gitignored `.env`. No yaml change is proposed here. vLLM logs rotate at 10m times 3 files. |
| `REDIS_HOST` and `REDIS_PORT` are passed through and are empty in `.env.example`. The cache block does not contain a host. The in-network DNS name `redis` is not automatically the operator's `REDIS_HOST`. | Medium | The operator sets the variables in `.env`. This design does not invent the values. |
| `LICENSE` still names `Qwen2.5-7B-Instruct-AWQ`. A reader can think that model is served. | Low | A separate docs-only LICENSE pull request may correct the sentence. It must not add a 7B service. The README already names `Qwen/Qwen3-4B-AWQ`. |
| No Qdrant collection exists. Until ingest runs, there is nothing to search and nothing to cite. | Low | Pull-request order is ingest, then NestJS, then the static page. |
| TEI's API key is a command argument interpolated by Compose. | Low | Accepted for this laptop. The value stays in `.env`. This plan does not edit `compose.yaml` to move it. |
| Hermes is on, and no MCP server exists. Leaving the parser enabled does not by itself expose tools. | Low | Do not design or ship the MCP server in this work. |

## Key Decisions

- **One GPU process.** vLLM serves `Qwen/Qwen3-4B-AWQ` at revision `74d4bd2bd4bff9cafc9345221320bffb08b406a3`. AWQ, Apache 2.0, about 2.5 GB weights, 0.80 utilization (6.4 GB cap), context 4096, 4 sequences, thinking off. Ollama, a 7B, and an FP16 4B are rejected.
- **Embeddings on CPU.** TEI `cpu-1.9` serves `BAAI/bge-small-en-v1.5` at revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`, MIT, 384 dimensions, because the GPU is taken.
- **Qdrant for the index, Postgres 18 for LiteLLM admin data.** Separate volume `qdrant-data`. REST published on `127.0.0.1:6333`. gRPC port 6334 is not published and is not described as disabled inside the container. No collection yet. Postgres host port is 15432 because Windows reserved 5432. In-network port is 5432.
- **Redis exact-match cache only.** `cache: true`, `type: redis`. Not semantic. Host publish `127.0.0.1:6379`. Service DNS name on `internal-net` is `redis`. `REDIS_HOST` and `REDIS_PORT` are environment pass-throughs and are empty in `.env.example`.
- **LiteLLM v1.108.1 is the only client entry.** Names `chat` and `embed` are declared in `config/litellm.yaml`, mounted read-only at `/app/config.yaml`. `store_model_in_db` is true. Both are stated. The flag is not changed. The proxy waits on healthy Postgres and Redis and does not wait on vLLM or TEI.
- **Network `internal-net` is a bridge.** It is not `internal: true` and does not block egress. All published ports are `127.0.0.1` only.
- **Citations are the product goal and are not implemented.** Ingest, NestJS `POST /ask` and `GET /health`, and the static UI are not built and have no ports. Metadata to store later: source, license, exact page link. A second ingest run must not duplicate. Hermes stays enabled for a later MCP server that this design does not specify.
- **Observability stays at healthchecks and Docker logs.** No scraper is added. The only measured rate is about 63 completion tokens per second for a chat through the LiteLLM proxy.

## Open Questions

No open questions remain. Model, cache, GPU placement, and ports are settled by `compose.yaml` and `config/litellm.yaml`. This design does not reopen them. Chunk size and the unpublished NestJS port are unspecified because that work is not built. They are not questions to settle in this draft.

## References

- Repository: https://github.com/shing3tsu/docsage
- `compose.yaml` (project `docsage`, network `internal-net`)
- `config/litellm.yaml` (names `chat` and `embed`, `store_model_in_db: true`)
- `README.md` (product goal, source table, unbuilt ingest / API / UI; Status section is stale)
- `LICENSE` (MIT, copyright 2026 Sina Ghaffari; stale `Qwen2.5-7B-Instruct-AWQ` sentence)
- `.env.example` (placeholder names only; `REDIS_HOST` and `REDIS_PORT` empty; `HF_TOKEN` optional)
- `.gitignore` (ignores `.env*` except `.env.example`)
- Kubernetes docs: https://kubernetes.io/docs/ , https://github.com/kubernetes/website , `content/en/docs` , CC BY 4.0
- Docker docs: https://docs.docker.com/ , https://github.com/docker/docs , `content/` , Apache 2.0
- Prometheus docs: https://prometheus.io/docs/ , https://github.com/prometheus/docs (`content/docs`) and https://github.com/prometheus/prometheus (`docs/`) , Apache 2.0
- Apache 2.0: https://www.apache.org/licenses/LICENSE-2.0
- CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- bge-small-en-v1.5: https://huggingface.co/BAAI/bge-small-en-v1.5
- Git subjects used only as rationale, not as the current model list: `c8ffc4f` (pinned 3B so the 8 GB GPU had KV-cache room), `49b7951` (Qwen3-4B-AWQ for Apache 2.0), `ffa026f` (CPU TEI), `594d2ae` (Qdrant on a named volume), `cbedace` (Redis for the LiteLLM cache), `28e14c3` (LiteLLM with Postgres and an exact Redis cache), `1ad64a4` (network renamed to `internal-net`)

## PR Plan

No pull request in this plan edits `compose.yaml`, `config/litellm.yaml`, or `.env`. None of them adds Lens, a semantic cache, a 7B model, a second GPU service, or an MCP server.

1. **README only.** This is the step immediately after this draft. Docs only. Update the architecture section so it matches the diagrams in this design: the running six-service Compose topology is separate from the not-built ingest path and the not-built ask path. Status text must stop saying that Compose is still future work. Ingest, the NestJS API, and the static UI stay described as not built. Run instructions are `cp .env.example .env` then `docker compose up -d`. Do not print secret values. Do not change the served model, the ports, or the network name.

2. **Ingest job (not built now).** Shallow-clone each docs repo at a pinned tag or commit, clean Markdown, split each page into chunks by heading, embed through LiteLLM `embed`, and store 384-dimensional vectors plus source, license, and exact page link in Qdrant. The collection is created by this job and is not named in this design. A second run does not create duplicates. Filter by source remains possible. Do not edit Compose, the LiteLLM config, or `.env`. Do not add a GPU embedder.

3. **NestJS `POST /ask` and `GET /health` (not built now).** `/ask` embeds the question with `embed`, searches Qdrant, and calls `chat` so the model answers only from those chunks. The response includes the source, its license, and a link to the exact page. No port is assigned. Do not edit Compose or the LiteLLM config.

4. **Static chat UI (not built now).** A static page that calls `/ask` and shows the answer and its sources. No port is assigned. Do not edit Compose.

A docs-only correction of the stale `Qwen2.5-7B-Instruct-AWQ` sentence in `LICENSE` is allowed as its own small pull request. It can land independently of the four steps above. It replaces that stale name with the model that actually runs, `Qwen/Qwen3-4B-AWQ`, and it does not add a 7B service, a Compose change, or any other code.
