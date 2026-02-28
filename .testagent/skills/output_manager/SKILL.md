---
name: output-manager
description: >
  Manage and verify output artifacts produced during task execution.
  Supports two artifact types:
  (1) User-downloadable deliverables — session-scoped files written by
      write_output_file and accessible via read_output_file / list_output_files;
  (2) Non-downloadable intermediate files — workspace or custom-path files
      accessible by passing a directory parameter to the same tools.
  Use this skill whenever a workflow needs to audit, merge, or verify that
  expected output files have been generated before finalizing a task.
version: 1.0.0
tools_dir: tools
allowed_tools:
  - read_output_file
  - list_output_files
tags: [output, files, verification, artifacts, download]
---

# Output Manager

## Overview

Provides read/list access to output artifacts in two scenarios:

- **用户下载产物 (User-downloadable artifacts)**: Files written by Workers via
  `write_output_file`, stored under `{output_dir}/{user_id}/{conversation_id}/`.
  Use `list_output_files()` and `read_output_file(filename)` WITHOUT a directory
  argument to access the session output directory automatically.

- **非用户下载产物 (Non-downloadable / intermediate files)**: Files in a custom
  path (workspace, cache, temp dirs). Pass the `directory` argument explicitly:
  `list_output_files(directory="/path/to/dir")` or
  `read_output_file(filename, directory="/path/to/dir")`.

## Tools

- `list_output_files(directory="")` — List files. Defaults to session output dir.
- `read_output_file(filename, directory="")` — Read a file. Defaults to session output dir.

## Workflow

1. After Workers complete their tasks, call `list_output_files()` to audit which
   files were produced.
2. If an expected file is missing, re-spawn the responsible Worker.
3. Call `read_output_file(filename)` to inspect file contents before merging
   batch results or generating a final report.
4. For intermediate workspace files, use the `directory` parameter instead of
   relying on the session context.

## Notes

- `list_output_files()` and `read_output_file()` with no `directory` arg require
  `OutputFileContext` to be initialized (i.e., `--output-dir` passed at startup).
  If not configured, both return `{"status": "error", "error": "..."}`.
- For workspace files that are NOT output artifacts, prefer `read_file` / `glob_files`
  from the base toolkit — they apply workspace-boundary security checks.
