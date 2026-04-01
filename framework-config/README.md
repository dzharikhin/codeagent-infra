# OpenCode Framework Configuration

This directory contains framework-level configuration templates and defaults.

These files are mounted read-only into devcontainers created by the framework,
and the `OPENCODE_CONFIG` environment variable points to the mount path.

## Usage

Framework config is automatically discovered and mounted when running
`ocframework init`. The mount path inside containers is:
`/opt/ocframework/config`

## Structure

Add configuration templates, default settings, or shared resources here
that should be available to all projects using this framework.
