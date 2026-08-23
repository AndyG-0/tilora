# Voice Assistant Setup & Audio Policies

Tilora provides modular Speech-to-Text (STT) and Text-to-Speech (TTS) pipelines with support for browser-native speech, cloud APIs, and self-hosted neural voice servers.

---

## Speech-to-Text (STT) & Speech Recognition

| Browser / Environment | STT Engine | Requirements |
|---|---|---|
| **Google Chrome / Microsoft Edge** | Web Speech API (Native) | Free, built-in browser engine. Secure context or insecure origin flag required. |
| **Apple Safari** | SpeechRecognition (Native) | Free, built-in. Requires HTTPS or `localhost`. |
| **Chromium / Raspberry Pi Kiosk** | OpenAI Whisper (Cloud STT) | Open-source Chromium lacks proprietary Google Speech keys. Enable Whisper STT in Settings. |
| **Mozilla Firefox & Brave** | OpenAI Whisper (Cloud STT) | Firefox lacks native Web Speech. Enable Whisper STT in Settings. |

### Enabling Cloud Whisper STT
1. Open **Settings → Admin settings → Voice input**.
2. Check **Enable OpenAI Whisper speech-to-text (Cloud STT)**.
3. Model: `whisper-1` (uses the configured OpenAI API key; costs ~$0.006 per minute of audio).

---

## Text-to-Speech (TTS) Engines

### 1. Browser Native Voices
Available on all devices by default without configuration.

### 2. OpenAI Text-to-Speech (Cloud)
Under **Settings → Admin settings → Voice output**:
- Check **Enable OpenAI text-to-speech**.
- Model: `gpt-4o-mini-tts` or `tts-1-hd`.
- Voices available to users: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`.

### 3. Piper Neural TTS (Self-Hosted)
[Piper](https://github.com/rhasspy/piper) is a fast, local neural text-to-speech system that runs efficiently even on a Raspberry Pi.
- Check **Enable Piper (self-hosted) text-to-speech**.
- **Server URL**: e.g. `http://piper.local:5000` (pointing to a `piper-http` or wyoming-piper container).
- **Voices**: Comma-separated voice IDs (e.g. `en_US-lessac-medium|Lessac,en_US-amy-medium|Amy`).

---

## Chromium Autoplay & Audio Policies

Chromium-based browsers block background audio playback until the webpage has received a user tap or key press.

On an unattended kiosk that boots directly into the dashboard with "Always-on microphone", spoken replies would stay silent until touched once.

### Solution for Kiosks
Launch Chromium with the `--autoplay-policy=no-user-gesture-required` flag (automatically configured by `deploy/kiosk.sh`).

For enterprise or remote kiosk deployments, apply the Chromium enterprise policy:
`/etc/chromium/policies/managed/dashboard.json`:

```json
{
  "AudioCaptureAllowedUrls": ["http://localhost:5173", "http://localhost:3000", "http://192.168.1.100:5173"]
}
```
