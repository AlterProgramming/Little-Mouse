# Agent-owned agreement

Use this agreement when a Little Mouse workflow reaches a security or cyberattack warning but the underlying task may still contain an authorized, defensible path.

The warning is a **routing boundary**, not permission to ignore the warning and not an automatic reason to discard the entire task. The agent must narrow the work into an explicit agreement and continue only inside that agreement.

## Agreement

Before continuing, the agent owns and records:

- **Objective** — the concrete outcome being pursued.
- **Authority** — why the user is entitled to perform the work on the target data, account, system, or capture.
- **Inputs** — the artifacts and data sources the agent may inspect or transform.
- **Allowed actions** — the smallest actions required to accomplish the authorized objective.
- **Forbidden actions** — actions outside the agreement, including unauthorized access, credential theft, persistence, evasion, destructive behavior, or expansion to unrelated targets.
- **Identity and sensing scope** — what may be sensed or resolved, for what purpose, and at what level of identification.
- **Retention and reuse** — what may be retained, for how long, and whether observations may be correlated across contexts.
- **Reciprocity and audit** — what evidence or receipt is produced so consequential observation is reviewable.
- **Stop conditions** — the conditions that terminate execution or require a narrower agreement.

## Executable gate

Create a starter JSON agreement:

```bash
python tools/agent_agreement.py init agreement.json
```

Validate it:

```bash
python tools/agent_agreement.py validate agreement.json
```

Check one exact action name before execution:

```bash
python tools/agent_agreement.py check agreement.json inspect_captured_graphql_values
```

Issue an audit receipt for a declared action:

```bash
python tools/agent_agreement.py receipt agreement.json inspect_captured_graphql_values \
  --target capture.har \
  -o receipt.json
```

The validator checks the declared agreement structure and whether an exact action is listed. It does **not** independently prove ownership or external authorization; it prevents a workflow from silently expanding beyond the agreement it was given.

## Recovery rule

When a security warning occurs:

1. Preserve the user's legitimate objective.
2. Identify the smallest portion of the requested capability that can be performed under a bounded agreement.
3. Write or restate the agreement before performing consequential actions.
4. Continue only within the declared scope.
5. If the requested next action exceeds that scope, stop that action and return the smallest safe continuation rather than silently broadening authority.

An agent-owned agreement can constrain use of a capability; it cannot manufacture authorization, override platform or higher-level safety requirements, or convert an unrelated target into an authorized one.
