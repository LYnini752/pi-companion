"""GPIO Zero mock pins exercise control flow only, not electrical wiring."""
import pytest
import companion

gpiozero = pytest.importorskip('gpiozero')
from gpiozero.pins.mock import MockFactory


@pytest.mark.parametrize('fail', [False, True])
def test_gpio_press_turn_release_and_cleanup(monkeypatch, fail):
    previous_factory = gpiozero.Device.pin_factory
    factory = MockFactory(); gpiozero.Device.pin_factory = factory
    original = gpiozero.Button
    devices, waits, played = [], [], []
    def make_button(*args, **kwargs):
        button = original(*args, **kwargs); devices.append(button)
        original_wait = button.wait_for_press
        def wait(*args, **kwargs):
            waits.append(True)
            if len(waits) > 1:
                raise KeyboardInterrupt
            button.pin.drive_low()
            return original_wait(*args, **kwargs)
        monkeypatch.setattr(button, 'wait_for_press', wait)
        return button
    monkeypatch.setattr(gpiozero, 'Button', make_button)
    def turn(history, config, released, status):
        assert not released() and factory.pin(27).state is True
        devices[0].pin.drive_high()
        assert released()
        if fail:
            raise ValueError('test recording failure')
        status('思考中')
        return 'question', 'answer', [{'role':'user','content':'question'}], [0.1], 16000, {}
    monkeypatch.setattr(companion, 'microphone_turn', turn)
    monkeypatch.setattr(companion, 'play', lambda *args: played.append(True))
    try:
        with pytest.raises(KeyboardInterrupt):
            companion.gpio_loop({}, 17, 27)
        assert devices[0].closed
        assert factory.pin(27).state is False
        assert len(played) == (0 if fail else 1)
        assert len(waits) == 2
    finally:
        factory.close(); gpiozero.Device.pin_factory = previous_factory
