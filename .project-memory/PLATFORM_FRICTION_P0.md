# API / BCP — Platform Friction Design Requirement

Status: P0 PRODUCT REQUIREMENT
Adopted: 2026-09-19

## Problem

Repeated additional-verification holds and other platform interruptions can add significant wall-clock delay to long technical sessions. The project must not depend on uninterrupted ChatGPT reasoning to remain productive.

## Required design response

API/BCP MUST:
- externalize project state before long work;
- run device/build jobs as bounded durable jobs when appropriate;
- checkpoint after every committed mutation;
- support ACTIVE/STANDBY conversation continuity;
- keep a single-writer lease with monotonic fencing;
- expose running job state independently of the originating conversation;
- use staged/atomic recovery rather than broad rescans;
- distinguish verification hold, 429, tool transient and real project failure;
- preserve legitimate technical scope durably;
- never use the user as the telemetry bus when machine-readable evidence exists.

## Non-goal

The system must not attempt to defeat, suppress or bypass platform safety mechanisms. The goal is continuity, lower ambiguity and reduced wasted time.

## Priority

Until these continuity mechanisms are FIELD_VERIFIED, they take precedence over expanding API/BCP into additional integrations that would increase interruption exposure.
