"""Output path collision helpers for PDF exports."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from ....config.schema import IOConfig
from ....core.errors import IoError, ValidationError, format_error_message
from ....core.models import ChapterDefinition
from ....utils.filenames import safe_filename


def resolve_output_paths(
    chapters: list[ChapterDefinition],
    output_dir: Path,
    io_config: IOConfig,
    location: str,
) -> list[Path]:
    """Resolve final output paths with configured collision handling."""
    error_location = "chapter_splitter.pdf.splitting.engine.collisions.resolve_output_paths"
    context = f" Context: {location}." if location else ""
    policy = io_config.output_collision_policy
    max_suffix = io_config.output_collision_max_suffix
    resolved: list[Path] = []
    used_stem_keys: set[str] = set()
    existing_paths_by_key = _index_existing_paths(
        output_dir=output_dir,
        context=context,
        error_location=error_location,
    )
    used_path_keys = set(existing_paths_by_key)

    for chapter in chapters:
        stem = safe_filename(chapter.title)
        stem_key = _portable_filename_key(stem)
        if policy in ("error", "overwrite") and stem_key in used_stem_keys:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Multiple chapter titles resolve to the same cross-platform output filename "
                    f"'{stem}.pdf'. Rename the chapters or set "
                    f"io.output_collision_policy='suffix'.{context}",
                )
            )
        used_stem_keys.add(stem_key)
        resolved.append(
            _resolve_chapter_output_path(
                stem=stem,
                output_dir=output_dir,
                policy=policy,
                max_suffix=max_suffix,
                io_config=io_config,
                used_path_keys=used_path_keys,
                existing_paths_by_key=existing_paths_by_key,
                context=context,
                error_location=error_location,
            )
        )
    return resolved


def _resolve_chapter_output_path(
    *,
    stem: str,
    output_dir: Path,
    policy: str,
    max_suffix: int,
    io_config: IOConfig,
    used_path_keys: set[str],
    existing_paths_by_key: dict[str, list[Path]],
    context: str,
    error_location: str,
) -> Path:
    """Resolve one output path under the configured collision policy."""
    if policy == "error":
        return _reserve_error_policy_path(
            stem=stem,
            output_dir=output_dir,
            io_config=io_config,
            used_path_keys=used_path_keys,
            existing_paths_by_key=existing_paths_by_key,
            context=context,
            error_location=error_location,
        )
    if policy == "overwrite":
        return _reserve_overwrite_policy_path(
            stem=stem,
            output_dir=output_dir,
            used_path_keys=used_path_keys,
            existing_paths_by_key=existing_paths_by_key,
            context=context,
            error_location=error_location,
        )
    if policy == "suffix":
        return _reserve_suffix_policy_path(
            stem=stem,
            output_dir=output_dir,
            max_suffix=max_suffix,
            used_path_keys=used_path_keys,
            context=context,
            error_location=error_location,
        )
    raise IoError(
        format_error_message(
            error_location,
            f"Unsupported output collision policy '{policy}'.{context}",
        )
    )


def _reserve_error_policy_path(
    *,
    stem: str,
    output_dir: Path,
    io_config: IOConfig,
    used_path_keys: set[str],
    existing_paths_by_key: dict[str, list[Path]],
    context: str,
    error_location: str,
) -> Path:
    """Reserve an output path for the error collision policy."""
    candidate = output_dir / f"{stem}.pdf"
    candidate_key = _portable_filename_key(candidate.name)
    if candidate_key in used_path_keys:
        existing_matches = existing_paths_by_key.get(candidate_key, [])
        conflicting_path = existing_matches[0] if existing_matches else candidate
        raise IoError(
            format_error_message(
                error_location,
                f"Output path already exists or conflicts cross-platform: "
                f"{conflicting_path}.{context} "
                f"{format_collision_hint(io_config)}",
            )
        )
    used_path_keys.add(candidate_key)
    return candidate


def _reserve_overwrite_policy_path(
    *,
    stem: str,
    output_dir: Path,
    used_path_keys: set[str],
    existing_paths_by_key: dict[str, list[Path]],
    context: str,
    error_location: str,
) -> Path:
    """Reserve an output path for the overwrite collision policy."""
    canonical_candidate = output_dir / f"{stem}.pdf"
    candidate_key = _portable_filename_key(canonical_candidate.name)
    existing_matches = existing_paths_by_key.get(candidate_key, [])
    if len(existing_matches) > 1:
        formatted_matches = ", ".join(str(path) for path in existing_matches)
        raise IoError(
            format_error_message(
                error_location,
                "Overwrite target is ambiguous because multiple existing names collide "
                f"cross-platform: {formatted_matches}.{context}",
            )
        )
    candidate = existing_matches[0] if existing_matches else canonical_candidate
    if candidate.exists() and not candidate.is_file():
        raise IoError(
            format_error_message(
                error_location,
                f"Overwrite target exists but is not a file: {candidate}.{context}",
            )
        )
    used_path_keys.add(candidate_key)
    return candidate


def _reserve_suffix_policy_path(
    *,
    stem: str,
    output_dir: Path,
    max_suffix: int,
    used_path_keys: set[str],
    context: str,
    error_location: str,
) -> Path:
    """Reserve an output path for the suffix collision policy."""
    for idx in range(1, max_suffix + 1):
        candidate_stem = stem if idx == 1 else with_suffix(stem, idx)
        candidate = output_dir / f"{candidate_stem}.pdf"
        candidate_key = _portable_filename_key(candidate.name)
        if candidate_key in used_path_keys or candidate.exists():
            continue
        used_path_keys.add(candidate_key)
        return candidate
    raise IoError(
        format_error_message(
            error_location,
            f"Unable to find an available output filename for '{stem}' after "
            f"{max_suffix - 1} suffix attempts.{context}",
        )
    )


def _portable_filename_key(name: str) -> str:
    """Return a case-insensitive, canonically normalized filename key."""
    return unicodedata.normalize("NFC", name.casefold())


def _index_existing_paths(
    *,
    output_dir: Path,
    context: str,
    error_location: str,
) -> dict[str, list[Path]]:
    """Index directory entries by their portable filename key before allocating outputs."""
    try:
        entries = sorted(output_dir.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        raise IoError(
            format_error_message(
                error_location,
                f"Unable to inspect existing output paths in {output_dir}.{context}",
            )
        ) from exc
    indexed: dict[str, list[Path]] = {}
    for entry in entries:
        indexed.setdefault(_portable_filename_key(entry.name), []).append(entry)
    return indexed


def format_collision_hint(io_config: IOConfig) -> str:
    """Build a consistent config hint for collision errors."""
    return "To change this behavior, update io.output_collision_policy (error, overwrite, suffix)."


def with_suffix(base: str, index: int) -> str:
    """Return a deterministic filename stem with a numeric suffix."""
    error_location = "chapter_splitter.pdf.splitting.engine.collisions.with_suffix"
    if index < 2:
        raise ValidationError(
            format_error_message(
                error_location,
                f"Suffix index must be >= 2 (got {index}).",
            )
        )
    return f"{base} ({index})"


__all__ = ["format_collision_hint", "resolve_output_paths", "with_suffix"]
