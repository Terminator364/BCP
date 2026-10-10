# MedBrain streaming backend experiment — 2026-10-11
Base: validated 0.5.0 internal, e73d318c2e19e14e1c3045e77284e4dadebb5156.
Branch: feat/medbrain-native-streaming-spike-20261011. This experiment must NOT overwrite the validated baseline.

## Scope A: interface and vendor parity
- Introduces InferenceBackend + NeuralRequest / NeuralResult / BackendCapabilities.
- The original BlockingVendorBackend retains warm weight caching and identical model parameters/prompt, still has synchronous Llama.complete with cache cleared by vendor each call.
- Introduces an IPC PARTIAL event contract guarded by safeStreaming = tokenDeltas AND hardNonThinking. Existing blocking backend advertises all capabilities false and sends NO fake partial events.
- The Android UI is not consuming partial events yet. The existing chat behavior and 0.5.0 stable branch remain unchanged.

## Next experimental gate
- Implement native llama.cpp token callback backend (upstream official Android example), actually negotiated hard Qwen3 non-thinking chat templates, proof of no internal thinking leaked in token stream.
- Introduce UI rate-limited partial accumulator with request_id binding and no patient text in logs.
- Measure first token P50/P95, warmed second turn and RAM/temperature with 1.7B GGUF on Galaxy S21 FE. Demonstrate persistent KV rather than merely warm weights.
- Recheck same signing key, SQLite survival, original books and offline study before release. NEVER tag this spike as installable.

## Scope B: UI protocol / future streamed token reception
- Added `SafeStreamBuffer`: only same request_id + provider-asserted safe_output may be displayed, recent text limited to 2500 chars, refresh <= approx. 3 times/s. Wrong-thread/unsafe private text cannot reach Chat preview.
- Activity wires PARTIAL IPC into request-specific progress callback and queues it with the original request; opening another thread does not cause its tokens to render there. Final REPLY continues to be cleaned, persisted and committed as before.
- Critical: current BlockingVendorBackend emits ZERO PARTIAL messages. This code alone does not improve time to first token; it safely prepares the UI for a truly streaming, hard-nonthinking native model.
