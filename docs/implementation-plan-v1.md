# Implementation Plan - OpenCode Framework v1

## Overview

This document outlines the step-by-step implementation plan to complete v1 of the OpenCode Framework CLI tool. The framework attaches AI coding agents to existing projects safely via devcontainer-backed isolation.

## Status Summary

**Completed:**
- CLI skeleton with `ocframework` entrypoint
- `--version` flag with global settings detection
- `init` command structure
- Preflight checks (tools, git validation, staged changes)
- Basic wizard flow
- Git worktree operations module
- `.opencode/` directory generation
- Basic test coverage
- Devcontainer extend/incompatible handling
- Security mount policy enforcement
- Docker rootless validation
- Optional feature completion (vi/nano)
- Comprehensive test coverage
- End-to-end validation

**No Remaining Work - v1 Complete!**

---

## Step 1: Tighten Spec Alignment

**Goal:** Ensure all behavior matches documentation exactly.

**Actions:**
- [ ] Review `docs/demo-issues.md` for any remaining overrides
- [ ] Cross-check `docs/cli-contract.md` against current CLI behavior
- [ ] Verify `docs/devcontainer-strategy.md` compliance
- [ ] Confirm `docs/security-model.md` mount rules
- [ ] Validate `docs/runtime-layout.md` file structure

**Acceptance:**
- No conflicts between implementation and docs
- `docs/demo-issues.md` is the override source of truth

**Files:**
- `src/opencode_framework/cli.py`
- `src/opencode_framework/preflight.py`
- `src/opencode_framework/wizard.py`
- `src/opencode_framework/generator.py`

---

## Step 2: Finish Preflight Behavior

**Goal:** All preflight checks match contract exactly.

**Current State:**
- Checks for `git`, `docker`, `devcontainer`, `pipx`
- Validates git working tree, repo root, bare repo, staged changes
- Detects existing `.opencode/`

**Issues:**
- Tool name mismatch: docs say `devcontainer-cli`, code checks `devcontainer`
- Need to verify actual executable name on systems

**Actions:**
- [ ] Verify correct executable name for devcontainer CLI
- [ ] Update `REQUIRED_TOOLS` in `preflight.py` if needed
- [ ] Ensure all error messages are actionable
- [ ] Add test for each preflight failure mode

**Acceptance:**
- All preflight failures have clear remediation text
- Tool names match actual system executables
- Tests cover all failure paths

**Files:**
- `src/opencode_framework/preflight.py`
- `tests/test_preflight.py` (new)

---

## Step 3: Solidify `.opencode/` Worktree Lifecycle

**Goal:** Worktree setup matches git-storage-model exactly.

**Current State:**
- `git_ops.py` implements branch creation, worktree management
- `init` command creates worktree on selected branch
- `--force` backs up existing `.opencode/`

**Issues:**
- Need to verify orphan branch behavior
- Need to ensure no auto-commit beyond initial

**Actions:**
- [ ] Verify branch suggestion is `codeagent-{username}`
- [ ] Confirm existing branch reuse works correctly
- [ ] Confirm orphan branch creation works for new branches
- [ ] Verify `--force` properly handles worktrees vs directories
- [ ] Ensure no unexpected commits are made
- [ ] Add integration tests with real git repos

**Acceptance:**
- New repo gets fresh `.opencode/` worktree
- Existing branch is reused without altering main branch
- `--force` creates backup and regenerates cleanly
- Normal mode exits cleanly if `.opencode/` exists

**Files:**
- `src/opencode_framework/git_ops.py`
- `src/opencode_framework/cli.py`
- `tests/test_git_ops.py`
- `tests/test_integration.py` (new)

---

## Step 4: Implement Proper Existing-Devcontainer Handling

**Goal:** Devcontainer detection and handling matches devcontainer-strategy spec.

**Current State:**
- `devcontainer.py` detects standard locations
- `wizard.py` asks about `extend` vs `from_scratch`
- `generator.py` always generates from scratch

**Issues:**
- No actual `extend` logic implemented
- Incompatible devcontainer doesn't exit, just defaults to `from_scratch`

**Actions:**
- [ ] Implement true `extend` logic in generator
- [ ] Make incompatible devcontainer exit with explanation
- [ ] Keep "no existing devcontainer" as automatic `from_scratch`
- [ ] Add tests for each scenario

