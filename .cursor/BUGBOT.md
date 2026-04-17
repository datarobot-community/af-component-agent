# BugBot Review Instructions

You are a code review bot. When reviewing pull requests in this repository, use the guideline below to identify issues and leave comments. The guideline defines critical areas that require sign-offs, general rules for public repositories, changelog expectations, and file operation best practices.

For each violation you detect, leave a comment with a clear title and a message referencing the relevant section of the guideline.

Full guideline source: https://datarobot.atlassian.net/wiki/spaces/BUZOK/pages/7305920528/REVIEW+BEFORE+COMMIT+Working+with+agentic+starter+application+and+its+components

---

# REVIEW BEFORE COMMIT: Working with agentic starter application and its components

## Background

Currently being migrated to https://github.com/datarobot-community/app-framework/tree/main/docs

Changes to datarobot/recipe-datarobot-agent-application proves to be high-impact to our customers, and because of the dynamic nature of the industry we do not make all changes under reviewed PBMPs with PRODUCT and DOC sign-offs: we have to pro-actively add improvements based on feedback. Therefore we need to know which changes are necessary to be reviewed/communicated with stakeholders.

The latest documentation requirement is to include it in the `af-component` themselves: https://github.com/datarobot-community/app-framework/blob/main/docs/src/design/documentation.md

This document outlines common guidelines which should be applied when making change or reviewing PRs in datarobot/recipe-datarobot-agent-application and related components:

- https://github.com/datarobot-community/af-component-agent
- https://github.com/datarobot-community/af-component-datarobot-mcp
- https://github.com/datarobot-oss/datarobot-genai
- https://github.com/datarobot-oss/cli

### Related

Application Framework Design Principles. Also:

- App Framework Overview and Architecture
- Template Customization and Maintenance Strategy
- https://github.com/datarobot-community/app-framework/tree/main/docs/src/design

## Stakeholders

| Stakeholder | Person | Approval |
|---|---|---|
| PRODUCT | @dr-nate-daly-pm | |
| TECHLEAD | @tsdaemon | |
| DOC | @smagee-robot @jendavies | |
| APPS-Customer Engineering | @carsongee @luke-shulman @zach-ingbretsen | |

## A. Critical areas

### A1. Renaming and wording

Requires: PRODUCT sign-off, DOC review

Template names, component names, primary module names (`myagent.py`) are considered highly important properties of UX. Their names are approved by PRODUCT, and any changes should be reflected in documentation.

### A2. Backward compatibility

Requires: TECHLEAD sign-off, PRODUCT sign-off, DOC review

See Backward compatibility of agentic application templates for more context.

### A10. Changes to `dr start`

Requires: PRODUCT and @carsongee sign-off, DOC review

`dr start` is the key part of UX of agentic starter application, and any changes to it have to be reviewed by PRODUCT ( @dr-nate-daly-pm ). This includes direct changes to `task start`, and indirect changes:

- new configuration options in `agent` or `mcp`
- Change to `dr start` logic in CLI itself

Tired waiting review from @carsongee ? Try splitting your PR, and deliver critical changes separately!

We **SHOULD BE** mindful about the number of questions we are asking from users in components configuration, and try reducing them as much as possible. Related initiatives:

- Component discovery
- Do not ask optional question: TBD

### A11. Adding or removing tasks in all components

Requires: @carsongee sign-off, DOC review

`task` is essentially our TUI, and we should be mindful adding or removing them as this may be just as disruptive as adding or removing GUI elements.

### A15. Adding or removing tools, prompts, resources to MCP

Requires: PRODUCT sign-off, DOC review

MCP is a key element of an agent which defines what agent can or can not do. Adding new tools (or other resources) without restrain will lead to poor experience, hence only vetted (read: most important) tools should be added to the default set available OOTB.

### A20. Changes to agent interface

Requires: PRODUCT review, DOC review

`myagent.py` is a core part of an agent definition, and changing it means users will have to migrate their agents if they want to merge upstream. This also means our documentation have to be updated to reflect a new interface for users.

## B. General guidelines

### B1. Assume public

Repositories linked at the top are either public, or meant to become public. Therefore:

- Do not include internal code, proprietary logic, or private repository references.
- Avoid leaking internal architecture, infrastructure details, or security mechanisms.
- Keep comments, README and any other communication language civil, polite, and free of internal references

### B2. Update CHANGELOG

- Use past tense
- When `CHANGELOG.md` is present, and your change looks like it should be communicated with users, please add it.
- Do not add every change: `Added .woff2 and .woff and .js files to fastapi_server/static/.gitignore` is not important to our users.
- When bumping child components, list all the changes:

```
- Updated agent component from 11.6.3 to 11.6.10:
  - Migrated to a new interface
  - Refactored agent infra concurrency configuration
  - Fixed header forwarding in LangGraph
  - Added debugpy for debugging in IDE
```

### B3. Update `docs` and `AGENTS.md` when necessary

Each component should store its documentation in `docs` folder and provide context for agents editing in `AGENTS.md`. After making change please apply your best judgement if changes are necessary. If they are, tag DOCs for review.

Use https://github.com/datarobot-community/app-framework/tree/main/skills/datarobot-app-framework-doc-update to generate or review documentation changes to make sure they are up to the standards.

### B10. Use `git rename` when moving files

`copier` relies on `git` history when it updates component and merges with local changes. Recently we have moved `agent.py` → `myagent.py`, and this broke downstream templates, so we had to add a custom migration.

### B11. Dependency discipline

Every new dependency added to `pyproject.toml` or `uv.lock` should be justified. Review PRs that introduce new packages and verify they are actually needed.

`pyproject.toml` contains an `exclude-dependencies` list under `[tool.uv]`. These packages are intentionally excluded because they are unused transitive dependencies pulled in by upstream packages. Do not remove entries from this list or re-add these packages without TECHLEAD approval.

Current exclusions:

| Package | Pulled in by | Reason |
|---|---|---|
| `uv` | build tooling | Not a runtime dependency |
| `langchain-milvus` | langchain ecosystem | Unused vector store integration |
| `pymilvus` | langchain-milvus | Transitive dep of langchain-milvus |
| `flask` | nvidia-nat-core 1.6.0 | Only used in NAT examples, not core library code |
