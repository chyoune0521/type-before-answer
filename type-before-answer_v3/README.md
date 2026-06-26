# Type Before Answer v3

This Anki add-on places an optional multiline typing box in the reviewer bottom bar. *Show Answer* is always allowed, even when the typing box is empty.

## Behavior

- `Enter` inserts a line break inside the typing box.
- `Ctrl+Enter` on Windows/Linux, `Cmd+Enter` on macOS, and `Esc` leave the typing box and return focus to the review window.
- The answer side keeps showing the text you typed on the question side. The box resets on the next question.
- The add-on can be toggled from Anki's top `Type` menu with `Type box: On` / `Type box: Off`.
- The typing box font size is configurable in Anki's add-on config. The default is `12pt`.
- The typing box has no visible label row, so the previous label space is available to the card area and the input box.
- The default typing box font is `Malgun Gothic`, with macOS-friendly Korean fallbacks and `MS Gothic` as a fallback.
- The typing box can be resized by dragging its resize handle. The last size is saved in `user_files/state.json`.

## Configuration

Open Anki's add-on configuration and edit:

```json
{
  "font_size_pt": 12
}
```

The `Type` menu toggle is not exposed in the add-on config. It is stored separately in `user_files/state.json` so it can be changed directly while Anki is running.

## Manual installation

Copy the `type-before-answer_v3` folder into Anki's `addons21` directory and restart Anki.

## Distribution notes

Package the contents of `type-before-answer_v3` without `__pycache__`, `.pyc`, generated `meta.json`, or generated `user_files/state.json`.
