# Autonomy Planner 0.2

## Purpose

The planner connects the existing persistent GoalManager to the policy-governed
AutonomyEngine. It chooses dependency-ready steps already authored by the
operator and submits a bounded proposal batch to the engine.

## Cycle

1. Read active goals from GoalManager.
2. Ask GoalManager for pending steps whose dependencies are completed.
3. Select in stable goal/step insertion order, up to the configured limit.
4. Submit the allowlisted `goal.start_step` internal action to AutonomyEngine.
5. The trusted callback rechecks readiness and atomically transitions the
   selected step through GoalManager's existing status API to `in_progress`.
6. AutonomyEngine records the request and result in its SQLite audit log.

## Runtime API

```python
result = ai.run_autonomy_cycle()
preview = ai.autonomy_planner.preview()
state = ai.autonomy_planner.status()
```

The cycle is explicit and synchronous. It does not start a background worker.
The default planner limit is one step per cycle, bounded again by the engine's
policy limit.

## Safety and semantics

- The planner cannot invent goals or steps; it only reads operator-authored
  GoalManager records.
- Only dependency-ready pending steps are proposed.
- The callback revalidates readiness immediately before the state transition.
- Only the internal, low-risk `goal.start_step` callback is registered.
- No shell, network, filesystem mutation outside GoalManager, model download,
  training, or external action is exposed.
- A step is marked `in_progress`, never `completed`. Completion requires an
  explicit later result/verification path.
- No LLM output is treated as an executable plan.
- The cycle is bounded and does not create threads or run continuously.
- Local/external actions remain unregistered and subject to the AutonomyEngine
  approval policy.

## Not implemented yet

This release is a deterministic goal selector and state-transition bridge,
not an end-to-end task executor. It does not yet decompose natural-language
goals, observe external task outcomes, verify artifacts, retry work, or mark
steps completed. Those capabilities require separate evaluators, typed action
contracts, idempotency, cancellation, and tests before they can be enabled.
