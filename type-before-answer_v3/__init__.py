"""Optional reviewer typing box with review-friendly focus handling."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
from urllib.parse import unquote

import aqt
from aqt import gui_hooks, mw
from aqt.qt import *
from aqt.reviewer import Reviewer
from aqt.utils import tooltip

logger = logging.getLogger(__name__)

ADDON_LABEL = "Type Before Answer"
INPUT_ID = "type-before-answer-v3-input"
WRAPPER_ID = "type-before-answer-v3-wrapper"
CONTAINER_ID = "type-before-answer-v3-container"
COMMAND_PREFIX = "type_before_answer_v3:"
FOCUS_COMMAND = f"{COMMAND_PREFIX}focus_reviewer"
SIZE_COMMAND_PREFIX = f"{COMMAND_PREFIX}box_size:"
TEXT_COMMAND_PREFIX = f"{COMMAND_PREFIX}text:"
FOCUS_DELAY_MS = 50

DEFAULT_FONT_SIZE_PT = 12
DEFAULT_FONT_FAMILY = '"Malgun Gothic", "Apple SD Gothic Neo", "Hiragino Sans", "MS Gothic", sans-serif'
DEFAULT_BOX_HEIGHT_PX = 96
MIN_FONT_SIZE_PT = 6
MAX_FONT_SIZE_PT = 72
MIN_BOX_WIDTH_PX = 160
MAX_BOX_WIDTH_PX = 2400
MIN_BOX_HEIGHT_PX = 48
MAX_BOX_HEIGHT_PX = 1600

STATE_FILE = Path(__file__).with_name("user_files") / "state.json"

_type_menu: Optional[QMenu] = None
_toggle_action: Optional[QAction] = None


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return {}
    except Exception:
        logger.exception("Could not read Type Before Answer state file")
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_file(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, sort_keys=True)
            file.write("\n")
    except Exception:
        logger.exception("Could not write Type Before Answer state file")


def _clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _get_config() -> dict[str, Any]:
    config = mw.addonManager.getConfig(__name__) if mw else None
    return config if isinstance(config, dict) else {}


def _font_size_pt() -> int:
    config = _get_config()
    return _clamp_int(
        config.get("font_size_pt"),
        DEFAULT_FONT_SIZE_PT,
        MIN_FONT_SIZE_PT,
        MAX_FONT_SIZE_PT,
    )


def _get_state() -> dict[str, Any]:
    state = _read_json_file(STATE_FILE)
    state.setdefault("enabled", True)
    return state


def _save_state(state: dict[str, Any]) -> None:
    _write_json_file(STATE_FILE, state)


def _is_enabled() -> bool:
    return bool(_get_state().get("enabled", True))


def _set_enabled(enabled: bool) -> None:
    state = _get_state()
    state["enabled"] = enabled
    _save_state(state)
    _sync_type_menu()
    _refresh_current_review_ui()
    tooltip(f"{ADDON_LABEL}: {'On' if enabled else 'Off'}", parent=mw, period=1200)
    if not enabled:
        _focus_reviewer(_current_reviewer())


def _bottom_web_available(reviewer: Reviewer) -> bool:
    bottom = getattr(reviewer, "bottom", None)
    return bool(bottom and getattr(bottom, "web", None))


def _current_reviewer() -> Optional[Reviewer]:
    reviewer = getattr(aqt.mw, "reviewer", None)
    if reviewer and getattr(reviewer, "card", None) is not None:
        return reviewer
    return None


def _reviewer_from_context(context: Any) -> Optional[Reviewer]:
    if isinstance(context, Reviewer):
        return context
    reviewer = getattr(context, "reviewer", None)
    if isinstance(reviewer, Reviewer):
        return reviewer
    return _current_reviewer()


def _reviewer_text(reviewer: Optional[Reviewer]) -> str:
    if not reviewer:
        return ""
    text = getattr(reviewer, "_type_before_answer_v3_text", "")
    return text if isinstance(text, str) else ""


def _set_reviewer_text(reviewer: Optional[Reviewer], text: str) -> None:
    if reviewer:
        reviewer._type_before_answer_v3_text = text  # type: ignore[attr-defined]


def _box_dimensions_from_state() -> tuple[Optional[int], int]:
    state = _get_state()
    width_value = state.get("box_width_px")
    width = None
    if width_value is not None:
        width = _clamp_int(width_value, MIN_BOX_WIDTH_PX, MIN_BOX_WIDTH_PX, MAX_BOX_WIDTH_PX)
    height = _clamp_int(
        state.get("box_height_px"),
        DEFAULT_BOX_HEIGHT_PX,
        MIN_BOX_HEIGHT_PX,
        MAX_BOX_HEIGHT_PX,
    )
    return width, height


def _build_review_ui_js(reviewer: Reviewer, show_input: bool, auto_focus: bool) -> str:
    width_px, height_px = _box_dimensions_from_state()
    enabled = _is_enabled()
    options = {
        "containerId": CONTAINER_ID,
        "enabled": enabled,
        "focusCommand": FOCUS_COMMAND,
        "focusDelayMs": FOCUS_DELAY_MS,
        "fontFamily": DEFAULT_FONT_FAMILY,
        "fontSizePt": _font_size_pt(),
        "heightPx": height_px,
        "inputId": INPUT_ID,
        "autoFocus": auto_focus,
        "showInput": enabled and show_input,
        "sizeCommandPrefix": SIZE_COMMAND_PREFIX,
        "textCommandPrefix": TEXT_COMMAND_PREFIX,
        "textValue": _reviewer_text(reviewer),
        "widthPx": width_px,
        "wrapperId": WRAPPER_ID,
    }
    return f"""