**Acceptance:**
- Compatible devcontainer can be extended
- Incompatible devcontainer causes exit with clear reason
- Missing devcontainer auto-selects `from_scratch`

**Files:**
- `src/opencode_framework/devcontainer.py`
- `src/opencode_framework/wizard.py`
- `src/opencode_framework/generator.py`
- `tests/test_devcontainer.py` (new)

---

## Step 5: Define and Implement Extend Generation Rules

**Goal:** Extending an existing devcontainer produces correct merged config.

**Decisions Needed:**
- Which fields are inherited from existing devcontainer
- Which fields are overridden by framework
- How to avoid mutating original devcontainer file

**Actions:**
- [ ] Document extend merge rules
- [ ] Implement `_generate_extended_devcontainer()` function
- [ ] Merge required framework settings into generated config
- [ ] Ensure canonical launch uses `.opencode/devcontainer.json`
- [ ] Add tests for extend scenarios

**Merge Rules (proposed):**
- Inherit: `image`, `build`, existing `features`
- Override: `name`, `workspaceFolder`, `workspaceMount`
- Merge: `mounts`, `features`, `customizations`
- Add: `postCreateCommand`, `postStartCommand` for opencode

**Acceptance:**
- Extended devcontainer preserves original intent
- Framework settings are correctly merged
- Original devcontainer file is not modified
- Launch command works with generated config

**Files:**
- `src/opencode_framework/generator.py`
- `docs/devcontainer-extend-rules.md` (new, optional)
- `tests/test_devcontainer.py`

---

## Step 6: Complete Optional Feature Generation

**Goal:** All wizard-selected features generate correctly.

**Current State:**
- `docker`, `python`, `nodejs`, `java` generate features
- `vi`, `nano` are collected but not used

**Actions:**
- [ ] Add `vi` feature/package installation
- [ ] Add `nano` feature/package installation
- [ ] Verify all features map correctly to devcontainer features
- [ ] Ensure `devcontainer.json` is the only source of truth
- [ ] Add tests for feature combinations

