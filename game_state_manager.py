"""
game_state_manager.py
---------------------
Centralises all game state logic into one place.

WHY: Previously, game_state was a raw string variable scattered across main.py.
     Any typo or invalid transition would silently corrupt the game loop.
     This class makes every state and every legal transition explicit,
     logs transitions for easy debugging, and provides a clean API
     that the rest of the refactor (Commits 2-22) will build on top of.

USAGE:
    gsm = GameStateManager()
    gsm.transition(GameState.GENERATING)       # validated — returns bool
    gsm.force_transition(GameState.BOOT_MENU)  # emergency bypass
    if gsm == GameState.RUNNING: ...
    if gsm.is_in(GameState.WIN, GameState.LOSE): ...
"""


class GameState:
    """
    All valid game states as string constants.

    Current states (matching original main.py names so Commit 1 is a zero-risk swap):
        MENU       -> title screen
        LOADING    -> race setup (racers, solver, BFS comparison)
        GENERATING -> GA evolution screen
        READY      -> pre-race overlay (controls + AI stats)
        RUNNING    -> active race
        GAMEOVER   -> post-race result screen

    Future states (scaffolded here for Commits 2-19, not yet wired):
        BOOT_MENU  -> new multi-option title screen   (replaces MENU)
        MAP_SELECT -> saved map browser
        AI_PREVIEW -> live A* path animation          (new)
        PRE_RACE   -> controls overlay + pulsing SPACE (replaces READY)
        WIN        -> dedicated win screen             (replaces GAMEOVER win branch)
        LOSE       -> dedicated lose screen            (replaces GAMEOVER lose branch)
    """

    # ── Active states (used right now) ──────────────────────────────────────
    MENU       = "MENU"
    LOADING    = "LOADING"
    GENERATING = "GENERATING"
    READY      = "READY"
    RUNNING    = "RUNNING"
    GAMEOVER   = "GAMEOVER"

    # ── Future states (wired in later commits) ───────────────────────────────
    BOOT_MENU  = "BOOT_MENU"
    MAP_SELECT = "MAP_SELECT"
    AI_PREVIEW = "AI_PREVIEW"
    PRE_RACE   = "PRE_RACE"
    WIN        = "WIN"
    LOSE       = "LOSE"


# ---------------------------------------------------------------------------
# Transition table
# Maps each state to the SET of states it is allowed to move into.
# Any transition NOT in this table is a bug and will be logged as a warning.
#
# NOTE: GAMEOVER -> RUNNING is intentional — the R-key restart path reuses
#       already-prepared race data and skips the full LOADING phase.
# ---------------------------------------------------------------------------
_VALID_TRANSITIONS: dict[str, set[str]] = {
    GameState.MENU:       {GameState.LOADING, GameState.GENERATING},
    GameState.GENERATING: {GameState.LOADING, GameState.MENU},
    GameState.LOADING:    {GameState.READY, GameState.MENU},
    GameState.READY:      {GameState.RUNNING},
    GameState.RUNNING:    {GameState.GAMEOVER},
    GameState.GAMEOVER:   {GameState.MENU, GameState.LOADING,
                           GameState.GENERATING, GameState.RUNNING},

    # Future transitions (already registered so connecting new states later
    # only requires adding entries here, not restructuring the table).
    GameState.BOOT_MENU:  {GameState.MAP_SELECT, GameState.GENERATING,
                           GameState.LOADING},
    GameState.MAP_SELECT: {GameState.LOADING, GameState.BOOT_MENU},
    GameState.AI_PREVIEW: {GameState.PRE_RACE},
    GameState.PRE_RACE:   {GameState.RUNNING},
    GameState.WIN:        {GameState.RUNNING, GameState.GENERATING,
                           GameState.BOOT_MENU},
    GameState.LOSE:       {GameState.RUNNING, GameState.GENERATING,
                           GameState.BOOT_MENU},
}


class GameStateManager:
    """
    Manages the active game state with validated transitions and a history log.

    Supports equality comparison against plain strings so that existing
    `if game_state == "MENU":` patterns can be updated to
    `if gsm == GameState.MENU:` with minimal friction — __eq__ handles both.
    """

    def __init__(self, initial_state: str = GameState.MENU):
        self._state: str = initial_state
        self._previous_state: str | None = None
        self._history: list[str] = []

    # ── Core API ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        """The current state string."""
        return self._state

    def transition(self, new_state: str) -> bool:
        """
        Move to new_state if it is a valid transition from the current state.

        Returns True on success. On failure, logs a warning, does NOT change
        state, and returns False so the caller can decide how to handle it.
        """
        allowed = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            print(
                f"[GSM WARNING] Invalid transition: {self._state!r} -> {new_state!r}. "
                f"Allowed: {sorted(allowed) or 'none'}"
            )
            return False

        self._record_and_set(new_state)
        return True

    def force_transition(self, new_state: str) -> None:
        """
        Move to new_state unconditionally, bypassing the transition table.
        Use ONLY for error recovery. Always add a comment at the call site
        explaining why a forced transition is necessary.
        """
        print(f"[GSM FORCE] {self._state!r} -> {new_state!r}")
        self._record_and_set(new_state)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def is_in(self, *states: str) -> bool:
        """Return True if the current state matches any of the given states."""
        return self._state in states

    @property
    def previous(self) -> str | None:
        """The state we were in before the most recent transition."""
        return self._previous_state

    @property
    def history(self) -> list[str]:
        """Read-only copy of the full state history, oldest entry first."""
        return list(self._history)

    # ── Dunder helpers ────────────────────────────────────────────────────────

    def __eq__(self, other: object) -> bool:
        """
        Allows both `gsm == "RUNNING"` and `gsm == GameState.RUNNING`.
        This means swapping `game_state == "X"` -> `gsm == "X"` throughout
        main.py requires no other changes — the comparison still resolves.
        """
        if isinstance(other, str):
            return self._state == other
        if isinstance(other, GameStateManager):
            return self._state == other._state
        return NotImplemented

    def __str__(self) -> str:
        return self._state

    def __repr__(self) -> str:
        return f"GameStateManager(state={self._state!r})"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _record_and_set(self, new_state: str) -> None:
        """Update history and set the new active state."""
        print(f"[GSM] {self._state!r} -> {new_state!r}")
        self._history.append(self._state)
        self._previous_state = self._state
        self._state = new_state
