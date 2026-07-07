# Dependencies License Audit — Micelia v0.1

**Date**: 2026-05-24
**Purpose**: verify that every runtime and dev dependency is license-compatible with AGPL-3.0-or-later (core orchestrator), Apache-2.0 (Python SDK), and FSL-1.1-ALv2 (new modules).
**Outcome**: all current dependencies are permissive (MIT / BSD / Apache 2.0) → fully compatible.

---

## 1. Methodology

For each dependency declared in `pyproject.toml` and `sdk/python/pyproject.toml`, we record:
- Upstream license (verified against PyPI metadata at the version pin)
- Compatibility with AGPLv3 as combined work
- Compatibility with Apache 2.0 as combined work
- Any specific concern (patent clauses, export restrictions, ethical clauses)

Permissive licenses (MIT, BSD-2, BSD-3, Apache 2.0, ISC) are universally compatible with AGPLv3 — they impose no copyleft and add only attribution requirements that AGPLv3 already satisfies.

Copyleft licenses (GPLv2, GPLv3, LGPL, AGPLv3) require careful review: only certain combinations work.

Source-available licenses (BSL, SSPL, ELv2, BUSL) are incompatible with both AGPL and Apache. None present in current deps.

---

## 2. Core orchestrator (`pyproject.toml`)

### 2.1 Runtime dependencies

| Package | License | AGPLv3 compat | Notes |
|---|---|---|---|
| fastapi >=0.109.0 | MIT | ✓ | Permissive |
| uvicorn[standard] >=0.27.0 | BSD-3-Clause | ✓ | Permissive |
| httpx >=0.26.0 | BSD-3-Clause | ✓ | Permissive |
| aiohttp >=3.9.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| websockets >=12.0 | BSD-3-Clause | ✓ | Permissive |
| sqlalchemy[asyncio] >=2.0.0 | MIT | ✓ | Permissive |
| asyncpg >=0.29.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| alembic >=1.13.0 | MIT | ✓ | Permissive |
| redis >=5.0.0 | MIT | ✓ | redis-py client, not the server |
| lancedb >=0.4.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| pydantic >=2.5.0 | MIT | ✓ | Permissive |
| pydantic-settings >=2.1.0 | MIT | ✓ | Permissive |
| python-dotenv >=1.0.0 | BSD-3-Clause | ✓ | Permissive |
| torch >=2.1.0 | BSD-style (custom) | ✓ | PyTorch BSD-style license is permissive |
| onnxruntime >=1.16.0 | MIT | ✓ | Permissive |
| loguru >=0.7.0 | MIT | ✓ | Permissive |
| click >=8.1.0 | BSD-3-Clause | ✓ | Permissive |
| rich >=13.7.0 | MIT | ✓ | Permissive |
| psutil >=5.9.0 | BSD-3-Clause | ✓ | Permissive |
| prometheus-client >=0.19.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| python-jose[cryptography] >=3.3.0 | MIT | ✓ | Permissive |
| passlib[bcrypt] >=1.7.4 | BSD-2-Clause | ✓ | Permissive |
| pyngrok >=7.0.0 | MIT | ✓ | Permissive |
| google-auth >=2.25.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| google-auth-oauthlib >=1.2.0 | Apache-2.0 | ✓ | Permissive + patent grant |
| google-api-python-client >=2.100.0 | Apache-2.0 | ✓ | Permissive + patent grant |

**Verdict**: all 26 runtime deps are permissive. No conflict with AGPLv3.

### 2.2 Dev dependencies

| Package | License | AGPLv3 compat | Notes |
|---|---|---|---|
| pytest >=7.4.0 | MIT | ✓ | Test-only |
| pytest-asyncio >=0.23.0 | Apache-2.0 | ✓ | Test-only |
| pytest-cov >=4.1.0 | MIT | ✓ | Test-only |
| black >=23.12.0 | MIT | ✓ | Tooling |
| ruff >=0.1.0 | MIT | ✓ | Tooling |
| mypy >=1.8.0 | MIT | ✓ | Tooling |
| respx >=0.20.0 | BSD-3-Clause | ✓ | Test mock for httpx |
| pytest-httpx >=0.30.0 | MIT | ✓ | Test mock |

