# AI and model development

The optional `ai-dev` profile prepares an Apple Silicon Mac for local model
experiments. Use Rust for custom models and training code; keep each project's
frameworks, datasets, weights, and experiment records in that project, not in
Orbit. This is workstation tooling, not a trained model or an inference service.

## Select the profile

From the Orbit checkout:

```sh
./scripts/orbit plan --profile ai-dev
./scripts/apply --profile ai-dev
./scripts/doctor
```

The first command is read-only. `apply` installs the base and selected profile
packages, runtimes, and managed configuration. Existing selections are retained.
It does not run the full setup service/startup phases. To run full workstation
provisioning instead, use `./setup --profile ai-dev` and review its broader effects.

`ai-dev` is opt-in. An explicit `--profile all` also includes it. Listing or
planning the profile does not select it or establish that its tools work.
Per-machine selections remain in ignored `.state/profiles.txt`.

## What it adds

| Tool | Purpose |
| --- | --- |
| `duckdb` | Inspect and query local CSV, JSON, and Parquet training data. |
| `hf` | Explicit model/dataset artifact retrieval and cache management through the Hugging Face CLI. |
| `hyperfine` | Benchmark repeatable training, preprocessing, and inference commands. |

Orbit's base already provides stable Rust through rustup, uv-managed Python,
CMake, Ninja, pkgconf, Git LFS, and general build/editor tools. They are not
reinstalled under a second owner. Homebrew may install its own Python dependency
for `hf`; that is CLI support, not the project's Python environment.

The profile adds no third-party Homebrew taps, global training libraries, model
weights, provider credentials, background services, automatic uploads, GPU driver
installers, or license acceptance. Homebrew packages remain rolling components,
not a frozen experiment environment. Inspect upstream installation behavior
before applying updates.

## Rust-first model development

**Start with Burn for new trainable models.** It provides tensors,
autodifferentiation, neural-network modules, optimizers, training facilities,
and CPU/GPU backends. Begin with a small classifier, regressor, or action scorer
and an explicit baseline before attempting language-model pretraining.

Use the existing Rust starter; no new project-specific installer is needed:

```sh
mkdir -p ~/src
orbit new rust model-lab ~/src --git
cd ~/src/model-lab
cargo add burn --features train,wgpu
cargo check --locked
```

These commands explicitly create a project and resolve/download Cargo packages.
They do not train a model, fetch a dataset, or prove GPU readiness. Review and
commit the resulting `Cargo.toml` and `Cargo.lock` together. `cargo add` selects
an available release at invocation time; record that release and use its matching
documentation, not examples from an incompatible development branch. For stronger
reproducibility, pin the project's Rust toolchain and record the SDK/macOS version.

Follow the [Burn training workflow](https://burn.dev/books/burn/basic-workflow/)
for model, data, training, and inference code. Burn's
[backend documentation](https://github.com/tracel-ai/burn#backend) describes
Apple GPU support through Metal/WebGPU. Use a supported CPU backend as the
correctness baseline and qualify the chosen GPU backend on the actual Mac.
Record the device/backend used and fail clearly on unavailable hardware rather
than silently comparing a CPU fallback with a GPU result. Some native backend
paths require additional Xcode/Metal toolchain components; Orbit neither installs
full Xcode nor accepts its license. Run Apple GPU experiments natively rather
than assuming a Linux container can use Metal.

Burn is the recommended starting point, not a global dependency installed by
Orbit. Add only the libraries the experiment needs:

- [Candle](https://github.com/huggingface/candle) for lightweight tensor/model
  work or an existing pretrained architecture it supports. Check the specific
  architecture, operations, training path, and backend before choosing it.
- [Hugging Face Tokenizers](https://github.com/huggingface/tokenizers) for text
  tokenization and [Safetensors](https://github.com/huggingface/safetensors) for
  tensor-weight interchange when the project needs them.

For established LLM adapter workflows on Apple Silicon,
[MLX LM](https://github.com/ml-explore/mlx-lm) is an optional Python route.
Keep it in a separate project-owned uv environment with a committed `uv.lock`.
Do not install PyTorch, MLX, notebooks, or multiple competing model servers
machine-wide merely to enable this profile. A Rust-first project can still use
Python for a specific experiment or comparison.

## Declare the project requirement

A project may include this `.orbit.json` at its root:

```json
{"version":1,"profiles":["ai-dev"]}
```

Merge this requirement with an existing declaration rather than replacing its
other profiles or service requirements. `orbit enter` and `orbit map --needs`
can then report an unselected profile. They do not inspect training results or
prove that the selected profile's packages are installed.

## Data, artifacts, and experiment discipline

Keep raw/private data and large generated files out of the source repository.
A project can add these paths to its own `.gitignore`:

```gitignore
/data/raw/
/artifacts/
/checkpoints/
/runs/
.env
```

Keep small, non-sensitive dataset manifests, split definitions, and experiment
configurations tracked. Model downloads and authentication are separate actions;
Orbit never runs `hf auth login`, accepts model terms, or uploads results. Pin
retrieved repositories to immutable revisions, record artifact hashes and license
terms, and never put tokens in source, command histories, or public run metadata.
Do not enable execution of remote model/dataset code as a convenience default.

For each run, record the source commit, lockfile and dataset/split digests,
configuration, seed, device/backend, wall time, measured memory when available,
and the result against an independently checkable baseline. A fixed seed alone
does not guarantee identical results across backends or hardware.

Keep training, calibration, and evaluation separate. Where examples share an
origin or task family, hold out that whole group rather than leaking related
examples across splits. Record failures and incomplete runs instead of dropping
them. A loss decrease is a training check, not evidence of general usefulness.

Build before benchmarking, define the exact measured interval, and count
preprocessing, model loading, fallback, and failed attempts where relevant.
`hyperfine` intentionally repeats its command: use only bounded experiments with
isolated output paths and no external effects. GPU measurements must include
completion/synchronization, not just asynchronous command submission.

## Verification boundaries

Orbit's profile tests check opt-in selection, preservation of existing choices,
deduplication, declarative package contents, and dispatch to a stubbed Homebrew
command. They do not install Homebrew packages or run model code.

On the target Mac, after an explicit apply, check `duckdb --version`,
`hf version`, and `hyperfine --version`, then run the selected project's
locked tests and a small bounded CPU training/checkpoint/reload exercise. Qualify
Metal separately against that baseline. Neither repository CI nor `orbit doctor`
by itself establishes numerical correctness, training quality, or GPU capability.

## Upstream references

- [Burn](https://github.com/tracel-ai/burn) and [Burn Book](https://burn.dev/books/burn/)
- [DuckDB CLI](https://duckdb.org/docs/stable/clients/cli/overview.html)
- [Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli)
- [Hyperfine](https://github.com/sharkdp/hyperfine)
- Homebrew formulas: [duckdb](https://formulae.brew.sh/formula/duckdb),
  [hf](https://formulae.brew.sh/formula/hf),
  [hyperfine](https://formulae.brew.sh/formula/hyperfine)
