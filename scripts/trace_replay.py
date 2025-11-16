#!/usr/bin/env python3
# Copyright © 2025 Sierra Labs LLC
# SPDX-License-Identifier: AGPL-3.0-only
# License-Filename: LICENSE

"""
Curses-based trace replay viewer for Blueplane Telemetry Core.

This script replays events from the SQLite raw_traces table in a terminal UI,
similar in spirit to asciinema but driven by telemetry events.

features:
- auto-play through events with a configurable delay
- manual navigation with j/k or arrow keys
- session and platform filtering
- optional non-ui mode for quick inspection / testing

Examples:
    # Replay the most recent Cursor session interactively
    python scripts/trace_replay.py --platform cursor

    # Replay a specific session ID
    python scripts/trace_replay.py --session-id curs_1763237800835_6e870742

    # Run in non-UI mode (just print a summary)
    python scripts/trace_replay.py --platform cursor --no-ui --limit 20
"""

import argparse
import json
import sys
import time
import zlib
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence as SeqType

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.processing.database.sqlite_client import SQLiteClient


def _load_gif_font(base_size: int = 18):
    """
    Try to load a high-quality monospace TrueType font for GIF rendering.

    On macOS we prefer Menlo / SF Mono. If none of the preferred fonts can be
    loaded, we fall back to Pillow's built-in bitmap font.
    """
    try:
        from PIL import ImageFont  # type: ignore
    except Exception:
        return None

    # Common monospace font candidates (paths and family names)
    candidates_paths = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFMono-Regular.otf",
        "/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/SF Mono Regular.ttf",
        # Homebrew-installed JetBrains Mono (common locations)
        "/usr/local/opt/jetbrains-mono/share/fonts/TTF/JetBrainsMono-Regular.ttf",
        "/opt/homebrew/opt/jetbrains-mono/share/fonts/TTF/JetBrainsMono-Regular.ttf",
    ]
    for path in candidates_paths:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), base_size)
            except Exception:
                continue

    candidates_names = [
        "Menlo",
        "SF Mono",
        "JetBrains Mono",
        "Fira Code",
        "Hack",
        "Courier New",
        "Consolas",
        "DejaVu Sans Mono",
    ]
    for name in candidates_names:
        try:
            return ImageFont.truetype(name, base_size)
        except Exception:
            continue

    try:
        from PIL import ImageFont  # type: ignore

        return ImageFont.load_default()
    except Exception:
        return None


@dataclass
class TraceEvent:
    sequence: int
    session_id: str
    event_type: str
    platform: str
    timestamp: str
    raw_json: str


