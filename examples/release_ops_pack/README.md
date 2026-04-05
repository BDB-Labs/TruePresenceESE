# Release Operations

Example external ESE pack that lives outside the `ese` core package.

## Development

```bash
pip install -e .
ese pack validate .
ese pack test .
```

After installation, `ese packs` will discover this project through the `ese.config_packs` entry point group.
