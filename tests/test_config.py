import pytest
from config import load_config, ConfigError

VALID_YAML = """
video:
  loop: true
  fullscreen: false
  screens:
    - path: "exhibit.mp4"
      window_title: "Screen 1"
      monitor: 0
    - path: "exhibit2.mp4"
      window_title: "Screen 2"
      monitor: 1

devices:
  main_light:
    type: l530
    ip: "192.168.1.101"
    initial_state:
      on: true
      brightness: 100
      hue: 30
      saturation: 80
  stage_switch:
    type: p100
    ip: "192.168.1.102"
    initial_state:
      on: false

cues:
  - at: 10.5
    device: main_light
    action: fade
    to_brightness: 20
    to_hue: 200
    to_saturation: 100
    duration: 5.0
  - at: 30.0
    device: stage_switch
    action: "on"
"""

def test_load_valid_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TAPO_EMAIL", "test@example.com")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    f = tmp_path / "config.yaml"
    f.write_text(VALID_YAML)
    cfg = load_config(str(f))
    assert cfg.tapo.email == "test@example.com"
    assert cfg.tapo.password == "secret"
    assert len(cfg.video.screens) == 2
    assert cfg.video.screens[0].path == "exhibit.mp4"
    assert cfg.video.screens[1].monitor == 1
    assert cfg.video.loop is True
    assert "main_light" in cfg.devices
    assert cfg.devices["main_light"].type == "l530"
    assert cfg.devices["main_light"].initial_state["brightness"] == 100
    assert len(cfg.cues) == 2

def test_missing_env_vars_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("TAPO_EMAIL", raising=False)
    monkeypatch.delenv("TAPO_PASSWORD", raising=False)
    f = tmp_path / "config.yaml"
    f.write_text(VALID_YAML)
    with pytest.raises(ConfigError, match="TAPO_EMAIL"):
        load_config(str(f))

def test_unknown_device_in_cue(tmp_path, monkeypatch):
    monkeypatch.setenv("TAPO_EMAIL", "test@example.com")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    bad = VALID_YAML.replace("main_light\n    action: fade", "nonexistent\n    action: fade")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="nonexistent"):
        load_config(str(f))

def test_unknown_device_type(tmp_path, monkeypatch):
    monkeypatch.setenv("TAPO_EMAIL", "test@example.com")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    bad = VALID_YAML.replace("type: l530", "type: unknown_model")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="unknown_model"):
        load_config(str(f))

def test_fade_cue_requires_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("TAPO_EMAIL", "test@example.com")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    bad = VALID_YAML.replace("    duration: 5.0\n", "")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="duration"):
        load_config(str(f))

def test_missing_screens_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("TAPO_EMAIL", "test@example.com")
    monkeypatch.setenv("TAPO_PASSWORD", "secret")
    bad = VALID_YAML.replace("  screens:\n    - path: \"exhibit.mp4\"\n      window_title: \"Screen 1\"\n      monitor: 0\n    - path: \"exhibit2.mp4\"\n      window_title: \"Screen 2\"\n      monitor: 1\n", "  screens: []\n")
    f = tmp_path / "config.yaml"
    f.write_text(bad)
    with pytest.raises(ConfigError, match="screens"):
        load_config(str(f))
