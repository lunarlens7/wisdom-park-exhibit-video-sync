import pytest
from config import CueConfig
from cue_engine import CueEngine


def make_engine(cues):
    return CueEngine(cues)


def cue(at, device, action, **kwargs):
    return CueConfig(at=at, devices=[device], action=action, **kwargs)


def test_fires_cue_when_position_passes_timestamp():
    engine = make_engine([cue(10.0, "light", "on")])
    result = engine.tick(10.1)
    assert len(result) == 1
    assert result[0].devices[0] == "light"


def test_does_not_fire_cue_before_timestamp():
    engine = make_engine([cue(10.0, "light", "on")])
    result = engine.tick(9.9)
    assert result == []


def test_cue_fires_only_once():
    engine = make_engine([cue(10.0, "light", "on")])
    engine.tick(10.1)
    result = engine.tick(10.2)
    assert result == []


def test_fires_multiple_cues_at_same_tick():
    engine = make_engine([
        cue(5.0, "light", "on"),
        cue(5.0, "switch", "off"),
    ])
    result = engine.tick(5.1)
    assert len(result) == 2


def test_seek_backward_resets_cues_ahead_of_new_position():
    engine = make_engine([cue(10.0, "light", "on"), cue(20.0, "switch", "off")])
    engine.tick(25.0)  # fires both
    engine.tick(8.0)   # seek back to 8s — should reset both cues
    result = engine.tick(10.1)
    assert len(result) == 1
    assert result[0].devices[0] == "light"


def test_seek_to_zero_resets_all_cues():
    engine = make_engine([cue(5.0, "light", "on"), cue(15.0, "switch", "off")])
    engine.tick(20.0)
    engine.tick(0.0)
    result1 = engine.tick(5.1)
    result2 = engine.tick(15.1)
    assert len(result1) == 1
    assert len(result2) == 1


def test_returns_reset_signal_on_seek_to_near_zero():
    engine = make_engine([cue(10.0, "light", "on")])
    engine.tick(30.0)
    engine.tick(0.5)
    assert engine.did_reset  # engine exposes whether a full reset just occurred