def load_events(
    session_id: Optional[str] = None,
    platform: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[TraceEvent]:
    """
    Load events from raw_traces with optional filters.

    Behavior when session_id is not provided:
    - Filters by platform (if given).
    - Loads all matching rows ordered by sequence.
    - Groups by session_id and selects the session with the MOST events
      (rather than simply the last one), which tends to be a more interesting
      session to replay interactively.
    - If limit is provided, trims to the most recent N events for that session.
    """
    db_path = Path.home() / ".blueplane" / "telemetry.db"
    if not db_path.exists():
        raise SystemExit(
            f"Database not found at {db_path}. "
            "Run scripts/init_database.py and ensure the processing server is running."
        )

    client = SQLiteClient(str(db_path))

    base_query = (
        "SELECT sequence, session_id, event_type, platform, timestamp, event_data "
        "FROM raw_traces"
    )
    where_clauses = []
    params: list = []

    if session_id:
        where_clauses.append("session_id = ?")
        params.append(session_id)

    if platform:
        where_clauses.append("platform = ?")
        params.append(platform)

    if where_clauses:
        base_query += " WHERE " + " AND ".join(where_clauses)

    base_query += " ORDER BY sequence"

    # If no explicit session_id was provided, automatically scope to the most recent session
    # for the given platform by taking the last session_id in the ordered results.
    with client.get_connection() as conn:
        cursor = conn.execute(base_query, tuple(params))
        rows = cursor.fetchall()

    if not rows:
        return []

    # Auto-select a session if session_id was not specified
    if session_id is None:
        # Group by session_id and select the one with the most events.
        counts: dict[str, int] = {}
        for _, sess, *_rest in rows:
            s = str(sess)
            counts[s] = counts.get(s, 0) + 1

        # Pick the session_id with the maximum count
        target_session = max(counts.items(), key=lambda kv: kv[1])[0]
        rows = [row for row in rows if str(row[1]) == target_session]

    # Apply limit at the end (most recent N)
    if limit is not None and limit > 0 and len(rows) > limit:
        rows = rows[-limit:]

    events: List[TraceEvent] = []
    for seq, sess, ev_type, plat, ts, blob in rows:
        try:
            json_str = zlib.decompress(blob).decode("utf-8")
        except Exception:
            # Fall back to an empty JSON object if decompression fails
            json_str = "{}"
        events.append(
            TraceEvent(
                sequence=seq,
                session_id=str(sess),
                event_type=str(ev_type),
                platform=str(plat),
                timestamp=str(ts),
                raw_json=json_str,
            )
        )

    return events


def print_events(events: SeqType[TraceEvent]) -> None:
    """Simple non-UI printing of events for quick inspection."""
    if not events:
        print("ℹ️  No matching events found.")
        return

    first = events[0]
    print(
        f"Replaying {len(events)} event(s) "
        f"for session_id={first.session_id} platform={first.platform}"
    )
    print("-" * 80)
    for ev in events:
        print(
            f"{ev.sequence:8d}  {ev.event_type:20s}  {ev.timestamp}  {ev.session_id}"
        )


def generate_gif(
    events: SeqType[TraceEvent],
    gif_path: str,
    auto_delay: float,
    width_chars: int = 160,
    height_lines: int = 40,
    wrap_long: bool = True,
    pretty: bool = True,
    scale_factor: int = 2,
    line_spacing: int = 4,
) -> None:
    """
    Generate an animated GIF replay of the trace.

    The GIF is rendered off-screen using Pillow and mimics the textual UI:
    - a simple header line
    - a small scrolling window of events around the current selection
    - a JSON details block for the selected event
    """
    if not events:
        print("ℹ️  No matching events found, not generating GIF.")
        return

    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
    except ImportError:
        print("❌ Pillow is not installed. Run `pip install -r requirements.txt`.")
        return

    font = _load_gif_font(base_size=18) or ImageFont.load_default()
    # Approximate character cell size from the font (Pillow 10+ uses getbbox)
    bbox = font.getbbox("M")
    char_w = bbox[2] - bbox[0]
    char_h = bbox[3] - bbox[1]
    line_height = char_h + max(0, line_spacing)
    img_w = width_chars * char_w
    img_h = height_lines * line_height

    max_frames = min(len(events), 200)
    if max_frames <= 0:
        print("ℹ️  No events to render into GIF.")
        return

    # Convert delay in seconds to per-frame duration in ms
    duration_ms = int(max(auto_delay, 0.2) * 1000)

    frames: list[Image.Image] = []
    selected = 0

    for _ in range(max_frames):
        ev = events[selected]
        lines: list[str] = []

        # Header
        header = (
            f"trace replay gif | session={events[0].session_id} "
            f"platform={events[0].platform} "
            f"[{selected+1}/{len(events)}]"
        )
        lines.append(header[:width_chars])
        lines.append("-" * width_chars)

        # Timeline window around current event
        window = 5
        start_idx = max(0, selected - window)
        end_idx = min(len(events), selected + window + 1)
        for idx in range(start_idx, end_idx):
            e = events[idx]
            prefix = ">" if idx == selected else " "
            line = (
                f"{prefix}{e.sequence:8d}  {e.event_type:16s}  "
                f"{e.timestamp}  {e.session_id}"
            )
            lines.append(line[:width_chars])

        # Spacer and details title
        lines.append("-" * width_chars)
        detail_title = (
            f"details seq={ev.sequence} type={ev.event_type} ts={ev.timestamp}"
        )
        lines.append(detail_title[:width_chars])

        # JSON body
        try:
            parsed = json.loads(ev.raw_json)
            if pretty:
                raw = json.dumps(parsed, indent=2)
            else:
                raw = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            raw = ev.raw_json

        json_lines = raw.splitlines()
        if wrap_long:
            wrapped: list[str] = []
            for line in json_lines:
                if len(line) <= width_chars:
                    wrapped.append(line)
                else:
                    wrapped.extend(
                        textwrap.wrap(
                            line,
                            width=max(10, width_chars),
                            break_long_words=False,
                            replace_whitespace=False,
                        )
                    )
            json_lines = wrapped

        for line in json_lines:
            if len(lines) >= height_lines:
                break
            lines.append(line[:width_chars])

        # Pad to full height
        while len(lines) < height_lines:
            lines.append("")

        # Render to image
        base = Image.new("L", (img_w, img_h), color=0)  # grayscale
        draw = ImageDraw.Draw(base)
        y = 0
        for line in lines[:height_lines]:
            draw.text((0, y), line, font=font, fill=255)
            y += line_height

        # Upscale for better legibility in GIF viewers
        if scale_factor > 1:
            frame = base.resize(
                (img_w * scale_factor, img_h * scale_factor),
                resample=Image.NEAREST,
            )
        else:
            frame = base

        frames.append(frame)

        if selected < len(events) - 1:
            selected += 1
        else:
            break

    if not frames:
        print("ℹ️  No frames were generated for GIF.")
        return

    out_path = Path(gif_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    frames[0].save(
        str(out_path),
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
    print(f"✅ Saved trace replay GIF to {out_path}")


def replay_curses(events: SeqType[TraceEvent], auto_delay: float) -> None:
    """Interactive curses-based replay UI."""
    if not events:
        print("ℹ️  No matching events found.")
        return

    import curses

    def _main(stdscr) -> None:
        curses.curs_set(0)
        stdscr.nodelay(False)

        selected = 0
        auto_play = auto_delay > 0
        last_advance = time.time()
        current_delay = max(0.0, auto_delay)

        wrap_long = False
        pretty = True

        while True:
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            session = events[0].session_id
            platform = events[0].platform
            status = (
                f"trace replay | session={session} platform={platform} "
                f"| q:quit  j/k or ↑/↓:navigate  ←/h:slower  →/l:faster  "
                f"space:auto  delay={current_delay:.1f}s  "
                f"w:wrap={'on' if wrap_long else 'off'}  "
                f"r:render={'pretty' if pretty else 'compact'}"
            )
            stdscr.addnstr(0, 0, status, w - 1, curses.A_BOLD)

            # Timeline list (top half)
            list_top = 2
            list_height = max(5, h // 2 - 1)
            start_idx = max(0, selected - list_height // 2)
            end_idx = min(len(events), start_idx + list_height)

            for i, idx in enumerate(range(start_idx, end_idx), start=list_top):
                ev = events[idx]
                line = (
                    f"{ev.sequence:8d}  {ev.event_type:16s}  "
                    f"{ev.timestamp}  {ev.session_id}"
                )
                if idx == selected:
                    stdscr.addnstr(i, 0, line, w - 1, curses.A_REVERSE)
                else:
                    stdscr.addnstr(i, 0, line, w - 1)

            # Details view (bottom half)
            detail_top = list_top + list_height + 1
            if detail_top < h:
                stdscr.hline(detail_top - 1, 0, "-", w)
                ev = events[selected]
                detail_title = (
                    f"Details for sequence={ev.sequence} "
                    f"event_type={ev.event_type} timestamp={ev.timestamp}"
                )
                stdscr.addnstr(detail_top, 0, detail_title, w - 1, curses.A_BOLD)

                # Pretty-print JSON, truncated to fit
                try:
                    parsed = json.loads(ev.raw_json)
                    if pretty:
                        raw = json.dumps(parsed, indent=2)
                    else:
                        raw = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
                except Exception:
                    raw = ev.raw_json

                lines = raw.splitlines()

                if wrap_long:
                    wrapped: list[str] = []
                    for line in lines:
                        if len(line) <= w - 1:
                            wrapped.append(line)
                        else:
                            wrapped.extend(
                                textwrap.wrap(
                                    line,
                                    width=max(10, w - 1),
                                    break_long_words=False,
                                    replace_whitespace=False,
                                )
                            )
                    detail_lines = wrapped
                else:
                    detail_lines = lines

                max_detail_lines = h - detail_top - 2
                for i, line in enumerate(detail_lines[:max_detail_lines]):
                    stdscr.addnstr(detail_top + 1 + i, 0, line, w - 1)

            stdscr.refresh()

            # Auto-play advance
            now = time.time()
            if auto_play and current_delay > 0 and now - last_advance >= current_delay:
                if selected < len(events) - 1:
                    selected += 1
                    last_advance = now

            stdscr.timeout(100)  # 100ms poll
            ch = stdscr.getch()
            if ch == -1:
                continue

            if ch in (ord("q"), 27):  # q or ESC
                break
            elif ch in (curses.KEY_DOWN, ord("j")):
                selected = min(len(events) - 1, selected + 1)
                auto_play = False
            elif ch in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
                auto_play = False
            elif ch == curses.KEY_NPAGE:  # Page Down
                selected = min(len(events) - 1, selected + 10)
                auto_play = False
            elif ch == curses.KEY_PPAGE:  # Page Up
                selected = max(0, selected - 10)
                auto_play = False
            elif ch == ord(" "):
                auto_play = not auto_play
                last_advance = time.time()
            elif ch in (curses.KEY_LEFT, ord("h")):
                # Slow down auto-play (increase delay)
                current_delay = min(5.0, current_delay + 0.2)
            elif ch in (curses.KEY_RIGHT, ord("l")):
                # Speed up auto-play (decrease delay, but not below 0.1s)
                current_delay = max(0.1, current_delay - 0.2)
            elif ch in (ord("w"), ord("W")):
                wrap_long = not wrap_long
            elif ch in (ord("r"), ord("R")):
                pretty = not pretty

    curses.wrapper(_main)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Curses-based trace replay viewer for raw_traces."
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help=(
            "Session ID to replay. If omitted, uses the session for the platform "
            "with the most events (i.e., the longest session)."
        ),
    )
    parser.add_argument(
        "--platform",
        type=str,
        default="cursor",
        help="Platform filter (default: cursor).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of events to load (most recent N for the session).",
    )
    parser.add_argument(
        "--auto-delay",
        type=float,
        default=0.8,
        help="Seconds between auto-advance steps (default: 0.8). Set to 0 to disable auto-play.",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Disable curses UI and just print a summary of events.",
    )
    parser.add_argument(
        "--gif",
        type=str,
        default=None,
        help=(
            "Optional path to write an animated GIF of the replay. "
            "When provided, a GIF is generated instead of launching the curses UI."
        ),
    )

    args = parser.parse_args()

    events = load_events(
        session_id=args.session_id,
        platform=args.platform,
        limit=args.limit,
    )

    if args.no_ui:
        print_events(events)
        return 0

    if args.gif:
        generate_gif(
            events,
            gif_path=args.gif,
            auto_delay=max(0.0, args.auto_delay),
        )
        return 0

    replay_curses(events, auto_delay=max(0.0, args.auto_delay))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


