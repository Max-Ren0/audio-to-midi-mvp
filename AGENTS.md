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