(function() {{
    const options = {json.dumps(options)};

    function removeInput() {{
        const container = document.getElementById(options.containerId);
        if (container) {{
            container.remove();
        }}

        const wrapper = document.getElementById(options.wrapperId);
        if (wrapper && wrapper.parentElement) {{
            const parent = wrapper.parentElement;
            while (wrapper.firstChild) {{
                parent.insertBefore(wrapper.firstChild, wrapper);
            }}
            wrapper.remove();
        }}
    }}

    const middle = document.getElementById("middle");
    if (!middle) {{
        return;
    }}

    if (!options.showInput) {{
        removeInput();
        return;
    }}

    let wrapper = document.getElementById(options.wrapperId);
    if (!wrapper) {{
        wrapper = document.createElement("div");
        wrapper.id = options.wrapperId;
        wrapper.style.display = "flex";
        wrapper.style.flexDirection = "column";
        wrapper.style.alignItems = "center";
        wrapper.style.gap = "4px";
        wrapper.style.width = "100%";
        while (middle.firstChild) {{
            wrapper.appendChild(middle.firstChild);
        }}
        middle.appendChild(wrapper);
    }}

    let container = document.getElementById(options.containerId);
    if (!container) {{
        container = document.createElement("div");
        container.id = options.containerId;
        container.style.width = "100%";
        container.style.display = "flex";
        container.style.flexDirection = "column";
        container.style.alignItems = "center";
        container.style.margin = "0";

        const textarea = document.createElement("textarea");
        textarea.id = options.inputId;
        textarea.setAttribute("aria-label", "Type before answer");
        textarea.rows = 3;
        textarea.spellcheck = false;
        textarea.dataset.typeBeforeAnswerV3 = "1";

        container.appendChild(textarea);
        wrapper.insertBefore(container, wrapper.firstChild);
    }} else if (wrapper.firstChild !== container) {{
        wrapper.insertBefore(container, wrapper.firstChild);
    }}

    const textarea = document.getElementById(options.inputId);
    if (!textarea) {{
        return;
    }}

    textarea.value = "";
    textarea.style.boxShadow = "";
    textarea.style.boxSizing = "border-box";
    textarea.style.display = "block";
    textarea.style.width = options.widthPx ? options.widthPx + "px" : "min(100%, 720px)";
    textarea.style.maxWidth = "100%";
    textarea.style.height = options.heightPx + "px";
    textarea.style.minWidth = "{MIN_BOX_WIDTH_PX}px";
    textarea.style.minHeight = "{MIN_BOX_HEIGHT_PX}px";
    textarea.style.resize = "both";
    textarea.style.overflow = "auto";
    textarea.style.padding = "6px 8px";
    textarea.style.fontFamily = options.fontFamily;
    textarea.style.fontSize = options.fontSizePt + "pt";
    textarea.style.lineHeight = "1.35";
    textarea.style.border = "1px solid var(--border, #b8b8b8)";
    textarea.style.borderRadius = "4px";
    textarea.style.background = "var(--canvas, white)";
    textarea.style.color = "var(--fg, inherit)";
    textarea.value = options.textValue || "";

    function focusReviewer() {{
        reportTextNow();
        textarea.blur();
        pycmd(options.focusCommand);
    }}

    function reportTextNow() {{
        pycmd(options.textCommandPrefix + encodeURIComponent(textarea.value));
    }}

    function reportTextSoon() {{
        if (textarea.dataset.typeBeforeAnswerV3TextReporting === "1") {{
            return;
        }}
        textarea.dataset.typeBeforeAnswerV3TextReporting = "1";
        setTimeout(function() {{
            textarea.dataset.typeBeforeAnswerV3TextReporting = "";
            reportTextNow();
        }}, 120);
    }}

    function reportSize() {{
        if (textarea.dataset.typeBeforeAnswerV3Reporting === "1") {{
            return;
        }}
        textarea.dataset.typeBeforeAnswerV3Reporting = "1";
        setTimeout(function() {{
            textarea.dataset.typeBeforeAnswerV3Reporting = "";
            const rect = textarea.getBoundingClientRect();
            const width = Math.round(rect.width);
            const height = Math.round(rect.height);
            if (width > 0 && height > 0) {{
                pycmd(options.sizeCommandPrefix + width + ":" + height);
            }}
        }}, 250);
    }}

    if (!textarea.dataset.typeBeforeAnswerV3Handler) {{
        textarea.addEventListener("keydown", function(evt) {{
            if (evt.key === "Enter" && (evt.ctrlKey || evt.metaKey) && !evt.shiftKey && !evt.altKey) {{
                evt.preventDefault();
                evt.stopPropagation();
                focusReviewer();
                return;
            }}

            if (evt.key === "Escape") {{
                evt.preventDefault();
                evt.stopPropagation();
                focusReviewer();
                return;
            }}

            if (evt.key === "Enter") {{
                evt.stopPropagation();
            }}
        }});
        textarea.addEventListener("input", reportTextSoon);
        textarea.addEventListener("change", reportTextNow);
        textarea.addEventListener("mouseup", reportSize);
        textarea.addEventListener("touchend", reportSize);
        textarea.dataset.typeBeforeAnswerV3Handler = "1";
    }}

    if (window.ResizeObserver && !textarea.typeBeforeAnswerV3ResizeObserver) {{
        textarea.typeBeforeAnswerV3ResizeObserver = new ResizeObserver(reportSize);
        textarea.typeBeforeAnswerV3ResizeObserver.observe(textarea);
    }}

    if (options.autoFocus) {{
        setTimeout(function() {{
            textarea.focus({{ preventScroll: true }});
            textarea.select();
        }}, options.focusDelayMs);
    }}
}})();
"""


GET_VALUE_JS = f"""
(function() {{
    const el = document.getElementById({json.dumps(INPUT_ID)});
    return el ? el.value : "";
}})();
"""


def _focus_reviewer(reviewer: Optional[Reviewer]) -> None:
    if not reviewer:
        return

    def _focus() -> None:
        try:
            web = getattr(reviewer, "web", None) or reviewer.mw.web
            web.setFocus()
            reviewer.mw.activateWindow()
        except Exception:
            logger.exception("Could not move focus back to the reviewer")

    reviewer.mw.progress.single_shot(0, _focus)


def _adjust_bottom_height(reviewer: Optional[Reviewer]) -> None:
    if reviewer and _bottom_web_available(reviewer):
        try:
            reviewer.bottom.web.adjustHeightToFit()
        except Exception:
            logger.exception("Could not adjust reviewer bottom bar height")


def _save_box_size_from_message(message: str, reviewer: Optional[Reviewer]) -> None:
    raw_size = message[len(SIZE_COMMAND_PREFIX) :]
    try:
        raw_width, raw_height = raw_size.split(":", 1)
    except ValueError:
        return

    width = _clamp_int(raw_width, MIN_BOX_WIDTH_PX, MIN_BOX_WIDTH_PX, MAX_BOX_WIDTH_PX)
    height = _clamp_int(raw_height, DEFAULT_BOX_HEIGHT_PX, MIN_BOX_HEIGHT_PX, MAX_BOX_HEIGHT_PX)
    state = _get_state()
    if state.get("box_width_px") == width and state.get("box_height_px") == height:
        return
    state["box_width_px"] = width
    state["box_height_px"] = height
    _save_state(state)
    _adjust_bottom_height(reviewer)


def _save_text_from_message(message: str, reviewer: Optional[Reviewer]) -> None:
    encoded_text = message[len(TEXT_COMMAND_PREFIX) :]
    _set_reviewer_text(reviewer, unquote(encoded_text))


def _on_js_message(handled: tuple[bool, Any], message: str, context: Any) -> tuple[bool, Any]:
    if handled[0] or not message.startswith(COMMAND_PREFIX):
        return handled

    reviewer = _reviewer_from_context(context)
    if message == FOCUS_COMMAND:
        _focus_reviewer(reviewer)
        return (True, None)

    if message.startswith(TEXT_COMMAND_PREFIX):
        _save_text_from_message(message, reviewer)
        return (True, None)

    if message.startswith(SIZE_COMMAND_PREFIX):
        _save_box_size_from_message(message, reviewer)
        return (True, None)

    return (False, None)


def _insert_or_refresh_ui(reviewer: Reviewer, show_input: bool, auto_focus: bool) -> None:
    if not _bottom_web_available(reviewer):
        return
    reviewer.bottom.web.eval(_build_review_ui_js(reviewer, show_input=show_input, auto_focus=auto_focus))
    reviewer.mw.progress.single_shot(FOCUS_DELAY_MS, lambda: _adjust_bottom_height(reviewer))

    def _focus_bottom() -> None:
        if show_input and auto_focus and _is_enabled() and _bottom_web_available(reviewer):
            reviewer.bottom.web.setFocus()

    reviewer.mw.progress.single_shot(FOCUS_DELAY_MS, _focus_bottom)


def _refresh_current_review_ui() -> None:
    reviewer = _current_reviewer()
    if not reviewer:
        return
    is_question = getattr(reviewer, "state", None) == "question"
    _insert_or_refresh_ui(reviewer, show_input=True, auto_focus=is_question)


def _on_show_question(card: Any) -> None:  # type: ignore[override]
    reviewer = _current_reviewer()
    if reviewer:
        _set_reviewer_text(reviewer, "")
        _insert_or_refresh_ui(reviewer, show_input=True, auto_focus=True)


def _on_show_answer(card: Any) -> None:  # type: ignore[override]
    reviewer = _current_reviewer()
    if reviewer:
        _insert_or_refresh_ui(reviewer, show_input=True, auto_focus=False)


def _patch_reviewer_methods() -> None:
    if hasattr(Reviewer, "_type_before_answer_v3_original_show_answer"):
        return

    Reviewer._type_before_answer_v3_original_show_answer = Reviewer._showAnswer  # type: ignore[attr-defined]

    def _show_answer_with_text_capture(self: Reviewer) -> None:
        original = getattr(Reviewer, "_type_before_answer_v3_original_show_answer")
        if not _is_enabled() or getattr(self, "state", None) != "question" or not _bottom_web_available(self):
            original(self)
            return

        def _refresh_answer_ui() -> None:
            if getattr(self, "state", None) == "answer":
                _insert_or_refresh_ui(self, show_input=True, auto_focus=False)

        def _after(result: Optional[str]) -> None:
            _set_reviewer_text(self, result or "")
            original(self)
            self.mw.progress.single_shot(FOCUS_DELAY_MS, _refresh_answer_ui)

        try:
            self.bottom.web.evalWithCallback(GET_VALUE_JS, _after)
        except Exception:
            logger.exception("Could not capture Type Before Answer text before showing answer")
            original(self)
            self.mw.progress.single_shot(FOCUS_DELAY_MS, _refresh_answer_ui)

    Reviewer._showAnswer = _show_answer_with_text_capture  # type: ignore[assignment]


def _sync_type_menu() -> None:
    if not _toggle_action:
        return
    enabled = _is_enabled()
    _toggle_action.blockSignals(True)
    _toggle_action.setChecked(enabled)
    _toggle_action.setText("Type box: On" if enabled else "Type box: Off")
    _toggle_action.blockSignals(False)


def _on_toggle_action_triggered(*_args: Any) -> None:
    if _toggle_action:
        _set_enabled(_toggle_action.isChecked())


def _setup_type_menu() -> None:
    global _type_menu, _toggle_action
    if _type_menu or not mw:
        return

    try:
        menu_bar = getattr(mw.form, "menubar", None) or mw.menuBar()
        for action in list(menu_bar.actions()):
            menu = action.menu()
            if menu and menu.objectName() == "typeBeforeAnswerV3Menu":
                menu_bar.removeAction(action)

        _type_menu = QMenu("Type", mw)
        _type_menu.setObjectName("typeBeforeAnswerV3Menu")
        help_menu = getattr(mw.form, "menuHelp", None)
        if help_menu:
            menu_bar.insertMenu(help_menu.menuAction(), _type_menu)
        else:
            menu_bar.addMenu(_type_menu)

        _toggle_action = QAction("Type box: On", mw)
        _toggle_action.setObjectName("typeBeforeAnswerV3ToggleAction")
        _toggle_action.setCheckable(True)
        _toggle_action.setToolTip("Show or hide the Type Before Answer box during review.")
        _toggle_action.triggered.connect(_on_toggle_action_triggered)
        _type_menu.addAction(_toggle_action)
        _sync_type_menu()
    except Exception:
        logger.exception("Could not add Type Before Answer menu")


def _on_config_updated(*_args: Any) -> None:
    _refresh_current_review_ui()


def _setup() -> None:
    _patch_reviewer_methods()
    _setup_type_menu()
    gui_hooks.reviewer_did_show_question.append(_on_show_question)
    if hasattr(gui_hooks, "reviewer_did_show_answer"):
        gui_hooks.reviewer_did_show_answer.append(_on_show_answer)
    gui_hooks.webview_did_receive_js_message.append(_on_js_message)
    if mw and hasattr(mw.addonManager, "setConfigUpdatedAction"):
        mw.addonManager.setConfigUpdatedAction(__name__, _on_config_updated)


_setup()
