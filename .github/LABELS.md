# GitHub Labels Reference

This document describes all labels used in the KLT (KoboToolbox Pipeline) project.

A streamlined set of 15 labels for effective issue management without overwhelming complexity.

## Label Categories

### Type Labels (6)
Primary classification of issues and PRs.

| Label | Color | Description | Usage |
|-------|-------|-------------|-------|
| `bug` | `#d73a4a` | Something isn't working as expected | Use for functional bugs, errors, unexpected behavior |
| `enhancement` | `#a2eeef` | New feature or improvement | Use for feature requests and enhancements |
| `data-quality` | `#ff6b6b` | Data missing, duplicate, or incorrect | Use for data integrity issues |
| `documentation` | `#0075ca` | Documentation improvements | Use for README, docstrings, guides |
| `question` | `#d876e3` | Help or clarification needed | Use for configuration help, how-to questions |
| `refactor` | `#fbca04` | Code improvement without behavior change | Use for code quality improvements |

### Priority Labels (3)
Indicate urgency. No label = medium priority.

| Label | Color | Description |
|-------|-------|-------------|
| `priority:critical` | `#b60205` | Data loss risk, production blocking, security issue |
| `priority:high` | `#d93f0b` | Important but not blocking, significant bug |
| `priority:low` | `#0e8a16` | Nice to have, minor issue |

### Special Labels (6)
Important flags for critical or specific issues.

| Label | Color | Description |
|-------|-------|-------------|
| `data-loss-risk` | `#b60205` | Potential for data loss (highest attention) |
| `breaking-change` | `#e11d21` | Breaking change requiring migration |
| `cursor-issue` | `#5319e7` | Incremental loading/cursor behavior problems |
| `kobo-api` | `#5319e7` | Related to KoboToolbox API specifics |
| `good-first-issue` | `#7057ff` | Good for newcomers |
| `needs-decision` | `#d4c5f9` | Design or approach decision needed |

## Common Label Combinations

### Critical Issues
Issues requiring immediate attention:
- `data-loss-risk` + `cursor-issue` + `priority:critical`
- `bug` + `data-quality` + `priority:critical`

### Feature Development
- `enhancement` + `priority:high`
- `enhancement` + `breaking-change` + `needs-decision`

### Data Quality Problems
- `data-quality` + `cursor-issue`
- `data-quality` + `kobo-api`

### Configuration Issues
- `question` + `documentation`
- `documentation` + `good-first-issue`

## Labeling Guidelines

### When to Use `data-loss-risk`
Apply this label when:
- Data has been permanently lost and cannot be recovered
- A bug could cause future data loss
- Cursor issues skip or miss data
- Deduplication is failing

### When to Use `cursor-issue`
Apply this label when:
- Incremental loading not working correctly
- Cursor advancing incorrectly or not advancing
- Data being skipped or duplicated due to cursor behavior
- Issues with `date_modified` or `_submission_time` cursors

### When to Use `breaking-change`
Apply this label when:
- API signatures change
- Configuration format changes
- Resource behavior changes significantly
- Migration is required for existing users

### When to Use Priority Labels

**Critical**:
- Production is down or blocked
- Data loss has occurred or is imminent
- Security vulnerability

**High**:
- Significant bug affecting functionality
- Important feature for major use case
- Performance degradation

**No label (Medium)**: Default priority for most issues

**Low**:
- Nice-to-have features
- Minor cosmetic issues
- Low-impact bugs

## Why These Labels?

This streamlined set focuses on:
- **Type labels** cover the main categories of work
- **Priority labels** highlight urgency (critical, high, low; medium = no label)
- **Special labels** flag the most important technical concerns specific to this pipeline:
  - `data-loss-risk` - Critical for data integrity
  - `cursor-issue` - Most common technical problem in dLT pipelines
  - `kobo-api` - External dependency issues
  - `breaking-change` - Impact on users
  - `good-first-issue` - Community contribution
  - `needs-decision` - Unblocks discussion

Components, detailed scopes, and workflow status are better captured in issue descriptions and GitHub's built-in features (assignees, milestones, projects).

## Related Documentation

- Issue Templates: `.github/ISSUE_TEMPLATE/`
- Pull Request Template: `.github/PULL_REQUEST_TEMPLATE.md`
- Setup Script: `setup-labels.sh` - Run this to create all labels in your repository
