# Mizune Domain Context

Mizune is a personal AI assistant, not a chatbot. The product promise is that Mizune understands the user's context, chooses the right capability, executes safely, reports progress, and learns from outcomes.

## Domain Terms

- Mizune: the assistant persona and product experience.
- Assistant Runtime: the backend loop that receives input, decides intent, executes capabilities, streams progress, and records memory.
- Capability: a user-visible thing Mizune can do, such as app control, WhatsApp, Gmail, web research, code review, memory recall, scheduling, or file organization.
- Action: one concrete operation performed by a capability, such as opening an app, sending a message, capturing the screen, or writing a note.
- Task: a user request that may require one or more actions.
- Execution Trace: the structured record of what Mizune planned, attempted, succeeded at, failed at, and why.
- Dashboard: the control room for Mizune. It should show status, tasks, capabilities, memory, integrations, and approvals, not just chat.
- Approval: an explicit user decision required before dangerous, irreversible, external, or privacy-sensitive actions.
- Integration: a connected external system such as WhatsApp, Gmail, Obsidian, GitHub, browser, Android, or local apps.
- Memory: stored facts, conversations, traces, preferences, skills, and summaries that affect future behavior.
- Skill: a dynamic executable extension loaded by Mizune at runtime.
- Cortex: the long-term memory and event data layer.
- Kernel Stream: low-level system and attention events that help Mizune understand current context.

## Product Principles

- Mizune should do the task, not only describe how to do it.
- Mizune should show progress while working.
- Mizune should ask for approval only when the action has real risk.
- Mizune should recover from failures and explain the next useful step.
- Mizune should keep one source of truth for each capability.
- Mizune should be safe by default for command execution, file writes, messaging, and tokens.
- The dashboard should make invisible agent work visible.

