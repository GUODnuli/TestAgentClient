# -*- coding: utf-8 -*-
"""Java AST parser using tree-sitter.

Extracts symbols (classes, interfaces, enums, methods, fields, constructors),
call edges (method invocations), annotations, and imports.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from tree_sitter import Node

from src.parser.base import (
    FileParseResult,
    LanguageParser,
    ParsedAnnotation,
    ParsedCallEdge,
    ParsedImport,
    ParsedSymbol,
)
from src.utils.fqn import java_fqn
from src.utils.tree_sitter_loader import get_parser

logger = logging.getLogger(__name__)

# Type declaration node types
_CLASS_TYPES = {"class_declaration", "interface_declaration", "enum_declaration"}
_METHOD_TYPES = {"method_declaration", "constructor_declaration"}

# Visibility modifiers
_VISIBILITY_KEYWORDS = {"public", "protected", "private"}


class JavaParser(LanguageParser):
    def language(self) -> str:
        return "java"

    def file_extensions(self) -> List[str]:
        return [".java"]

    def parse_file(self, file_path: str, content: bytes, package_prefix: str = "") -> FileParseResult:
        parser = get_parser("java")
        tree = parser.parse(content)
        root = tree.root_node

        result = FileParseResult()

        # Extract package declaration
        package = self._extract_package(root, content)
        if not package and package_prefix:
            package = package_prefix

        # Extract imports
        result.imports = self._extract_imports(root, content)

        # Build import map for type resolution
        import_map = self._build_import_map(result.imports)

        # Extract type declarations (classes, interfaces, enums) recursively
        self._extract_types(root, content, package, "", result, import_map)

        return result

    # ── Package ──

    def _extract_package(self, root: Node, content: bytes) -> str:
        for child in root.children:
            if child.type == "package_declaration":
                # Get the scoped_identifier or identifier child
                for c in child.children:
                    if c.type in ("scoped_identifier", "identifier"):
                        return self._node_text(c, content)
        return ""

    # ── Imports ──

    def _extract_imports(self, root: Node, content: bytes) -> List[ParsedImport]:
        imports = []
        for child in root.children:
            if child.type == "import_declaration":
                text = self._node_text(child, content)
                is_static = "static" in text
                path = ""
                for c in child.children:
                    if c.type in ("scoped_identifier", "identifier"):
                        path = self._node_text(c, content)
                    elif c.type == "asterisk":
                        path += ".*"

                if path:
                    import_type = "static" if is_static else ("wildcard" if path.endswith(".*") else "single")
                    imports.append(ParsedImport(import_path=path, import_type=import_type))
        return imports

    def _build_import_map(self, imports: List[ParsedImport]) -> Dict[str, str]:
        """Map simple class name -> fully qualified name from imports."""
        m: Dict[str, str] = {}
        for imp in imports:
            if imp.import_type == "single" or imp.import_type == "static":
                parts = imp.import_path.rsplit(".", 1)
                if len(parts) == 2:
                    m[parts[1]] = imp.import_path
        return m

    # ── Type declarations ──

    def _extract_types(
        self,
        node: Node,
        content: bytes,
        package: str,
        parent_fqn: str,
        result: FileParseResult,
        import_map: Dict[str, str],
    ):
        for child in node.children:
            if child.type in _CLASS_TYPES:
                self._process_type_declaration(child, content, package, parent_fqn, result, import_map)
            elif child.type == "program":
                # Top-level: recurse
                self._extract_types(child, content, package, parent_fqn, result, import_map)

    def _process_type_declaration(
        self,
        node: Node,
        content: bytes,
        package: str,
        parent_fqn: str,
        result: FileParseResult,
        import_map: Dict[str, str],
    ):
        name = self._find_child_text(node, "identifier", content)
        if not name:
            return

        symbol_type = {
            "class_declaration": "CLASS",
            "interface_declaration": "INTERFACE",
            "enum_declaration": "ENUM",
        }.get(node.type, "CLASS")

        fqn = java_fqn(package, name) if not parent_fqn else f"{parent_fqn}.{name}"
        visibility = self._extract_visibility(node, content)
        signature = self._build_type_signature(node, content, symbol_type, name)

        result.symbols.append(ParsedSymbol(
            fqn=fqn,
            name=name,
            symbol_type=symbol_type,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            parent_fqn=parent_fqn,
            visibility=visibility,
        ))

        # Extract annotations on the type
        self._extract_annotations_for(node, content, fqn, "CLASS", result)

        # Process body
        body = self._find_child(node, "class_body") or self._find_child(node, "interface_body") or self._find_child(node, "enum_body")
        if body:
            self._process_class_body(body, content, package, fqn, result, import_map)

    def _process_class_body(
        self,
        body: Node,
        content: bytes,
        package: str,
        class_fqn: str,
        result: FileParseResult,
        import_map: Dict[str, str],
    ):
        # Track field types for call resolution
        field_types: Dict[str, str] = {}

        for child in body.children:
            if child.type in _METHOD_TYPES:
                self._process_method(child, content, package, class_fqn, result, import_map, field_types)
            elif child.type == "field_declaration":
                self._process_field(child, content, class_fqn, result, field_types, import_map)
            elif child.type in _CLASS_TYPES:
                # Inner class
                self._process_type_declaration(child, content, package, class_fqn, result, import_map)

    # ── Methods ──

    def _process_method(
        self,
        node: Node,
        content: bytes,
        package: str,
        class_fqn: str,
        result: FileParseResult,
        import_map: Dict[str, str],
        field_types: Dict[str, str],
    ):
        name = self._find_child_text(node, "identifier", content)
        if not name:
            return

        is_constructor = node.type == "constructor_declaration"
        symbol_type = "CONSTRUCTOR" if is_constructor else "METHOD"
        fqn = f"{class_fqn}.{name}"
        visibility = self._extract_visibility(node, content)
        signature = self._build_method_signature(node, content)

        result.symbols.append(ParsedSymbol(
            fqn=fqn,
            name=name,
            symbol_type=symbol_type,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            signature=signature,
            parent_fqn=class_fqn,
            visibility=visibility,
        ))

        # Extract annotations on the method
        self._extract_annotations_for(node, content, fqn, "METHOD", result)

        # Build local variable type map from method parameters + local declarations
        local_types: Dict[str, str] = dict(field_types)  # inherit field types
        self._extract_param_types(node, content, import_map, local_types)

        # Extract call edges from method body
        method_body = self._find_child(node, "block") or self._find_child(node, "constructor_body")
        if method_body:
            self._extract_local_var_types(method_body, content, import_map, local_types)
            self._extract_calls(method_body, content, fqn, result, import_map, local_types)

    def _extract_param_types(
        self, node: Node, content: bytes, import_map: Dict[str, str], local_types: Dict[str, str],
    ):
        """Extract parameter types from formal_parameters."""
        params = self._find_child(node, "formal_parameters")
        if not params:
            return
        for child in params.children:
            if child.type == "formal_parameter":
                type_name = ""
                param_name = ""
                for c in child.children:
                    if c.type in ("type_identifier", "generic_type", "array_type",
                                  "scoped_type_identifier"):
                        type_name = self._node_text(c, content).split("<")[0].strip()
                    elif c.type == "identifier":
                        param_name = self._node_text(c, content)
                if type_name and param_name and type_name[0].isupper():
                    resolved = import_map.get(type_name, type_name)
                    local_types[param_name] = resolved

    def _extract_local_var_types(
        self, body: Node, content: bytes, import_map: Dict[str, str], local_types: Dict[str, str],
    ):
        """Scan method body for local variable declarations and record their types."""
        for child in body.children:
            if child.type == "local_variable_declaration":
                type_name = ""
                for c in child.children:
                    if c.type in ("type_identifier", "generic_type", "array_type",
                                  "scoped_type_identifier"):
                        type_name = self._node_text(c, content).split("<")[0].strip()
                    elif c.type == "variable_declarator":
                        var_name = self._find_child_text(c, "identifier", content)
                        if type_name and var_name and type_name[0].isupper():
                            resolved = import_map.get(type_name, type_name)
                            local_types[var_name] = resolved
            # Recurse into blocks (if/else/for/try)
            elif child.type in ("block", "if_statement", "for_statement", "while_statement",
                                "try_statement", "try_with_resources_statement", "switch_expression"):
                self._extract_local_var_types(child, content, import_map, local_types)

    # ── Fields ──

    def _process_field(
        self,
        node: Node,
        content: bytes,
        class_fqn: str,
        result: FileParseResult,
        field_types: Dict[str, str],
        import_map: Dict[str, str],
    ):
        # Extract type
        type_node = None
        for child in node.children:
            if child.type in ("type_identifier", "generic_type", "array_type", "integral_type",
                              "floating_point_type", "boolean_type", "void_type", "scoped_type_identifier"):
                type_node = child
                break

        type_name = self._node_text(type_node, content) if type_node else ""

        # Extract variable declarators
        for child in node.children:
            if child.type == "variable_declarator":
                var_name = self._find_child_text(child, "identifier", content)
                if var_name:
                    fqn = f"{class_fqn}.{var_name}"
                    visibility = self._extract_visibility(node, content)
                    sig = f"{type_name} {var_name}"

                    result.symbols.append(ParsedSymbol(
                        fqn=fqn,
                        name=var_name,
                        symbol_type="FIELD",
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=sig,
                        parent_fqn=class_fqn,
                        visibility=visibility,
                    ))

                    # Track field type for heuristic call resolution
                    simple_type = type_name.split("<")[0].strip()
                    if simple_type and simple_type[0].isupper():
                        # Resolve FQN from imports
                        resolved = import_map.get(simple_type, simple_type)
                        field_types[var_name] = resolved

                    # Extract field annotations
                    self._extract_annotations_for(node, content, fqn, "FIELD", result)

    # ── Call edges ──

    def _extract_calls(
        self,
        node: Node,
        content: bytes,
        caller_fqn: str,
        result: FileParseResult,
        import_map: Dict[str, str],
        field_types: Dict[str, str],
    ):
        """Recursively extract method_invocation nodes and build call edges."""
        if node.type == "method_invocation":
            edge = self._resolve_method_invocation(node, content, caller_fqn, import_map, field_types)
            if edge:
                result.call_edges.append(edge)

        for child in node.children:
            self._extract_calls(child, content, caller_fqn, result, import_map, field_types)

    def _resolve_method_invocation(
        self,
        node: Node,
        content: bytes,
        caller_fqn: str,
        import_map: Dict[str, str],
        field_types: Dict[str, str],
    ) -> Optional[ParsedCallEdge]:
        """Heuristically resolve a method invocation to a callee FQN.

        Handles patterns:
        - method()                     → same-class call
        - object.method()              → field/local/import resolution
        - Class.staticMethod()         → import resolution
        - object.method1().method2()   → chained call (extract method2, low confidence)
        """
        method_name = None
        object_name = None
        is_chained = False

        for child in node.children:
            if child.type == "identifier" and method_name is None:
                text = self._node_text(child, content)
                if object_name is None:
                    next_sib = child.next_named_sibling
                    if next_sib and next_sib.type == "identifier":
                        object_name = text
                    else:
                        method_name = text
                else:
                    method_name = text
            elif child.type == "field_access":
                object_name = self._node_text(child, content)
            elif child.type == "method_invocation":
                # Chained call: obj.method1().method2()
                # The inner method_invocation is the receiver; extract the outer method name
                is_chained = True
                # Try to get the receiver's object for context
                inner_idents = [c for c in child.children if c.type == "identifier"]
                if inner_idents:
                    object_name = self._node_text(inner_idents[0], content)

        if not method_name:
            idents = [c for c in node.children if c.type == "identifier"]
            if len(idents) >= 2:
                object_name = self._node_text(idents[0], content)
                method_name = self._node_text(idents[1], content)
            elif len(idents) == 1:
                method_name = self._node_text(idents[0], content)

        if not method_name:
            return None

        confidence = 0.3
        callee_fqn = method_name

        if is_chained:
            # Chained calls have low confidence since we can't resolve the intermediate type
            callee_fqn = f"?.{method_name}" if not object_name else f"{object_name}.?.{method_name}"
            confidence = 0.2
        elif object_name:
            # Try to resolve object type from local/field types
            resolved_type = field_types.get(object_name)
            if resolved_type:
                callee_fqn = f"{resolved_type}.{method_name}"
                confidence = 0.7
            else:
                # Try import_map (static method or class name)
                resolved_type = import_map.get(object_name)
                if resolved_type:
                    callee_fqn = f"{resolved_type}.{method_name}"
                    confidence = 0.6
                else:
                    callee_fqn = f"{object_name}.{method_name}"
                    confidence = 0.4
        else:
            # Same-class method call
            class_fqn = caller_fqn.rsplit(".", 1)[0] if "." in caller_fqn else ""
            if class_fqn:
                callee_fqn = f"{class_fqn}.{method_name}"
                confidence = 0.8

        return ParsedCallEdge(
            caller_fqn=caller_fqn,
            callee_fqn=callee_fqn,
            call_type="internal",
            line=node.start_point[0] + 1,
            confidence=confidence,
        )

    # ── Annotations ──

    def _extract_annotations_for(
        self,
        node: Node,
        content: bytes,
        symbol_fqn: str,
        scope: str,
        result: FileParseResult,
    ):
        """Extract annotations preceding a declaration node."""
        # In tree-sitter-java, annotations are siblings before the declaration
        # or children named "modifiers" containing annotations
        modifiers = self._find_child(node, "modifiers")
        targets = [modifiers] if modifiers else [node]

        for target in targets:
            if target is None:
                continue
            for child in target.children:
                if child.type in ("marker_annotation", "annotation"):
                    ann = self._parse_annotation(child, content, symbol_fqn, scope)
                    if ann:
                        result.annotations.append(ann)

    def _parse_annotation(
        self, node: Node, content: bytes, symbol_fqn: str, scope: str
    ) -> Optional[ParsedAnnotation]:
        ann_name = ""
        params: Dict[str, Any] = {}

        for child in node.children:
            if child.type == "identifier":
                ann_name = self._node_text(child, content)
            elif child.type == "scoped_identifier":
                ann_name = self._node_text(child, content)
            elif child.type == "annotation_argument_list":
                params = self._parse_annotation_args(child, content)

        if ann_name:
            return ParsedAnnotation(
                symbol_fqn=symbol_fqn,
                annotation_name=ann_name,
                scope=scope,
                params=params,
            )
        return None

    def _parse_annotation_args(self, node: Node, content: bytes) -> Dict[str, Any]:
        """Parse annotation arguments into a dict."""
        params: Dict[str, Any] = {}
        for child in node.children:
            if child.type == "element_value_pair":
                key = ""
                val = ""
                for c in child.children:
                    if c.type == "identifier":
                        key = self._node_text(c, content)
                    elif c.type in ("string_literal", "decimal_integer_literal",
                                    "true", "false", "identifier"):
                        val = self._node_text(c, content).strip('"')
                    elif c.type == "element_value_array_initializer":
                        val = self._node_text(c, content)
                if key:
                    params[key] = val
            elif child.type in ("string_literal", "decimal_integer_literal"):
                # Single-value annotation like @TransCode("LN_LOAN_APPLY")
                params["value"] = self._node_text(child, content).strip('"')
        return params

    # ── Helpers ──

    def _extract_visibility(self, node: Node, content: bytes) -> str:
        modifiers = self._find_child(node, "modifiers")
        if modifiers:
            for child in modifiers.children:
                text = self._node_text(child, content)
                if text in _VISIBILITY_KEYWORDS:
                    return text
        return "package-private"

    def _build_type_signature(self, node: Node, content: bytes, symbol_type: str, name: str) -> str:
        parts = []
        modifiers = self._find_child(node, "modifiers")
        if modifiers:
            for child in modifiers.children:
                if child.type not in ("marker_annotation", "annotation"):
                    parts.append(self._node_text(child, content))

        type_keyword = {"CLASS": "class", "INTERFACE": "interface", "ENUM": "enum"}.get(symbol_type, "class")
        parts.append(type_keyword)
        parts.append(name)

        # Extends/implements
        for child in node.children:
            if child.type == "superclass":
                parts.append("extends")
                for c in child.children:
                    if c.type in ("type_identifier", "scoped_type_identifier", "generic_type"):
                        parts.append(self._node_text(c, content))
            elif child.type == "super_interfaces":
                parts.append("implements")
                ifaces = []
                for c in child.children:
                    if c.type == "type_list":
                        ifaces.append(self._node_text(c, content))
                parts.append(", ".join(ifaces) if ifaces else self._node_text(child, content))

        return " ".join(parts)

    def _build_method_signature(self, node: Node, content: bytes) -> str:
        """Build method signature from the declaration (without body)."""
        parts = []
        for child in node.children:
            if child.type == "modifiers":
                mod_parts = []
                for c in child.children:
                    if c.type not in ("marker_annotation", "annotation"):
                        mod_parts.append(self._node_text(c, content))
                if mod_parts:
                    parts.append(" ".join(mod_parts))
            elif child.type in ("type_identifier", "generic_type", "array_type",
                                "integral_type", "floating_point_type", "boolean_type",
                                "void_type", "scoped_type_identifier"):
                parts.append(self._node_text(child, content))
            elif child.type == "identifier":
                parts.append(self._node_text(child, content))
            elif child.type == "formal_parameters":
                parts.append(self._node_text(child, content))
            elif child.type in ("block", "constructor_body"):
                break  # Stop before body
        return " ".join(parts)

    @staticmethod
    def _node_text(node: Node, content: bytes) -> str:
        return content[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    @staticmethod
    def _find_child(node: Node, child_type: str) -> Optional[Node]:
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    @staticmethod
    def _find_child_text(node: Node, child_type: str, content: bytes) -> str:
        for child in node.children:
            if child.type == child_type:
                return content[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        return ""
