# Shared Alert Sound Files

Place the following MP3 sound files in this directory for bundling with the Chrome extension:

- **alert-up.mp3** - Played when an UP signal alert is triggered
- **alert-down.mp3** - Played when a DOWN signal alert is triggered
- **alert-generic.mp3** - Played for general notifications

These files should be identical to those in `backend/static/sounds/`. The extension build process copies them into the extension's assets directory.

These are ALERT-ONLY sounds. They notify the user of detected signals and do NOT indicate trade execution.

## Sourcing Sounds

You can source free notification sounds from:
- freesound.org (CC0 licensed)
- mixkit.co (free sound effects)
- Or generate simple tones using Audacity or ffmpeg