**Acceptance:**
- All wizard options generate correct config
- Features work when devcontainer launches
- No separate feature state files

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py` (new)

---

## Step 7: Enforce Mount and Security Policy

**Goal:** Mount permissions match security-model exactly.

**Current State:**
- Global config mounted read-only
- Global auth.json mounted read-only
- Project mounted read-write

**Issues:**
- Whole project is read-write, but docs want config layers read-only
- Need to separate source access from config access

**Mount Rules (from docs):**
- Read-only: global config, framework config, project config, auth.json
- Read-write: `.opencode/runtime_data/`, project source

**Actions:**
- [ ] Review if project config layer needs separate mount
- [ ] Ensure `.opencode/` config files are read-only in container
- [ ] Ensure `.opencode/runtime_data/` is read-write
- [ ] Ensure project source is read-write
- [ ] Add tests for mount semantics

**Acceptance:**
- Agent cannot modify global/framework/project config
- Agent can modify source and runtime_data
- Auth file is read-only when present

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Step 8: Implement Docker Rootless Validation

**Goal:** Docker access only enabled when rootless context exists.

**Current State:**
- Docker selection adds feature to devcontainer
- Sets `DOCKER_CONTEXT=rootless` in env
- No validation of rootless context

**Actions:**
- [ ] Add preflight check for rootless Docker context when Docker selected
- [ ] Fail clearly if Docker selected but no rootless context
- [ ] Only set `DOCKER_CONTEXT=rootless` when validated
- [ ] Add tests for Docker validation

**Acceptance:**
- Docker access requires valid rootless context
- Clear error if validation fails
- Security tradeoff remains explicit

**Files:**
- `src/opencode_framework/preflight.py`
- `src/opencode_framework/wizard.py`
- `tests/test_preflight.py`

---

## Step 9: Finish Runtime Layout Details

**Goal:** Generated files match runtime-layout spec exactly.

**Current State:**
- Generates `devcontainer.json`, `.env`, `README.md`, `.gitignore`
- Creates `runtime_data/` subdirectories
- Creates `opencode.json`

**Actions:**
- [ ] Verify all root-level files are present
- [ ] Verify `.env` contains expected variables
- [ ] Verify `runtime_data/` subdirectories match spec
- [ ] Verify `.gitignore` excludes correct paths
- [ ] Verify `README.md` has correct content

**Acceptance:**
- `.opencode/` matches spec exactly
- Runtime data separated from versioned config
- All documented files present

**Files:**
- `src/opencode_framework/generator.py`
- `tests/test_generator.py`

---

## Step 10: Polish CLI Output and UX

**Goal:** CLI output matches contract exactly.

**Version Output:**
- Framework version
- Framework repo path
- Global config found (bool + path if found)
- Global auth.json found (bool + path if found)

**Init Output:**
- Preflight status
- Worktree/branch creation status
- Generation status
- Launch command
- Note about opencode auto-start

**Actions:**
- [ ] Review all typer.echo/secho calls
- [ ] Ensure error messages are consistent
- [ ] Ensure success messages match contract
- [ ] Remove any debug/extra output
- [ ] Add tests for output format

**Acceptance:**
- Output matches documented format
- No extra output
- Clear, actionable messages

**Files:**
- `src/opencode_framework/cli.py`
- `tests/test_cli.py`

---

## Step 11: Expand Automated Tests

**Goal:** Comprehensive test coverage for all features.

**Unit Tests Needed:**
- [ ] Preflight failure modes
- [ ] Existing `.opencode/` normal vs `--force`
- [ ] Branch suggestion and reuse/create
- [ ] Devcontainer detection and compatibility
- [ ] Optional feature generation
- [ ] Mount semantics in devcontainer.json
- [ ] Docker rootless validation
- [ ] Backup creation

**Integration Tests Needed:**
- [ ] Fresh `init` in real git repo
- [ ] `init --force` backup/regenerate
- [ ] Existing compatible devcontainer
- [ ] Existing incompatible devcontainer
- [ ] Global config/auth present vs absent
- [ ] Branch reuse scenario
- [ ] Worktree creation/cleanup

**Acceptance:**
- All major code paths tested
- Both success and failure cases covered
- Tests can run without git installed (skip gracefully)

**Files:**
- `tests/test_preflight.py` (new)
- `tests/test_devcontainer.py` (new)
- `tests/test_generator.py` (new)
- `tests/test_integration.py` (new)
- `tests/test_git_ops.py` (expand)

---

## Step 12: Validate in Real Environment

**Goal:** End-to-end validation of complete system.

**Prerequisites:**
- Git installed
- Docker installed
- Devcontainer CLI installed
- Pipx installed

**Actions:**
- [ ] Run full test suite
- [ ] Install with `pip install -e .`
- [ ] Test `ocframework` (bare command)
- [ ] Test `ocframework --version`
- [ ] Test `ocframework --help`
- [ ] Test `ocframework init` in fresh repo
- [ ] Inspect generated `.opencode/`
- [ ] Review generated `devcontainer.json`
- [ ] Test `ocframework init --force`
- [ ] Verify backup creation
- [ ] Test with existing devcontainer
- [ ] Test with global config present/absent
- [ ] Test with global auth present/absent

**Acceptance:**
- All manual tests pass
- Generated config is valid
- Launch command works
- No unexpected behavior

---

## Implementation Order

1. **Preflight/tool-name cleanup** (Step 2)
2. **Worktree/`--force` hardening** (Step 3)
3. **Devcontainer incompatible/extend behavior** (Steps 4-5)
4. **Security mounts and Docker rootless validation** (Steps 7-8)
5. **Optional feature completion** (Step 6)
6. **Runtime layout polish** (Step 9)
7. **Tests** (Step 11)
8. **Manual verification** (Step 12)

---

## Definition of Done

- [x] `init` matches documented flow and failure conditions
- [x] `.opencode/` created as worktree-backed config area
- [x] Devcontainer generation supports `from_scratch` and `extend`
- [x] Incompatible devcontainer exits with explanation
- [x] Security/mount rules match docs
- [x] Docker access requires rootless validation
- [x] All optional features generate correctly
- [x] Tests cover happy path and failure cases
- [x] Manual CLI verification passes
- [x] All tests pass (or skip appropriately without tools)

---

## Notes

- Keep each step as a separate commit or PR-sized unit
- Add tests in the same step as the behavior they verify
- Use `pytest.mark.skipif` for tests requiring tools not installed
- Do not expand CLI surface beyond `init` and `--version` in v1
- Follow Python 3.12+ best practices
- Maintain backward compatibility with existing generated configs where possible
