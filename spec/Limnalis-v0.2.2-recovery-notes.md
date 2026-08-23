# Limnalis v0.2.2 recovery notes

## Status

The original `Limnalis-v0.2.2.pdf` binary and the original `limnalis_v0.2.2.md` file were not present in the active working directory when recovery began. The reconstruction is therefore not byte-identical.

## Sources used

- surviving `Limnalis-v0.2.pdf`
- surviving `Limnalis-v0.2.1.pdf`
- rendered pages from the missing v0.2.2 PDF (including contents and representative sections)
- `Limnalis_conformance_matrix_v0_2_2.xlsx`
- `limnalis_conformance_matrix_v0.2.2.md`
- `limnalis_fixture_corpus_v0.2.2.json` and `.yaml`
- v0.2.2 AST, result, and fixture schemas
- settled AST pressure-point note
- specification text and patches preserved in the project conversation, including session semantics, notation-layer responsibilities, diagnostic registry, and abstract-machine refactor

## Confidence

- Core semantic design: high
- Kernel and evaluation structures: high
- Grammar and AST: high
- Corpus case coverage: high
- Exact original prose, section pagination, and typography: medium/low

## Recommended repository treatment

Store the reconstructed files with an explicit recovery commit and retain this note. If an original copy resurfaces later, diff it against the reconstruction rather than replacing it silently.
