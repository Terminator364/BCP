# BCP Cross-Project Field Binding Batch — R3

Date: 2026-10-06  
Status: REPOSITORY_PACKAGE / NOT EXECUTED / NOT FIELD CERTIFIED

## Purpose

This is the single batched field-observation package that follows Phase 8 repository
qualification. It exists to discover local roots/runtime evidence that repository sources
cannot prove.

It is **not** a migration script and **not** an updater.

## Scope

Projects:
- BCP;
- TLIB;
- Excellentia;
- Delivery;
- BuildHub;
- PC COMMAND;
- PhoneMouse;
- P2PCR95.

## Probe

Script:

`windows/BCP_R3_CROSS_PROJECT_FIELD_BINDING_PROBE.ps1`

Default receipt:

`%LOCALAPPDATA%\ChatGPT_ManagedApps\bcp\evidence\BCP_R3_CROSS_PROJECT_BINDING_LATEST.json`

Schema:

`schemas/bcp_cross_project_field_binding_probe_v1.schema.json`

## System safety boundary

The probe may read:
- Win32 process inventory;
- listening TCP endpoints;
- scheduled-task definitions;
- Windows services;
- HKCU Run startup entries;
- bounded top-level directory candidates;
- physical RAM/pagefile/system-drive headroom;
- localhost BCP `/health`.

The probe does **not**:
- stop/start/restart processes;
- change scheduled tasks;
- modify services;
- modify registry values;
- install/update/uninstall software;
- reboot/shutdown Windows;
- recursively crawl the disk;
- perform remote network discovery;
- promote a binding.

The only optional write is the resulting evidence JSON. `-NoFileWrite` disables even
that write and emits JSON to stdout only.

## Privacy / secret handling

Command lines and task arguments can contain credentials. Before they are serialized the
probe redacts:
- Telegram bot token shapes;
- Bearer tokens;
- common API/access/auth token keys;
- secret/password-like key/value arguments;
- secret-bearing query-string parameters.

The evidence package must never be treated as a secret-export mechanism.

## Binding truth law

A matching directory name is only a local-root candidate.

A matching process is not installation proof.

A matching listener is not project authority.

A provider-synced directory is not hot transactional-state authority.

The Phase 8 repository bindings remain unchanged until BCP consumes this receipt and
performs exact readback/capability checks.

Every project result therefore leaves:

`binding_decision = READBACK_REQUIRED`

and:

`field_certified = false`.

## Why one batch

The construction contract requires field work to be batched because:
- Desktop Commander is last-mile/metered;
- the target PC is resource constrained;
- repeated diagnostics waste quota and user time;
- repository/simulation gates should settle first.

This package collects all unresolved project binding evidence in one Windows observation
campaign.

## Acceptance before execution

Repository package PASS requires:
1. PowerShell syntax parses;
2. static guard finds no system-mutation commands;
3. no recursive filesystem crawl;
4. secret-redaction rules exist;
5. only localhost BCP health is network-probed;
6. receipt schema parses;
7. Phase 8 contract regression remains green.

## Execution gate

Actual execution is permitted only after the Phase 8 construction branch is integrated
and current-head reconciliation confirms no newer field package supersedes this one.

Execution does not itself certify the projects. It produces evidence for the next
readback/adapter-binding decision.
