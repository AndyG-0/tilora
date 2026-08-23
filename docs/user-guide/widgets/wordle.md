# Wordle Widget

The **Wordle** widget (`type: wordle`) provides a daily 5-letter word puzzle game playable directly on your smart display.

---

## Features

- **Daily Word Guessing**: Guess the 5-letter word in 6 attempts with classic color-coded letter clues (Green = Correct spot, Yellow = In word, Gray = Not in word).
- **On-Screen Keyboard & Physical Input**: Use the interactive on-screen touch keyboard or desktop keyboard.
- **Streak & Statistics**: Tracks games played, win rate, and current/max streak in local storage.
- **Zero Configuration**: Runs client-side with zero external API calls.

---

## Configuration (`dashboard.yaml`)

```yaml
- id: wordle
  type: wordle
  enabled: true
  layout: { col: 4, row: 4, colSpan: 1, rowSpan: 1 }
  settings: {}
```
