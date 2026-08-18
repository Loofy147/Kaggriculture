# Trace-Driven Reactive Middleware — Build & Stress Report

Date: 2026-08-17

## Verification status

**EXPERIMENTALLY_SUPPORTED:** The revised core architecture passes 12/12 functional tests under pytest.

Covered invariants include:

- deterministic trace fallback
- hard-constraint dominance
- strategic priority arbitration
- overlay exception isolation
- mutation isolation after overlay failure
- partial-execution remainder capture
- bounded history
- returned-action deep-copy isolation
- instance state isolation
- stable tie handling
- randomized safety invariant
- concurrent execution of independent engine instances

## Stress results

### 100,000 sequential decisions

- elapsed: 1.914 s
- throughput: ~52,247 decisions/s
- hard holds: 5,264
- adversarial actions: 7,288
- fallback actions: 0
- retained history: 1,000
- pending actions: 2,703

### 128,000 decisions across 64 independent instances / 16 workers

- elapsed: 2.585 s
- aggregate throughput: ~49,517 decisions/s
- history bound invariant: PASS

### 500,000 sequential decisions

- elapsed: 12.446 s
- throughput: ~40,172 decisions/s
- hard holds: 26,316
- adversarial actions: 36,437
- fallback actions: 0
- retained history: 1,000
- pending actions: 13,514

## Important finding

**OPEN / DESIGN ISSUE:** `pending_actions` is append-only in the current recovery implementation. The stress run therefore shows linear growth in queued remainders.

This is not a correctness failure of the current tests, but it is a production-risk memory/backpressure issue. A real execution adapter needs an explicit queue lifecycle:

`enqueue -> eligibility -> retry -> success/final failure -> removal`

and probably a capacity/backpressure policy.

## Concurrency boundary

The current engine is **instance-local, not shared-instance thread-safe**. The stress test validates many independent engines running concurrently. It does not claim that multiple threads may safely call `act()` on the same `ReactivePipeline` object.

A shared-instance deployment needs one of:

- a lock around the decision cycle,
- an actor/event-loop model,
- or immutable state snapshots with serialized state commits.

## First bug found and fixed

The first stress-oriented mutation-isolation test exposed that `Intent(frozen=True)` did not make its nested action dictionary immutable. An overlay could mutate the dictionary and then fail, corrupting the canonical baseline.

The fix is to give every overlay a deep-copied intent and to deep-copy accepted proposals before arbitration.

## Current architectural status

**GOOD RESEARCH/PROTOTYPE BASELINE.**

Not yet production-grade because execution queue lifecycle and shared-instance concurrency semantics remain intentionally unresolved.
