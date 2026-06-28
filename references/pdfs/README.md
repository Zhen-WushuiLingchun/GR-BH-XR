# PDF Originals

Store original literature PDFs here when they are legally redistributable,
open-access, or otherwise safe to keep in the repository.

## Naming

Use stable, searchable names:

```text
YYYY-short-citation-key-main-topic.pdf
```

Examples:

```text
2018-raptor-i-time-dependent-grrt.pdf
2022-aart-kerr-photon-rings.pdf
```

## Index Requirement

Every PDF kept here must be indexed in `references/references.md` with:

- `PDF path`;
- stable locator such as DOI, arXiv ID, or URL;
- short summary;
- project use;
- limitations or open questions.

## Local-Only PDFs

Use `references/pdfs/local_only/` for files that should be available on this
machine but should not be pushed, such as restricted-access PDFs, very large
documents, or temporary downloads. That directory is ignored by Git.

For local-only files, still add a `references/references.md` entry with the
stable locator and mark the PDF path as local-only.
