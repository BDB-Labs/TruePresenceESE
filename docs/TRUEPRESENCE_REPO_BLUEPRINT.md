# TruePresence Repo Blueprint

Target repository structure:

```text
repo/
├── truepresence/
│   ├── api/
│   ├── surfaces/
│   │   ├── telegram/
│   │   └── web_guard/
│   ├── evidence/
│   ├── decision/
│   ├── ensemble/
│   ├── memory/
│   ├── identity/
│   ├── challenges/
│   ├── runtime/
│   └── artifacts/
├── ese/
├── docs/
└── tests/
```

Clarifications:

- `truepresence/` is the product application.
- `ese/` is generic orchestration substrate code.
- The product should not be cognitively overshadowed by the substrate.

Practical boundary rules:

- Product contracts, evidence normalization, argument graphs, decision logic, artifacts, and enforcement mappings belong in `truepresence/`.
- Generic role execution infrastructure, provider/model plumbing, and reusable orchestration mechanics belong in `ese/`.
- If moving old modules is risky, V1 should use compatibility shims so contributors can follow the clearer product-oriented layout without breaking existing imports.
