"""Shared competitor discovery / validation targets (UI + prompts + post-processing)."""

# Final output: 2 same-tier + 2 competitors ahead (4 total).
SAME_LEVEL_COUNT = 2
ONE_LEVEL_ABOVE_COUNT = 2
TOTAL_COMPETITOR_COUNT = SAME_LEVEL_COUNT + ONE_LEVEL_ABOVE_COUNT
INITIAL_CANDIDATE_TARGET = TOTAL_COMPETITOR_COUNT

# Per prompt: cited by ≥ this many distinct AI engines (strict validation uses engines only).
MIN_ENGINE_CITATIONS = 2
MIN_CITATION_HITS_PER_PROMPT = 2
MIN_ENGINE_CITATIONS_PER_PROMPT = MIN_ENGINE_CITATIONS

# Expansion batch when strict targets are not yet met.
EXPANSION_SAME_LEVEL_BATCH = 2
EXPANSION_ONE_LEVEL_ABOVE_BATCH = 2
EXPANSION_BATCH_SIZE = EXPANSION_SAME_LEVEL_BATCH + EXPANSION_ONE_LEVEL_ABOVE_BATCH

# Keep fetching until strict 2+2 × multi-AI is satisfied (do not stop early).
# Post-scan expansion cap (keeps report responsive; strict 2+2 may stay incomplete).
MAX_COMPETITOR_VALIDATION_ROUNDS = 2
