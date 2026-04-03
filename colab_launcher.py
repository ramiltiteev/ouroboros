# Ensure jokes tool is discovered (module in tools/ will be picked up by ToolRegistry)
try:
    import ouroboros.tools.jokes
except ImportError:
    pass  # Will fail first time on warmup, but will load later when invoked via ToolRegistry


def _handle_supervisor_command(text: str, chat_id: int, tg_offset: int = 0):
    """Handle supervisor slash-commands.

    Returns:
        True  — terminal command fully handled (caller should `continue`)
        str   — dual-path note to prepend (caller falls through to LLM)
        ""    — not a recognized command (falsy, caller falls through)
    """
    lowered = text.strip().lower()

    if lowered.startswith("/panic"):
        send_with_budget(chat_id, "🛑 PANIC: stopping everything now.")
        kill_workers()
        st2 = load_state()
        st2["tg_offset"] = tg_offset
        save_state(st2)
        raise SystemExit("PANIC")

    if lowered.startswith("/restart"):
        st2 = load_state()
        st2["session_id"] = uuid.uuid4().hex
        st2["tg_offset"] = tg_offset
        save_state(st2)
        send_with_budget(chat_id, "♻️ Restarting (soft).")
        ok, msg = safe_restart(reason="owner_restart", unsynced_policy="rescue_and_reset")
        if not ok:
            send_with_budget(chat_id, f"⚠️ Restart cancelled: {msg}")
            return True
        kill_workers()
        os.execv(sys.executable, [sys.executable, __file__])

    # Dual-path commands: supervisor handles + LLM sees a note
    if lowered.startswith("/status"):
        status = status_text(WORKERS, PENDING, RUNNING, SOFT_TIMEOUT_SEC, HARD_TIMEOUT_SEC)
        send_with_budget(chat_id, status, force_budget=True)
        return "[Supervisor handled /status — status text already sent to chat]\n"

    if lowered.startswith("/review"):
        queue_review_task(reason="owner:/review", force=True)
        return "[Supervisor handled /review — review task queued]\n"

    if lowered.startswith("/evolve"):
        parts = lowered.split()
        action = parts[1] if len(parts) > 1 else "on"
        turn_on = action not in ("off", "stop", "0")
        st2 = load_state()
        st2["evolution_mode_enabled"] = bool(turn_on)
        save_state(st2)
        if not turn_on:
            PENDING[:] = [t for t in PENDING if str(t.get("type")) != "evolution"]
            sort_pending()
            persist_queue_snapshot(reason="evolve_off")
        state_str = "ON" if turn_on else "OFF"
        send_with_budget(chat_id, f"🧬 Evolution: {state_str}")
        return f"[Supervisor handled /evolve — evolution toggled {state_str}]\n"

    if lowered.startswith("/bg"):
        parts = lowered.split()
        action = parts[1] if len(parts) > 1 else "status"
        if action in ("start", "on", "1"):
            result = _consciousness.start()
            send_with_budget(chat_id, f"🧠 {result}")
        elif action in ("stop", "off", "0"):
            result = _consciousness.stop()
            send_with_budget(chat_id, f"🧠 {result}")
        else:
            bg_status = "running" if _consciousness.is_running else "stopped"
            send_with_budget(chat_id, f"🧠 Background consciousness: {bg_status}")
        return f"[Supervisor handled /bg {action}]\n"

    # New joke command
    if lowered.startswith("/joke"):
        # Import jokes module if not already
        import ouroboros.tools.jokes as jokes

        result = jokes.get_joke()
        joke_text = result["joke"]
        send_with_budget(chat_id, f"😂 {joke_text}")
        return "[Supervisor handled /joke — joke sent to chat]\n"

    return ""