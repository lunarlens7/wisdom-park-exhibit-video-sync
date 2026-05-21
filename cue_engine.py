from config import CueConfig

NEAR_ZERO_THRESHOLD = 1.0  # seconds — seeks to within this of 0 trigger a full reset


class CueEngine:
    def __init__(self, cues: list[CueConfig]):
        self._cues = cues
        self._fired: set[int] = set()
        self._last_position: float = 0.0
        self.did_reset: bool = False

    def tick(self, position: float) -> list[CueConfig]:
        self.did_reset = False

        # Detect seek backward
        if position < self._last_position - 0.5:
            if position <= NEAR_ZERO_THRESHOLD:
                self._fired.clear()
                self.did_reset = True
            else:
                self._fired = {
                    i for i in self._fired if self._cues[i].at <= position
                }

        self._last_position = position

        to_fire = []
        for i, cue in enumerate(self._cues):
            if i not in self._fired and cue.at <= position:
                self._fired.add(i)
                to_fire.append(cue)

        return to_fire
