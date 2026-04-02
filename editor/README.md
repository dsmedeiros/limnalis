# Limnalis Editor Support

VS Code extension providing syntax highlighting and snippets for Limnalis surface syntax (`.lmn` files).

## Installation

### Option A: Symlink (development)

Create a symlink from this directory into your VS Code extensions folder:

```bash
# Linux / macOS
ln -s "$(pwd)/editor/vscode" ~/.vscode/extensions/limnalis-language

# Windows (PowerShell, run as admin)
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.vscode\extensions\limnalis-language" -Target "editor\vscode"
```

### Option B: Copy

Copy the `editor/vscode` directory into `~/.vscode/extensions/limnalis-language`, then reload VS Code.

## What's Supported

### Syntax Highlighting

- **Keywords**: `bundle`, `frame`, `evaluator`, `baseline`, `anchor`, `fictional_anchor`, `bridge`, `local`, `systemic`, `meta`, `evidence`, `evidence_relation`, `resolution_policy`, `joint_adequacy`, `session`, `step`, `judged_by`, `transport`, `claims`
- **Operators**: `AND`, `OR`, `IMPLIES`, `IFF`, `=>`, `declare`, `as`, `within`
- **Type names**: `idealization`, `placeholder`, `proxy`, `aggregate`, `point`, `set`, `manifold`, `moving`, `fixed`, `on_reference`, `tracked`, `single`, `paraconsistent_union`, `priority_order`, `adjudicated`, `primary`, `adversarial`, `audit`, `auxiliary`
- **Strings**: double-quoted strings with escape sequences
- **Comments**: `#` line comments and `//` line comments
- **Inline patterns**: `@{...}` frame patterns
- **Inline lists**: `[...]` list expressions
- **Punctuation**: block braces `{}`, statement terminators `;`
- **Identifiers**: ATOM tokens highlighted as variables

### Snippets

| Prefix         | Description                              |
|----------------|------------------------------------------|
| `bundle`       | Full bundle scaffold with frame and claims |
| `evaluator`    | Evaluator block with kind and binding     |
| `claims-local` | Local claim block with one claim          |
| `bridge`       | Bridge block with from/to frames          |
| `anchor`       | Anchor with adequacy assessment           |
| `frame`        | Frame shorthand statement                 |

### Comment Toggling

Press `Ctrl+/` (or `Cmd+/` on macOS) to toggle `#` line comments. Both `#` and `//` comment styles are syntax-highlighted, but the comment toggle shortcut uses `#` (VS Code only supports a single line comment style for toggling).

### Auto-closing Pairs

Brackets `{}`, `[]`, `()` and double quotes are auto-closed.

## What Highlighting Looks Like

When the extension is active, a `.lmn` file will show:
- **Purple/blue** for control keywords (`bundle`, `evaluator`, `anchor`, etc.)
- **Operator color** for logical connectives (`AND`, `OR`, `IMPLIES`)
- **Type color** for subtype and kind values (`idealization`, `proxy`, `adjudicated`)
- **Green** for strings
- **Gray** for comments
- Standard variable coloring for identifiers

Exact colors depend on your VS Code color theme.

## Roadmap

- **Tree-sitter grammar**: A Tree-sitter grammar for more precise incremental parsing and code folding
- **Language Server Protocol (LSP)**: Diagnostics, go-to-definition, hover info, and completion powered by the Limnalis parser and normalizer
- **Semantic highlighting**: Token-level semantic tokens for richer theme support
