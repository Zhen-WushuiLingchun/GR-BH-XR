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

### Year Convention

`YYYY` in the file name is the **preprint/arXiv year** of the stored PDF. The
BibTeX `year` field is the **journal publication year**, which may differ by one
year (for example `2016-bhac-...` for arXiv 2016 with journal year 2017, and
`2012-koral-...` for arXiv 2012 with journal year 2013). This is intentional and
not an inconsistency: the file name tracks the document that was downloaded,
while the citation tracks the published version.

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

## Temporary Review Cache

Literature downloaded only for equation extraction, license inspection, or a
bounded source review may instead remain under ignored `outputs/`. For example,
the 2026-08-10 BBH review cache is under `outputs/bbh_literature/`. Such files
are not project sources and must not be required for tests or builds. Their
stable locators, reviewed revisions, checksums when relevant, and conclusions
must still be recorded in `references/references.md`, a source note, or a code
review before the cache is used to justify implementation.
