# Alert Sound Files

Place the following MP3 sound files in this directory:

- **alert-up.mp3** - Played when an UP signal alert is triggered
- **alert-down.mp3** - Played when a DOWN signal alert is triggered
- **alert-generic.mp3** - Played for general notifications

These are ALERT-ONLY sounds for monitoring purposes. They indicate that a signal has been detected, NOT that a trade has been executed.

## Requirements

- Format: MP3
- Duration: 0.5 - 2 seconds recommended
- File size: Keep under 100KB for fast loading

## Fallback

If sound files are not present, the Chrome extension will use a Web Audio API oscillator-based fallback beep with different frequencies for UP (ascending tone) and DOWN (descending tone) alerts.
