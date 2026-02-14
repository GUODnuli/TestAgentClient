# -*- coding: utf-8 -*-
"""Tests for Java AST parser."""

from pathlib import Path

import pytest

from src.parser.java_parser import JavaParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "java"


@pytest.fixture
def parser():
    return JavaParser()


def _parse_fixture(parser, filename):
    path = FIXTURES / filename
    content = path.read_bytes()
    return parser.parse_file(str(path), content)


class TestJavaParserSymbols:
    def test_class_extraction(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        class_symbols = [s for s in result.symbols if s.symbol_type == "CLASS"]
        assert len(class_symbols) == 1
        assert class_symbols[0].name == "LoanController"
        assert class_symbols[0].fqn == "com.bank.loan.controller.LoanController"

    def test_method_extraction(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        methods = [s for s in result.symbols if s.symbol_type == "METHOD"]
        method_names = {m.name for m in methods}
        assert "apply" in method_names
        assert "getStatus" in method_names

    def test_field_extraction(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        fields = [s for s in result.symbols if s.symbol_type == "FIELD"]
        assert len(fields) >= 1
        assert any(f.name == "loanService" for f in fields)

    def test_interface_extraction(self, parser):
        result = _parse_fixture(parser, "LoanMapper.java")
        interfaces = [s for s in result.symbols if s.symbol_type == "INTERFACE"]
        assert len(interfaces) == 1
        assert interfaces[0].name == "LoanMapper"

    def test_service_class(self, parser):
        result = _parse_fixture(parser, "LoanService.java")
        classes = [s for s in result.symbols if s.symbol_type == "CLASS"]
        assert len(classes) == 1
        assert classes[0].fqn == "com.bank.loan.service.LoanService"

        methods = [s for s in result.symbols if s.symbol_type == "METHOD"]
        assert len(methods) == 2
        fqns = {m.fqn for m in methods}
        assert "com.bank.loan.service.LoanService.submitApplication" in fqns
        assert "com.bank.loan.service.LoanService.queryStatus" in fqns


class TestJavaParserAnnotations:
    def test_class_annotations(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        class_anns = [a for a in result.annotations if a.scope == "CLASS"]
        ann_names = {a.annotation_name for a in class_anns}
        assert "RestController" in ann_names
        assert "RequestMapping" in ann_names

    def test_method_annotations(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        method_anns = [a for a in result.annotations if a.scope == "METHOD"]
        ann_names = {a.annotation_name for a in method_anns}
        assert "TransCode" in ann_names
        assert "PostMapping" in ann_names

    def test_annotation_params(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        transcode = [a for a in result.annotations if a.annotation_name == "TransCode"]
        assert len(transcode) == 1
        assert transcode[0].params.get("value") == "LN_LOAN_APPLY"

    def test_service_annotation(self, parser):
        result = _parse_fixture(parser, "LoanService.java")
        class_anns = [a for a in result.annotations if a.scope == "CLASS"]
        assert any(a.annotation_name == "Service" for a in class_anns)


class TestJavaParserImports:
    def test_imports(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        assert len(result.imports) >= 3
        import_paths = {i.import_path for i in result.imports}
        assert "com.bank.loan.service.LoanService" in import_paths


class TestJavaParserCallEdges:
    def test_method_calls(self, parser):
        result = _parse_fixture(parser, "LoanService.java")
        edges = result.call_edges
        # submitApplication calls loanMapper.insertApplication and request methods
        caller_fqns = {e.caller_fqn for e in edges}
        assert any("submitApplication" in f for f in caller_fqns)

    def test_call_targets(self, parser):
        result = _parse_fixture(parser, "LoanController.java")
        edges = result.call_edges
        callee_fqns = {e.callee_fqn for e in edges}
        # apply() calls loanService.submitApplication()
        assert any("submitApplication" in f for f in callee_fqns)
