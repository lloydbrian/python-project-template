# ADR 0012: Optional AI stack, and Python versions that follow it

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-11-24 |
| **Decided by** | LBD |

## Context
Future AI projects need retrieval: a vector store, embeddings, PDF text extraction and web search. The packages first proposed were `chromadb`, `pydantic`, `python-dotenv`, `tavily-python` and `pdfplumber`. Checked on 2026-11-24:

- `pydantic` and `python-dotenv` are already template dependencies, with newer floors. The proposed `python-dotenv>=1.1.0` floor allowed a version with a published advisory (fixed in 1.2.2).
- `chromadb` 1.5.9 (latest) always installs `onnxruntime` for its built-in embedder, and onnxruntime 1.32.0 ships wheels for Python 3.11–3.14 only, with no source package. ChromaDB therefore cannot install on Python 3.15, the template default.
- `chromadb` has four advisories with no fixed release. All affect the ChromaDB **server** (code injection through model repositories, and tenant authorization), not the embedded client.
- `pdfplumber` and `tavily-python` are clean and install everywhere.

## Decision
- A Copier question `ai_stack` (service and notebooks; default `none`) offers:
  - **`lancedb`**: LanceDB + sentence-transformers (all-MiniLM-L6-v2, CPU). Embedded and disk-based, no advisories, and installs from wheels on every offered Python, including 3.15.
  - **`chromadb`**: ChromaDB with its built-in embedder. It has the simplest API, but supports **Python 3.14 or older**.
- `ai_stack` is asked **before** `python_version`. With `chromadb`, the Python default becomes 3.14, and 3.15 is a disabled choice that states the reason (and is refused with `--data`).
- Both stacks add `pdfplumber` and `tavily-python`, and the same `rag.DocumentStore` interface (`add`, `search`, `count`), so changing stores touches one file.
- Both use the **same embedding model**, so search behaviour stays comparable across a switch. The model is baked into container images at build time (`HF_HUB_OFFLINE=1`), so containers never download it.
- `data/` is git-ignored whenever an AI stack is chosen, and the service's read-only container gets a `vectors` volume for the store. `mise run image` embeds and searches inside the image with `--network=none` to prove the model was baked in.
- ChromaDB projects ship `.pip-audit-ignore`, one line per server-only advisory with a reason, an owner and `expires: on-bootstrap`. `mise run bootstrap` dates each line to today + 90 days. The audit then ignores only those IDs, and fails once they expire (ADR 0006 rules). The exceptions are valid only while the project uses the embedded client, opens only stores it created, and installs no Hugging Face embedding function: the advisories' code-injection path is an embedding function named in a store's saved configuration. ChromaDB telemetry is turned off.

## Alternatives considered
- *ChromaDB for everyone*: impossible on 3.15, and it fails the audit gate without exceptions.
- *Qdrant client*: clean and installs on 3.15, with a path to a server later; it is a reasonable future option, but LanceDB is closer to Chroma's embedded model.
- *fastembed*: also requires onnxruntime, so it has no 3.15 support.
- *model2vec*: tiny and fast with no torch, but lower quality and not in LanceDB's registry.
- *API embeddings (OpenAI/Voyage)*: smallest install, but they need a key, network access and per-token cost, and text leaves the machine. They remain one registry line away.
- *PyMuPDF* for PDFs: AGPL licence. *Docling*: no 3.15 wheels.
- *Optional extras instead of a question*: services install no extras in images, and extras would not be audited or tested.

## Consequences
- The template CI matrix adds `service-ai-lancedb` (3.15) and `notebooks-ai-chromadb` (3.14). Negative controls cover the 3.15 guard and undated exceptions.
- LanceDB projects carry PyTorch (about 140 MB macOS / 540 MB Linux wheel), so their images are large.
- When onnxruntime publishes 3.15 wheels, a template release removes the `python_version` validator, and ChromaDB projects can run `copier update --data python_version=3.15`. When chromadb fixes the advisories, the release removes `.pip-audit-ignore` entries.
