# Human conversation session — red/green gate — 2026-10-11

Base release: MedBrain 0.5.1-field-rc build 42, branch feat/medbrain-native-streaming-spike-20261011.
No user corpus or existing SQLite history was changed.

Cycle A:
- Added HumanConversationAcceptanceTest as a separate RED-GATE commit 0070bbf1.
- Covers 12 ambiguous ellipses, 6 explicit topic switches, medical discussion interrupted
  by identity question and thanks, human social remarks with vs without GGUF, and a
  continuation prompt with long prior history.
- Previous failure mode: "Pourquoi ?" / "Je n'ai pas compris" / "Explique-le autrement"
  fell out of the conversation context, or a later "merci" displaced the old clinical topic.
- Router now explicitly treats a bounded set of *discourse dependent* phrases as
  follow-ups, recognizes population modifiers, yet retains explicit new diseases as new topics.
- With neural model available, "tu sais quoi?" and "hein?" now go through the real
  general-chat dialogue rather than a fixed canned answer. No-model fallback remains.
- Topic anchoring excludes product metadata, greetings and social acknowledgements.
- Automated tests are not a simulated Qwen conversation. They prove only deterministic
  routing, document isolation, UI/SQLite and prompt-construction contracts.

Cycle B — 14 near-identical topic-switch/context cases and substantive-answer anchoring: medical names override contextual prefixes, but generic treatment/age/example questions remain tied to prior medical subject. Social fast acknowledgements are not used as the last substantive clinical explanation. No response quality claims beyond deterministic simulations.
