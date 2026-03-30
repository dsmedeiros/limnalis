"""LinkML projection pipeline for Limnalis canonical Pydantic models.

This module generates LinkML YAML schema artifacts from canonical Pydantic models
by introspecting their JSON Schema representations. The generated artifacts are
PROJECTIONS — derived, approximate views — NOT the canonical source of truth.

The canonical source of truth for all Limnalis types lives in the Pydantic model
layer under ``src/limnalis/models/``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml

from limnalis.interop.types import ProjectionResult

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_SOURCE_MODELS: dict[str, tuple[str, str]] = {
    "ast": (
        "limnalis.models.ast",
        "BundleNode",
    ),
    "evaluation_result": (
        "limnalis.models.conformance",
        "ExpectedResult",
    ),
    "conformance_report": (
        "limnalis.models.conformance",
        "ExpectedResult",
    ),
}

_LINKML_SCHEMA_IDS: dict[str, str] = {
    "ast": "https://limnalis.dev/schema/ast",
    "evaluation_result": "https://limnalis.dev/schema/results",
    "conformance_report": "https://limnalis.dev/schema/results",
}

_LINKML_NAMES: dict[str, str] = {
    "ast": "limnalis_ast",
    "evaluation_result": "limnalis_results",
    "conformance_report": "limnalis_results",
}

_DEFAULT_FILENAMES: dict[str, str] = {
    "ast": "limnalis_ast.linkml.yaml",
    "evaluation_result": "limnalis_results.linkml.yaml",
    "conformance_report": "limnalis_results.linkml.yaml",
}


def project_linkml_schema(
    source_model: Literal["ast", "evaluation_result", "conformance_report"] = "ast",
    *,
    output_path: str | Path | None = None,
) -> ProjectionResult:
    """Generate a LinkML YAML schema artifact from canonical Pydantic models.

    This is a PROJECTION — not the canonical source of truth.
    The generated LinkML schema describes the shape of the canonical models
    for use in documentation, validation, and interop toolchains.

    Returns a :class:`ProjectionResult` with warnings about lossy/unsupported
    mappings.
    """
    import importlib

    mod_path, cls_name = _SOURCE_MODELS[source_model]
    mod = importlib.import_module(mod_path)
    root_cls = getattr(mod, cls_name)

    json_schema = root_cls.model_json_schema()

    converter = _JsonSchemaToLinkML(
        schema_id=_LINKML_SCHEMA_IDS[source_model],
        schema_name=_LINKML_NAMES[source_model],
        source_model_label=source_model,
        root_class_name=cls_name,
        pydantic_module=mod_path,
    )
    linkml_doc = converter.convert(json_schema)

    yaml_text = _render_yaml(linkml_doc)

    result_path: str | None = None
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml_text, encoding="utf-8")
        result_path = str(out)

    return ProjectionResult(
        target_format="linkml",
        source_model=source_model,
        artifact_path=result_path,
        warnings=converter.warnings,
        lossy_fields=converter.lossy_fields,
    )


# ---------------------------------------------------------------------------
# Internal converter
# ---------------------------------------------------------------------------

# JSON Schema type -> LinkML range
_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "integer": "integer",
    "number": "float",
    "boolean": "boolean",
}


class _JsonSchemaToLinkML:
    """Converts a Pydantic-generated JSON Schema (with ``$defs``) to a LinkML
    schema document (as a plain dict ready for YAML serialisation)."""

    def __init__(
        self,
        *,
        schema_id: str,
        schema_name: str,
        source_model_label: str,
        root_class_name: str,
        pydantic_module: str,
    ) -> None:
        self.schema_id = schema_id
        self.schema_name = schema_name
        self.source_model_label = source_model_label
        self.root_class_name = root_class_name
        self.pydantic_module = pydantic_module

        self.warnings: list[str] = []
        self.lossy_fields: list[str] = []
        self._defs: dict[str, Any] = {}
        self._enum_names: set[str] = set()

    # -- public entry point -------------------------------------------------

    def convert(self, json_schema: dict[str, Any]) -> dict[str, Any]:
        self._defs = json_schema.get("$defs", {})

        classes: dict[str, Any] = {}
        enums: dict[str, Any] = {}

        # Discover which $defs are enum-like (string with ``enum`` key)
        for def_name, defn in self._defs.items():
            if self._is_enum_def(defn):
                self._enum_names.add(def_name)

        # Convert definitions
        for def_name, defn in self._defs.items():
            if def_name in self._enum_names:
                enums[def_name] = self._convert_enum(def_name, defn)
            else:
                cls = self._convert_class(def_name, defn)
                if cls is not None:
                    classes[def_name] = cls

        # Build the top-level LinkML document
        doc: dict[str, Any] = {
            "id": self.schema_id,
            "name": self.schema_name,
            "title": f"Limnalis {self.source_model_label.replace('_', ' ').title()} Schema (Projected)",
            "description": (
                f"LinkML projection of the canonical Limnalis Pydantic models "
                f"from {self.pydantic_module}.\n"
                f"This is a DERIVED artifact — the canonical source of truth is the "
                f"Pydantic model layer in {self.pydantic_module.replace('.', '/')}."
            ),
            "prefixes": {
                "linkml": "https://w3id.org/linkml/",
                "limnalis": "https://limnalis.dev/schema/",
            },
            "default_range": "string",
        }

        if classes:
            doc["classes"] = classes
        if enums:
            doc["enums"] = enums

        return doc

    # -- enum handling ------------------------------------------------------

    @staticmethod
    def _is_enum_def(defn: dict[str, Any]) -> bool:
        """Return True when a $def looks like a Literal enum."""
        if defn.get("type") == "string" and "enum" in defn:
            return True
        # Pydantic sometimes wraps Literal in a const or enum at the top level
        return False

    def _convert_enum(self, name: str, defn: dict[str, Any]) -> dict[str, Any]:
        values = defn.get("enum", [])
        permissible: dict[str, dict[str, Any]] = {}
        for v in values:
            permissible[str(v)] = {}
        result: dict[str, Any] = {
            "permissible_values": permissible,
        }
        desc = defn.get("description")
        if desc:
            result["description"] = desc
        return result

    # -- class handling -----------------------------------------------------

    def _convert_class(self, name: str, defn: dict[str, Any]) -> dict[str, Any] | None:
        """Convert a JSON Schema object definition into a LinkML class dict."""
        if defn.get("type") != "object" and "properties" not in defn:
            # Might be a union wrapper or other non-object — skip with warning
            if "anyOf" in defn or "oneOf" in defn:
                self.warnings.append(
                    f"{name}: union type mapped as stub class (LinkML lacks native "
                    f"discriminated unions)"
                )
                self.lossy_fields.append(name)
                # Create a stub noting it's a union
                return {
                    "description": (
                        f"Union type — this is a LOSSY projection. "
                        f"In the canonical Pydantic model this is a discriminated union."
                    ),
                }
            # Other non-object defs (e.g. bare types) — skip
            return None

        props = defn.get("properties", {})
        required_set = set(defn.get("required", []))

        attributes: dict[str, Any] = {}
        for prop_name, prop_schema in props.items():
            attr = self._convert_property(name, prop_name, prop_schema, prop_name in required_set)
            # Use the alias-free name; Pydantic may emit alias names (e.g. ``from`` as a key)
            attributes[prop_name] = attr

        result: dict[str, Any] = {}
        desc = defn.get("description")
        if desc:
            result["description"] = desc
        else:
            result["description"] = f"{name} model"
        result["attributes"] = attributes
        return result

    # -- property / attribute handling --------------------------------------

    def _convert_property(
        self,
        class_name: str,
        prop_name: str,
        schema: dict[str, Any],
        is_required: bool,
    ) -> dict[str, Any]:
        attr: dict[str, Any] = {}
        if is_required:
            attr["required"] = True

        # Resolve the effective schema (strip allOf wrappers with single item)
        schema = self._unwrap_allof(schema)

        # --- $ref ---
        if "$ref" in schema:
            ref_name = self._ref_name(schema["$ref"])
            attr["range"] = ref_name
            return attr

        # --- const (Literal single-value fields like node discriminators) ---
        if "const" in schema:
            attr["range"] = "string"
            attr["equals_string"] = schema["const"]
            return attr

        # --- enum (inline Literal) ---
        if "enum" in schema and schema.get("type") == "string":
            # Inline string enum — create a note; LinkML would need a named enum
            attr["range"] = "string"
            attr["description"] = f"One of: {', '.join(str(v) for v in schema['enum'])}"
            return attr

        # --- anyOf / oneOf (union types, nullable) ---
        if "anyOf" in schema or "oneOf" in schema:
            variants = schema.get("anyOf") or schema.get("oneOf", [])
            return self._convert_union_property(class_name, prop_name, variants, attr)

        # --- array ---
        if schema.get("type") == "array":
            attr["multivalued"] = True
            items = schema.get("items", {})
            items = self._unwrap_allof(items)
            if "$ref" in items:
                attr["range"] = self._ref_name(items["$ref"])
            elif "anyOf" in items or "oneOf" in items:
                # Array of union — lossy
                qualified = f"{class_name}.{prop_name}"
                self.warnings.append(
                    f"{qualified}: array of union type; projected as multivalued "
                    f"string (lossy)"
                )
                self.lossy_fields.append(qualified)
                attr["range"] = "string"
                attr["description"] = "Array of discriminated union (lossy projection)"
            else:
                item_type = items.get("type", "string")
                if item_type == "array":
                    # Nested array (e.g. list[tuple[...]])
                    qualified = f"{class_name}.{prop_name}"
                    self.warnings.append(
                        f"{qualified}: nested array (tuple) projected as "
                        f"multivalued string (lossy)"
                    )
                    self.lossy_fields.append(qualified)
                    attr["range"] = "string"
                    attr["description"] = "Nested array / tuple type (lossy projection)"
                else:
                    attr["range"] = _TYPE_MAP.get(item_type, "string")
            return attr

        # --- object (dict-like, e.g. dict[str, Any]) ---
        if schema.get("type") == "object":
            qualified = f"{class_name}.{prop_name}"
            self.warnings.append(
                f"{qualified}: open dict type projected as string (lossy)"
            )
            self.lossy_fields.append(qualified)
            attr["range"] = "string"
            attr["description"] = "Open dict type (lossy projection)"
            return attr

        # --- simple type ---
        simple_type = schema.get("type", "string")
        attr["range"] = _TYPE_MAP.get(simple_type, "string")
        return attr

    def _convert_union_property(
        self,
        class_name: str,
        prop_name: str,
        variants: list[dict[str, Any]],
        attr: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle anyOf / oneOf union properties."""
        # Filter out null variants (used for Optional)
        non_null = [v for v in variants if v.get("type") != "null"]
        null_present = len(non_null) < len(variants)

        if null_present and not attr.get("required"):
            # It's an Optional field — not required is already captured
            pass

        if len(non_null) == 1:
            # Simple Optional[X]
            inner = self._unwrap_allof(non_null[0])
            if "$ref" in inner:
                attr["range"] = self._ref_name(inner["$ref"])
            elif inner.get("type") == "array":
                attr["multivalued"] = True
                items = inner.get("items", {})
                items = self._unwrap_allof(items)
                if "$ref" in items:
                    attr["range"] = self._ref_name(items["$ref"])
                else:
                    attr["range"] = _TYPE_MAP.get(items.get("type", "string"), "string")
            elif "enum" in inner and inner.get("type") == "string":
                attr["range"] = "string"
                attr["description"] = f"One of: {', '.join(str(v) for v in inner['enum'])}"
            else:
                attr["range"] = _TYPE_MAP.get(inner.get("type", "string"), "string")
            return attr

        if len(non_null) > 1:
            # True union — lossy in LinkML
            qualified = f"{class_name}.{prop_name}"

            # Check if all variants are $ref (discriminated union of classes)
            all_refs = all("$ref" in self._unwrap_allof(v) for v in non_null)
            if all_refs:
                ref_names = [self._ref_name(self._unwrap_allof(v)["$ref"]) for v in non_null]
                self.warnings.append(
                    f"{qualified}: discriminated union of "
                    f"[{', '.join(ref_names)}]; projected as first variant (lossy)"
                )
                self.lossy_fields.append(qualified)
                attr["range"] = ref_names[0]
                attr["description"] = (
                    f"Discriminated union (lossy projection). "
                    f"Canonical variants: {', '.join(ref_names)}"
                )
            else:
                # Mixed union
                self.warnings.append(
                    f"{qualified}: mixed union type projected as string (lossy)"
                )
                self.lossy_fields.append(qualified)
                attr["range"] = "string"
                attr["description"] = "Mixed union type (lossy projection)"
            return attr

        # Fallback: all null or empty
        attr["range"] = "string"
        return attr

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def _unwrap_allof(schema: dict[str, Any]) -> dict[str, Any]:
        """Pydantic sometimes wraps a single $ref in ``allOf: [{$ref: ...}]``."""
        if "allOf" in schema and len(schema["allOf"]) == 1:
            return schema["allOf"][0]
        return schema

    @staticmethod
    def _ref_name(ref: str) -> str:
        """Extract the definition name from ``#/$defs/FooBar``."""
        return ref.rsplit("/", 1)[-1]


# ---------------------------------------------------------------------------
# YAML rendering
# ---------------------------------------------------------------------------


def _render_yaml(doc: dict[str, Any]) -> str:
    """Render the LinkML document dict to a YAML string with a header comment."""
    header = (
        "# ==========================================================================\n"
        "# THIS FILE IS A DERIVED PROJECTION — NOT THE CANONICAL SOURCE OF TRUTH.\n"
        "#\n"
        f"# Generated from: {doc.get('description', '').split(chr(10))[0]}\n"
        "# Canonical models live in the Pydantic model layer under src/limnalis/models/.\n"
        "#\n"
        "# Lossy / unsupported mappings:\n"
        "#   - Discriminated unions are projected as the first variant class or string.\n"
        "#   - Open dict types (dict[str, Any]) are projected as string.\n"
        "#   - Nested arrays / tuples are projected as multivalued string.\n"
        "#   - Pydantic validators and cross-field constraints are not represented.\n"
        "# ==========================================================================\n\n"
    )

    # sort_keys=False: LinkML schema keys are ordered semantically
    # (id -> name -> title -> description -> prefixes -> classes -> enums -> types)
    # rather than alphabetically, for human readability.
    yaml_body = yaml.dump(
        doc,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )

    return header + yaml_body
