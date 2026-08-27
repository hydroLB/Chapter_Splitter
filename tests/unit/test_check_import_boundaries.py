"""Tests for the import-boundary enforcement script."""

from scripts import check_import_boundaries


def test_cli_commands_are_classified_as_interfaces() -> None:
    assert check_import_boundaries._layer_for_module("chapter_splitter.cli_commands.detect") == 2


def test_unclassified_package_module_is_a_violation() -> None:
    violations = check_import_boundaries._find_violations(
        {"chapter_splitter.new_package.module": set()}
    )

    assert violations == [
        "chapter_splitter.new_package.module is not assigned to an architecture layer; "
        "add a layer prefix or an explicit exception"
    ]


def test_package_root_is_an_explicit_classification_exception() -> None:
    assert (
        check_import_boundaries._find_violations(
            {"chapter_splitter": set(), "chapter_splitter._version": set()}
        )
        == []
    )
