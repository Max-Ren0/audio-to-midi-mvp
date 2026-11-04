# Project instructions

## Scope
- Build an audio/video-to-multitrack-MIDI MVP. Validate transcription quality before adding a frontend.
- Read CONTEXT.md before work and update it at milestones.
- Keep research claims separate from measured results.

## Version management
- The user authorizes saving and pushing each usable project version to the private GitHub repository.
- Before changing existing code, inspect status and create a snapshot commit of relevant project changes. Do not include unrelated changes or secrets.
- At each completed usable milestone: run appropriate checks, review the staged changes, commit with a concrete description, and push to origin.
- Record changes and validation in CHANGELOG.md and CONTEXT.md.
- Tag meaningful milestones with semantic versions. Planning tags use prerelease names such as v0.0.0-planning; they do not imply a working MVP.
- Use main for verified milestones and short-lived branches for larger experiments. Avoid force pushes and rewritten published history.
- If pushing fails, preserve local commits and report the failure; do not claim cloud synchronization succeeded.
- Do not upload credentials, private input media, downloaded model weights, temporary competitor resources, or generated bulk results.
- This is an agent workflow during active project work, not a background filesystem watcher.

## Independent verification
- The main agent completes a checkable version and freezes it as a Git commit before starting an independent verification subagent.
- The verifier checks original requirements and actual artifacts, does not edit project files, and does not assume the main agent’s claims are correct.
- Check omissions, factual or logical errors, and key boundaries. Report specific file locations and evidence; only run checks that preserve existing data and services.
- The main agent evaluates each finding, fixes confirmed issues, freezes a new version, and re-verifies affected parts. Bind every review to a commit and artifact hashes when artifacts are not tracked.
- Final delivery states what was verified, what was found and resolved, and remaining uncertainties.

## Current target override (2026-10-15)
- Ignore vocals from now on. Default target and acceptance cover piano, acoustic guitar, electric guitar, bass, drums, and strings. Input may contain vocals; vocal output is not required. Preserve historical artifacts.

## Canonical project location
- All project files belong under `/Users/ringscherry/Desktop/Codex项目/吉他产品/`. Repository: `音频转MIDI/`; original media/product docs: sibling `v0.0/` and Pages files; early planning: sibling `历史规划/`.
- New projects belong under `/Users/ringscherry/Desktop/Codex项目/<项目名>/`, never in date-based project folders.
- Old date-based paths are compatibility symlinks only. Preserve historical manifests/hashes; do not rewrite frozen artifacts solely to replace paths.
