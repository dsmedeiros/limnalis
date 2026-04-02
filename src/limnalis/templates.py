"""Authoring templates for Limnalis bundles, plugin packs, and conformance cases.

Each function returns a string scaffold ready for writing to a file.
Templates use triple-quoted strings with no file I/O for loading.
"""

from __future__ import annotations


def bundle_template(name: str) -> str:
    """Return a .lmn bundle scaffold with *name* substituted."""
    return (
        f"bundle {name} {{\n"
        f"  frame @{name}:default::standard;\n"
        f"\n"
        f"  evaluator eval_default {{\n"
        f"    kind model;\n"
        f"    binding {name}://eval/default;\n"
        f"  }}\n"
        f"\n"
        f"  local {{\n"
        f"    c1: p;\n"
        f"  }}\n"
        f"}}\n"
    )


def plugin_pack_template(name: str) -> str:
    """Return a Python plugin-pack module scaffold with *name* substituted."""
    return (
        f'"""Plugin pack: {name}."""\n'
        f"from __future__ import annotations\n"
        f"\n"
        f"from typing import Any\n"
        f"\n"
        f"\n"
        f"def {name}_handler(\n"
        f"    expr: Any, claim: Any, step_ctx: Any, machine_state: Any\n"
        f") -> Any:\n"
        f'    """Evaluate claims for the {name} plugin pack."""\n'
        f"    # TODO: Implement evaluation logic\n"
        f"    from limnalis.api.results import TruthCore\n"
        f"\n"
        f"    return TruthCore(\n"
        f'        truth="T",\n'
        f'        reason="placeholder",\n'
        f"        confidence=1.0,\n"
        f'        provenance=["{name}"],\n'
        f"    )\n"
        f"\n"
        f"\n"
        f"def register_{name}_plugins(registry: Any) -> None:\n"
        f'    """Register {name} plugin bindings."""\n'
        f"    registry.register(\n"
        f'        "evaluator_binding",\n'
        f'        "{name}://eval/default",\n'
        f"        {name}_handler,\n"
        f"    )\n"
    )


def conformance_case_template(case_id: str) -> str:
    """Return a JSON conformance-case fixture scaffold."""
    import json

    case = {
        "id": case_id,
        "name": f"{case_id} test case",
        "source": f"bundle {case_id}_bundle {{ frame @{case_id}:default::nominal; "
        f"evaluator ev0 {{ kind model; binding test://eval/default; }}; "
        f"local {{ c1: p; }} }}",
        "expected": {
            "sessions": [
                {
                    "session_id": "default",
                    "steps": [{"step_id": "step0"}],
                }
            ]
        },
    }
    return json.dumps(case, indent=2) + "\n"