**Verdict**: 8 dev deps, all permissive. No conflict.

---

## 3. Python SDK (`sdk/python/pyproject.toml`)

| Package | License | Apache-2.0 compat | Notes |
|---|---|---|---|
| httpx >=0.27,<1 | BSD-3-Clause | ✓ | Permissive |
| redis[hiredis] >=5.0,<6 | MIT | ✓ | Permissive |
| pydantic >=2.0,<3 | MIT | ✓ | Permissive |
| pydantic-settings >=2.0,<3 | MIT | ✓ | Permissive |

**Dev deps**: pytest (MIT), pytest-asyncio (Apache 2.0), respx (BSD-3), fakeredis (MIT). All permissive.

**Verdict**: SDK can ship under Apache-2.0 without conflict.

---

## 4. Frontend (`frontend/package.json`)

Not deeply audited in this pass (Node ecosystem is broader). Top-level deps:

| Package | License | AGPLv3 compat |
|---|---|---|
| next ^14.0.0 | MIT | ✓ |
| react ^18.2.0 | MIT | ✓ |
| react-dom ^18.2.0 | MIT | ✓ |
| @tanstack/react-query ^5.0.0 | MIT | ✓ |
| zustand ^4.4.0 | MIT | ✓ |
| lucide-react ^0.292.0 | ISC | ✓ |
| recharts ^2.10.0 | MIT | ✓ |
| date-fns ^2.30.0 | MIT | ✓ |

Tailwind, PostCSS, TypeScript: all MIT/Apache.

**Action item**: when the trademark is registered and the project moves to v0.2, run a full `license-checker` on `node_modules/` to verify the deep tree.

---

## 5. AI model providers (runtime, not deps)

Per `docs/AI_SOVEREIGNTY_POLICY.md`, the core must function with open-weight models. Verified open-weight options:

| Model | License | Open-weight? | Local-runnable? |
|---|---|---|---|
| Llama 3.1 8B | Llama Community License | Yes | Yes (Ollama) |
| Mistral 7B | Apache 2.0 | Yes | Yes (Ollama) |
| Qwen 2.5 7B | Tongyi Qianwen License | Yes | Yes (Ollama) |
| bge-m3 (embeddings) | MIT | Yes | Yes |
| Whisper Large v3 | MIT | Yes | Yes |

Note: the Llama Community License has commercial-use thresholds (>700M MAU) that do not affect Micelia in practice. Mistral and Qwen are fully permissive for our use.

Proprietary models (GPT-4, Claude, Gemini) are accessed via API and do not impose source-code obligations on Micelia. Compatibility with AGPL is preserved.

---

## 6. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Future dep introduces GPL component (incompatible with Apache SDK) | Low | High | PR checklist requires license check on new deps |
| Frontend npm transitive deps include GPL package | Low | Medium | Add `license-checker --failOn 'GPL'` to CI |
| Model provider changes terms retroactively | Medium | Low | Open-weight stack provides fallback; policy enforces graceful degradation |
| Patent troll targets a permissive dep | Low | Medium | Apache 2.0 patent grant in upstream deps provides indirect protection |

---

## 7. Acceptance criteria for new dependencies

A PR introducing a new runtime dependency must:

1. Declare the upstream license in the PR description
2. Verify it appears in this audit's "compatible" set OR justify the addition
3. For copyleft additions: explicit Steward approval required
4. For source-available additions: NOT permitted in core (FSL modules may be reviewed case-by-case)

---

## 8. Next audits

- **2026-Q3**: re-audit triggered by v0.2 milestone (new modules, frontend tree)
- **2027-Q1**: annual review aligned with `docs/AI_SOVEREIGNTY_POLICY.md` §5 cycle
- **Ad-hoc**: any time a contributor proposes adding a non-MIT/BSD/Apache dep
