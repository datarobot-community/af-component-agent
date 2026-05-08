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
| APPS-Customer Engineering | @carsongee | |

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

### B4. User-facing documentation

**Relationship to other rules**

- User-visible changes may require both **B2** (CHANGELOG) and updates under this section. When both apply, **mention them in one comment thread** so authors get a single checklist.
- If the PR falls under critical areas that already require DOC involvement (**A1**, **A10**, **A15**, **A20**, or others with explicit DOC requirements), **do not duplicate** generic B3 boilerplate. Reference that section and only add B3-specific gaps (for example exact README paths).

**When to assess**

Decide whether the changes would impact or require updates to user-facing documentation in this repository (for example README files, setup or deployment guides, architecture or customization docs aimed at users, or in-repo descriptions of behavior, configuration, or interfaces).

**Changes that usually do not require documentation updates** (use judgment; avoid nagging when the diff is limited to cases like these):

- Comments-only, internal refactors, or test-only changes with no user-facing behavior
- Tooling or dependency bumps that do not change documented setup, configuration, or workflows in this repo
- Fixes that do not alter documented commands, defaults, env vars, or public surfaces described in-repo

**How authors can satisfy this rule**

- Include the documentation updates in the PR, **or**
- Add a **Documentation** line to the PR description (or a single top-level PR comment), for example: `Documentation: updated README.md and agent/AGENTS.md` or `Documentation: N/A — no user-visible change` or `Documentation: deferred — [DOC-123](https://…) will cover new MCP env vars.`
- When that line is present and substantive, treat it as meeting the justification or deferral path **unless the diff clearly contradicts** it (for example new user-facing flags with no doc mention and no deferral).
- For **deferral**, a **linked DOC ticket** plus a **short scope** of what documentation will follow is preferred over an unexplained omission.

**Discussion**

For unclear cases, authors may contact **DOC** stakeholders (see the Stakeholders table) or raise the question in the PR / issue tracker for guidance.

**BugBot behavior when documentation likely needs updates** and the PR has no doc changes and no acceptable justification or deferral:

- Leave **one consolidated comment** on the PR (or append to an existing documentation thread); do not file multiple comments with the same ask.
- In that comment, **name specific files or topics** that appear affected (for example `README.md` install steps, `agent/AGENTS.md` conventions) so the author has an actionable checklist.
- Ask the author to update the documentation, add a **Documentation** line with justification, or add a **linked DOC ticket** with scope for deferral.

### B10. Use `git rename` when moving files

`copier` relies on `git` history when it updates component and merges with local changes. Recently we have moved `agent.py` → `myagent.py`, and this broke downstream templates, so we had to add a custom migration.

### B11. Dependency discipline

Every new dependency added to `pyproject.toml` or `uv.lock` should be justified. Review PRs that introduce new packages and verify they are actually needed.

In this repo, unwanted transitive packages are not listed under uv’s `exclude-dependencies`. Instead, `template/{{agent_app_name}}/pyproject.toml.jinja` uses `[tool.uv] override-dependencies` with impossible environment markers (for example `"<package>; sys_platform == 'never'"`) so the resolver drops those dependencies. Compatibility and CVE pins live in the same `override-dependencies` block. Do not remove exclusion overrides or re-add blocked packages without TECHLEAD approval.

Current blocked packages (see `# Excluded` in `override-dependencies`):

| Package | Reason |
|---|---|
| `gevent` | Not used |
| `onnxruntime` | Not used |
| `fastembed` | Not used |
| `langchain-milvus` | Unused; CVE exposure |
| `pymilvus` | Unused; CVE exposure |
| `diskcache` | Unused; CVE exposure |
| `annoy` | Unused; build issues |
| `uv` | Not a runtime dependency |
| `build` | Python build system pulled in by crewai; runtime unnecessary |
| `kubernetes` | K8s client pulled in by crewai-tools; not used |
| `stagehand` | Playwright web automation pulled in by crewai-tools; not used |
| `pytube` | YouTube downloader pulled in by crewai-tools; not used |
| `youtube-transcript-api` | YouTube transcripts pulled in by crewai-tools; not used |
| `lancedb` | Optional vector DB pulled in by crewai; not used |
| `openpyxl` | Excel parser pulled in by crewai-tools; not used |
| `python-docx` | Word doc parser pulled in by crewai-tools; not used |
| `llama-index-cli` | CLI tool pulled in by llama-index; not needed at runtime |
| `scikit-network` | Graph analysis pulled in by ragas; not used |
