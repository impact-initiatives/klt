## Pull Request

### Type
<!-- Check one -->
- [ ] Feature
- [ ] Bug Fix
- [ ] Refactor
- [ ] Documentation
- [ ] Tests
- [ ] Chore

### Component
<!-- Check all that apply -->
- [ ] Pipeline orchestration
- [ ] Resource (kobo_asset, kobo_submission, etc.)
- [ ] Model / Data validation
- [ ] Transformation (EAV, data processing)
- [ ] CLI
- [ ] Tests
- [ ] Documentation

### Description
<!-- Describe what changed and why -->



### Breaking Changes
<!-- Check one -->
- [ ] No breaking changes
- [ ] Yes - breaking changes (describe migration path below)

<!-- If breaking changes, describe the impact and migration guide -->



### Data Impact
<!-- Does this affect existing pipeline data, cursor state, or schema? -->
- [ ] No impact on existing data
- [ ] Changes cursor behavior
- [ ] Changes data schema
- [ ] Changes data transformation logic
- [ ] May require pipeline state reset

<!-- If data impact, describe what users need to do -->



### Testing
<!-- Check all that apply -->
- [ ] Added new tests
- [ ] Updated existing tests
- [ ] All tests pass (`uv run pytest`)
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] Tested with actual KoboToolbox API
- [ ] Tested with sample data only

### Cursor Behavior
<!-- If this PR changes incremental loading, describe the cursor behavior -->
<!-- Leave blank if not applicable -->



### Documentation
<!-- Check all that apply -->
- [ ] Updated README.md
- [ ] Updated AGENTS.md
- [ ] Updated docstrings
- [ ] Updated .dlt/config.toml examples
- [ ] No documentation changes needed

### Additional Context
<!-- Any other information, screenshots, or notes for reviewers -->
