"""
game_state_manager.py
---------------------
Central state machine. Every legal transition is explicit here.
main.py uses gsm.transition() — invalid jumps get logged, never silently corrupt.
"""


class GameState:
    # ── Active states ─────────────────────────────────────────────────────────
    BOOT_MENU  = "BOOT_MENU"
    TUTORIAL   = "TUTORIAL"
    MAP_SELECT = "MAP_SELECT"
    GA_SETUP   = "GA_SETUP"   
    GENERATING = "GENERATING"
    LOADING    = "LOADING"
    AI_PREVIEW = "AI_PREVIEW"
    PRE_RACE   = "PRE_RACE"
    RUNNING    = "RUNNING"
    PAUSED     = "PAUSED"
    WIN        = "WIN"
    LOSE       = "LOSE"

    # ── Legacy aliases ─────────────────────────────────────────────────────────
    MENU     = "BOOT_MENU"
    READY    = "PRE_RACE"
    GAMEOVER = "WIN"


_VALID_TRANSITIONS: dict[str, set[str]] = {
    GameState.BOOT_MENU:  {GameState.MAP_SELECT, GameState.GA_SETUP,
                           GameState.GENERATING, GameState.LOADING,
                           GameState.TUTORIAL},
    GameState.MAP_SELECT: {GameState.LOADING, GameState.BOOT_MENU},
    GameState.GA_SETUP:   {GameState.GENERATING, GameState.BOOT_MENU},  
    GameState.GENERATING: {GameState.LOADING, GameState.BOOT_MENU},
    GameState.LOADING:    {GameState.AI_PREVIEW, GameState.BOOT_MENU},
    GameState.AI_PREVIEW: {GameState.PRE_RACE},
    GameState.PRE_RACE:   {GameState.RUNNING},
    GameState.RUNNING:    {GameState.WIN, GameState.LOSE,
                            GameState.PAUSED},
     GameState.PAUSED:     {GameState.RUNNING,           
                           GameState.BOOT_MENU},
    GameState.TUTORIAL:   {GameState.BOOT_MENU},
    GameState.WIN:        {GameState.PRE_RACE, GameState.GENERATING,
                           GameState.BOOT_MENU},
    GameState.LOSE:       {GameState.PRE_RACE, GameState.GENERATING,
                           GameState.BOOT_MENU},
}


class GameStateManager:
    """Validated state machine with history log."""

    def __init__(self, initial: str = GameState.BOOT_MENU):
        self._state    = initial
        self._previous: str | None = None
        self._history:  list[str]  = []

    @property
    def state(self) -> str:
        return self._state

    def transition(self, new_state: str) -> bool:
        allowed = _VALID_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            print(f"[GSM WARNING] {self._state!r} -> {new_state!r} not allowed. "
                  f"Valid: {sorted(allowed) or 'none'}")
            return False
        self._do(new_state)
        return True

    def force_transition(self, new_state: str) -> None:
        print(f"[GSM FORCE] {self._state!r} -> {new_state!r}")
        self._do(new_state)

    def is_in(self, *states: str) -> bool:
        return self._state in states

    @property
    def previous(self) -> str | None:
        return self._previous

    @property
    def history(self) -> list[str]:
        return list(self._history)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self._state == other
        if isinstance(other, GameStateManager):
            return self._state == other._state
        return NotImplemented

    def __str__(self)  -> str: return self._state
    def __repr__(self) -> str: return f"GameStateManager({self._state!r})"

    def _do(self, new_state: str) -> None:
        print(f"[GSM] {self._state!r} -> {new_state!r}")
        self._history.append(self._state)
        self._previous = self._state
        self._state    = new_state