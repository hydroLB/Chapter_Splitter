"""Output path collision helpers for PDF exports."""

from __future__ import annotations

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
    """Resolve final output paths with configured collision handling.

    Summary:
        Convert chapter titles into output paths, applying collision policy against existing files
        and within-run duplicates.
    Inputs:
        - chapters: Validated chapters for export.
        - output_dir: Output directory for chapter PDFs.
        - io_config: IO configuration controlling collision policy.
        - location: Fully qualified module and method name.
    Outputs:
        - List of final output paths in the same order as chapters.
    Side effects:
        Checks filesystem state for existing output files.
    Error handling:
        Raises ValidationError or IoError when collisions cannot be resolved safely.
    Ties to other methods:
        Used by split_pdf_into_chapters before writing any bytes.
    Why this exists:
        Resolving all paths up front avoids partial exports when a late chapter collides.
    """
    error_location = "chapter_splitter.pdf.splitting.engine.collisions.resolve_output_paths"
    context = f" Context: {location}." if location else ""
    policy = io_config.output_collision_policy
    max_suffix = io_config.output_collision_max_suffix
    resolved: list[Path] = []
    used_stems: set[str] = set()
    used_paths: set[Path] = set()

    for chapter in chapters:
        stem = safe_filename(chapter.title)
        if policy in ("error", "overwrite") and stem in used_stems:
            raise ValidationError(
                format_error_message(
                    error_location,
                    "Multiple chapter titles sanitize to the same output filename stem "
                    f"'{stem}'. Rename the chapters or set io.output_collision_policy='suffix'."
                    f"{context}",
                )
            )
        used_stems.add(stem)
        resolved.append(
            _resolve_chapter_output_path(
                stem=stem,
                output_dir=output_dir,
                policy=policy,
                max_suffix=max_suffix,
                io_config=io_config,
                used_paths=used_paths,
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
    used_paths: set[Path],
    context: str,
    error_location: str,
) -> Path:
    """Resolve one output path under the configured collision policy.

    Summary:
        Apply error, overwrite, or suffix collision handling for a single sanitized chapter stem.
    Inputs:
        - stem: Sanitized filename stem for the chapter.
        - output_dir: Output directory for exported PDFs.
        - policy: Configured collision policy string.
        - max_suffix: Maximum numeric suffix search depth for suffix mode.
        - io_config: IO configuration used for user-facing hints.
        - used_paths: Paths already reserved during the current export run.
        - context: Formatted context suffix for error messages.
        - error_location: Fully qualified helper location for error messages.
    Outputs:
        - Resolved output path for the chapter.
    Side effects:
        Checks filesystem state and mutates used_paths when a path is reserved.
    Error handling:
        Raises IoError when the configured policy is unsupported or no path is available.
    Ties to other methods:
        Used by resolve_output_paths.
    Why this exists:
        Keeping per-path collision handling isolated reduces the complexity of the outer loop.
    """
    if policy == "error":
        return _reserve_error_policy_path(
            stem=stem,
            output_dir=output_dir,
            io_config=io_config,
            used_paths=used_paths,
            context=context,
            error_location=error_location,
        )
    if policy == "overwrite":
        return _reserve_overwrite_policy_path(
            stem=stem,
            output_dir=output_dir,
            used_paths=used_paths,
        )
    if policy == "suffix":
        return _reserve_suffix_policy_path(
            stem=stem,
            output_dir=output_dir,
            max_suffix=max_suffix,
            used_paths=used_paths,
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
    used_paths: set[Path],
    context: str,
    error_location: str,
) -> Path:
    """Reserve an output path for the error collision policy.

    Summary:
        Fail immediately when the target output file already exists.
    Inputs:
        - stem: Sanitized filename stem for the chapter.
        - output_dir: Output directory for exported PDFs.
        - io_config: IO configuration used for user-facing hints.
        - used_paths: Paths already reserved during the current export run.
        - context: Formatted context suffix for error messages.
        - error_location: Fully qualified helper location for error messages.
    Outputs:
        - Reserved output path.
    Side effects:
        Mutates used_paths when the candidate is available.
    Error handling:
        Raises IoError when an existing file blocks export.
    Ties to other methods:
        Used by _resolve_chapter_output_path.
    Why this exists:
        The error policy should be explicit and produce a single actionable failure point.
    """
    candidate = output_dir / f"{stem}.pdf"
    if candidate.exists():
        raise IoError(
            format_error_message(
                error_location,
                f"Output file already exists: {candidate}.{context} "
                f"{format_collision_hint(io_config)}",
            )
        )
    used_paths.add(candidate)
    return candidate


def _reserve_overwrite_policy_path(
    *,
    stem: str,
    output_dir: Path,
    used_paths: set[Path],
) -> Path:
    """Reserve an output path for the overwrite collision policy.

    Summary:
        Reuse the canonical chapter filename regardless of whether it already exists.
    Inputs:
        - stem: Sanitized filename stem for the chapter.
        - output_dir: Output directory for exported PDFs.
        - used_paths: Paths already reserved during the current export run.
    Outputs:
        - Reserved output path.
    Side effects:
        Mutates used_paths.
    Error handling:
        None.
    Ties to other methods:
        Used by _resolve_chapter_output_path.
    Why this exists:
        Overwrite mode should remain the simplest, lowest-overhead branch.
    """
    candidate = output_dir / f"{stem}.pdf"
    used_paths.add(candidate)
    return candidate


def _reserve_suffix_policy_path(
    *,
    stem: str,
    output_dir: Path,
    max_suffix: int,
    used_paths: set[Path],
    context: str,
    error_location: str,
) -> Path:
    """Reserve an output path for the suffix collision policy.

    Summary:
        Search for the first unused filename stem by appending numeric suffixes when necessary.
    Inputs:
        - stem: Sanitized filename stem for the chapter.
        - output_dir: Output directory for exported PDFs.
        - max_suffix: Maximum numeric suffix search depth.
        - used_paths: Paths already reserved during the current export run.
        - context: Formatted context suffix for error messages.
        - error_location: Fully qualified helper location for error messages.
    Outputs:
        - Reserved output path.
    Side effects:
        Checks filesystem state and mutates used_paths when a candidate is reserved.
    Error handling:
        Raises IoError when no candidate is available within the configured suffix range.
    Ties to other methods:
        Used by _resolve_chapter_output_path.
    Why this exists:
        Suffix-mode filename allocation is the noisiest branch and deserves its own helper.
    """
    for idx in range(1, max_suffix + 1):
        candidate_stem = stem if idx == 1 else with_suffix(stem, idx)
        candidate = output_dir / f"{candidate_stem}.pdf"
        if candidate in used_paths or candidate.exists():
            continue
        used_paths.add(candidate)
        return candidate
    raise IoError(
        format_error_message(
            error_location,
            f"Unable to find an available output filename for '{stem}' after "
            f"{max_suffix - 1} suffix attempts.{context}",
        )
    )


def format_collision_hint(io_config: IOConfig) -> str:
    """Build a consistent config hint for collision errors.

    Summary:
        Provide a short hint that points to the config knob controlling collision behavior.
    Inputs:
        - io_config: IO configuration used by the pipeline.
    Outputs:
        - Human-readable hint string.
    Side effects:
        None.
    Error handling:
        None.
    Ties to other methods:
        Used by _reserve_error_policy_path.
    Why this exists:
        Collision errors are common user friction points, so the guidance should stay consistent.
    """
    return "To change this behavior, update io.output_collision_policy (error, overwrite, suffix)."


def with_suffix(base: str, index: int) -> str:
    """Return a deterministic filename stem with a numeric suffix.

    Summary:
        Append a " (n)" suffix to a filename stem without changing the extension.
    Inputs:
        - base: Base filename stem.
        - index: Numeric suffix value.
    Outputs:
        - Suffixed filename stem.
    Side effects:
        None.
    Error handling:
        Raises ValidationError when index is less than two.
    Ties to other methods:
        Used by _reserve_suffix_policy_path.
    Why this exists:
        Suffixing provides a non-destructive collision policy that keeps outputs user-friendly.
    """
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
