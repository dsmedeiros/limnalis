# SARIF Export

The `lint` and `analyze` CLI commands can emit their diagnostics as [SARIF 2.1.0](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-schema-2.1.0.json) (Static Analysis Results Interchange Format) JSON, the format consumed by GitHub code scanning, the VS Code SARIF viewer, and most static-analysis dashboards.

## Usage

```bash
limnalis lint examples/minimal_bundle.lmn --format sarif
limnalis analyze examples/minimal_bundle.lmn --format sarif
```

`--format` accepts `plain`, `json`, `grouped` (default), and `sarif` on both commands. Structured formats (`json`, `sarif`) always print a document, even when there are no diagnostics, so downstream tooling never has to special-case empty output. Exit code is `1` if any error-severity diagnostic was produced, `0` otherwise -- independent of the output format.

`lint` runs parse, normalize, and schema validation. `analyze` runs the same checks plus structural analysis of the normalized bundle.

## Output shape

The SARIF log contains a single run whose tool driver is `limnalis` with the installed package version. Example (abridged):

```json
{
  "$schema": "https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-schema-2.1.0.json",
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "limnalis",
          "version": "0.2.2rc1",
          "rules": [
            {
              "id": "resolution_policy_defaulted",
              "shortDescription": { "text": "Synthesized ResolutionPolicy(...) ..." }
            }
          ]
        }
      },
      "results": [
        {
          "ruleId": "resolution_policy_defaulted",
          "level": "note",
          "message": { "text": "Synthesized ResolutionPolicy(...) ..." },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "examples/minimal_bundle.lmn" },
                "region": { "startLine": 1, "startColumn": 1, "endLine": 12, "endColumn": 2 }
              }
            }
          ],
          "properties": { "phase": "normalize", "subject": "minimal_bundle" }
        }
      ]
    }
  ]
}
```

Field mapping:

| SARIF field | Source |
|---|---|
| `ruleId` | The diagnostic `code`; every distinct code also becomes a driver rule with its first message as `shortDescription` |
| `level` | Diagnostic severity: `error` → `error`, `warning` → `warning`, `info` (and anything else) → `note` |
| `message.text` | The diagnostic message |
| `locations[].physicalLocation.artifactLocation.uri` | The linted source path (present when the CLI knows the file) |
| `locations[].physicalLocation.region` | The diagnostic's source span (start/end line and column), when the diagnostic carries one |
| `properties.phase`, `properties.subject` | The diagnostic's pipeline phase and subject id, when present |

Output is deterministic: results are sorted by (`ruleId`, message) and rules by id, so identical input yields byte-identical SARIF -- suitable for snapshot testing and diff-based review.

## CI example (GitHub code scanning)

```yaml
- name: Lint Limnalis bundles
  run: |
    PYTHONPATH=src python -m limnalis lint bundles/my_bundle.lmn --format sarif > limnalis.sarif

- name: Upload SARIF
  uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: limnalis.sarif
```

## Notes

- The SARIF builder is internal (`limnalis.sarif` is not part of the stable `limnalis.api.*` surface); the supported way to obtain SARIF output is the CLI.
- One source file per invocation: each CLI run produces one SARIF log for one `.lmn` file. Merge logs downstream if you lint many files.

## Further reading

- [Getting Started](getting_started.md) -- CLI walkthrough
- [Architecture](architecture.md) -- where `lint`/`analyze` sit in the CLI package
