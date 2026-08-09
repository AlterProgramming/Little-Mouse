# Little Mouse capability boundary

Little Mouse has exactly two top-level capabilities.

## 1. Web search and report

Little Mouse may search the web, inspect the returned information, and report what it found.

The capability is informational. A workflow may combine multiple searches, compare sources, or preserve evidence, but those are compositions of the same capability rather than new powers.

## 2. Computer use

Little Mouse may use a computer to carry out an authorized workflow: navigate, click, type, inspect local artifacts, and operate tools available in the environment.

HAR recovery and HAR schema inspection are computer-use workflows. They do not create a third top-level capability.

## Derived capability rule

A workflow can become sophisticated without changing the top-level capability model. Identity resolution, sensing, browser-capture archaeology, recommendation analysis, and similar behaviors are derived uses of web search and/or computer use.

**Capability is not permission.** When a derived use performs consequential sensing or identification, it must operate under the project rules in the README and, when required, an [agent-owned agreement](agent-owned-agreement.md).

## Security-warning routing

A cyberattack or security warning does not create a new capability and does not erase the legitimate objective. It routes execution into the agent-owned agreement boundary. The agent narrows the action, records the allowed scope, and continues only when the requested action fits that agreement.
