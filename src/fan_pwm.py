"""Explicit control of the already configured Raspberry Pi 5 fan PWM.

Import and construction do not access hardware. Entering the context acquires
an advisory lock and reads the configuration; only ``set_percent`` / ``stop``
write it. Keep the context open throughout a recording. Closing it leaves the
last output setting unchanged. A configured duty cycle is never an RPM or
mechanical-state measurement.

Example (announce the change and confirm the bench conditions beforehand)::

    with FanPWM(journal_path="results/new_session/fan.jsonl") as fan:
        fan.set_percent(25)
        # Stabilise and record while this context retains the lock.
        # fan.stop() is a separate, explicit request, if wanted.

The backend is the existing Linux hardware-PWM channel, not software PWM.
The lock coordinates users of this class; direct pinctrl/sysfs writes and
unrelated programs do not honour it and still require a process check.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4


GPIO_BCM = 18
PHYSICAL_PIN = 12
PWM_CHIP = 0
PWM_CHANNEL = 2
PERIOD_NS = 40_000
PWM_FUNCTION = "a3"
PWM_FUNCTION_NAME = "PWM0_CHAN2"
RP1_DEVICE_NAME = "1f00098000.pwm"
RP1_COMPATIBLE = b"raspberrypi,rp1-pwm"
DEFAULT_PWM_PATH = Path("/sys/class/pwm/pwmchip0/pwm2")
DEFAULT_LOCK_PATH = Path("/tmp/edge-ai-fan-gpio18.lock")


class FanPWMError(RuntimeError):
    """A command or configuration could not be confirmed."""


class FanPWMBusy(FanPWMError):
    """Another cooperating controller already owns the fan lock."""


class FanPWM:
    """Control BCM18 / physical pin 12 using exported RP1 PWM0 channel 2.

    ``pwm_path`` and ``runner`` can be replaced with fixtures for hardware-free
    tests. Even with an alternate path, device identity, channel, polarity and
    period must pass the same checks. No PWM export, boot configuration or
    package installation is performed.
    """

    def __init__(
        self,
        *,
        journal_path: str | Path,
        pwm_path: str | Path = DEFAULT_PWM_PATH,
        lock_path: str | Path = DEFAULT_LOCK_PATH,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.journal_path = Path(journal_path)
        self.pwm_path = Path(pwm_path)
        self.lock_path = Path(lock_path)
        self._runner = runner
        self._lock_fd: int | None = None
        self._mutex = threading.RLock()
        self._session_id = uuid4().hex
        self._transaction_id: str | None = None

    def _journal(self, event: str, **details: Any) -> None:
        record = {
            "schema_version": 1,
            "utc": datetime.now(timezone.utc).isoformat(),
            "monotonic_ns": time.monotonic_ns(),
            "session_id": self._session_id,
            "transaction_id": self._transaction_id,
            "pid": os.getpid(),
            "event": event,
            "gpio_bcm": GPIO_BCM,
            "physical_pin": PHYSICAL_PIN,
            **details,
        }
        # A failed intent journal prevents the subsequent hardware write.
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self.journal_path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def _record_failure(self, event: str, error: BaseException, **details: Any) -> None:
        # Preserve the original failure if the journal itself is unavailable.
        try:
            self._journal(event, error_type=type(error).__name__, error=str(error), **details)
        except OSError:
            pass

    def __enter__(self) -> FanPWM:
        with self._mutex:
            if self._lock_fd is not None:
                raise FanPWMError("This controller already holds its lock.")
            fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                os.close(fd)
                error = FanPWMBusy(f"Fan control lock is held: {self.lock_path}")
                self._record_failure("lock_busy", error)
                raise error from exc
            except BaseException:
                os.close(fd)
                raise
            self._lock_fd = fd
            try:
                self._journal("lock_acquired", lock_path=str(self.lock_path))
                state = self._read_state()
                self._journal("preflight_passed", state=state, hardware_changed=False)
            except BaseException as exc:
                self._record_failure("preflight_failed", exc, hardware_changed=False)
                self._release_lock()
                raise
            return self

    def _release_lock(self) -> None:
        fd, self._lock_fd = self._lock_fd, None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def close(self) -> None:
        """Release the lock without changing the configured fan output."""
        with self._mutex:
            if self._lock_fd is None:
                return
            try:
                self._journal("lock_released", hardware_changed=False,
                              output_policy="leave_last_setting_unchanged")
            finally:
                self._release_lock()

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> bool:
        try:
            self.close()
        except OSError:
            if exc is None:
                raise
        return False

    def _require_lock(self) -> None:
        if self._lock_fd is None:
            raise FanPWMError("Use the controller as a context manager to hold its lock.")

    def _validate_device(self) -> Path:
        chip = self.pwm_path.parent
        if self.pwm_path.name != "pwm2" or chip.name != "pwmchip0":
            raise FanPWMError("Expected exported pwmchip0/pwm2 for BCM18, physical pin 12.")
        try:
            channel = self.pwm_path.resolve(strict=True)
            device = (chip / "device").resolve(strict=True)
            compatible = (device / "of_node" / "compatible").read_bytes().split(b"\0")
            channel_count = int((chip / "npwm").read_text().strip())
        except (OSError, ValueError) as exc:
            raise FanPWMError(f"Cannot verify the existing exported RP1 PWM channel: {exc}") from exc
        if (
            device.name != RP1_DEVICE_NAME
            or RP1_COMPATIBLE not in compatible
            or channel.name != "pwm2"
            or channel.parent.name != "pwmchip0"
            or channel.parents[1].name != "pwm"
            or channel.parents[2] != device
            or channel_count < 3
        ):
            raise FanPWMError("PWM channel does not belong to the expected RP1 PWM0 device.")
        return device

    def _read_attributes(self) -> dict[str, Any]:
        try:
            period = int((self.pwm_path / "period").read_text().strip())
            duty = int((self.pwm_path / "duty_cycle").read_text().strip())
            enable = int((self.pwm_path / "enable").read_text().strip())
            polarity = (self.pwm_path / "polarity").read_text().strip()
        except (OSError, ValueError) as exc:
            raise FanPWMError(f"Cannot read PWM configuration: {exc}") from exc
        if period != PERIOD_NS or polarity != "normal":
            raise FanPWMError("Expected an existing 40,000 ns period and normal polarity; no change made.")
        if not 0 <= duty <= period or enable not in {0, 1}:
            raise FanPWMError("Invalid PWM duty_cycle or enable readback.")
        return {
            "period_ns": period,
            "duty_cycle_ns": duty,
            "enable": enable,
            "polarity": polarity,
            "configured_frequency_hz": 1_000_000_000 / period,
            "configured_duty_percent": 100 * duty / period,
        }

    def _pinctrl(self, *arguments: str) -> str:
        command = ["pinctrl", *arguments]
        self._journal("command_intent", command=command)
        try:
            result = self._runner(command, check=False, capture_output=True, text=True, timeout=5)
            self._journal("command_result", command=command, returncode=result.returncode,
                          stdout=result.stdout, stderr=result.stderr)
            if result.returncode != 0:
                raise FanPWMError(f"pinctrl failed ({result.returncode}): {result.stderr.strip()}")
            return result.stdout.strip()
        except BaseException as exc:
            self._record_failure("command_failed", exc, command=command)
            raise

    def _read_pin(self) -> dict[str, str]:
        raw = self._pinctrl("get", str(GPIO_BCM))
        match = re.fullmatch(
            r"18:\s+(?P<mux>\w+)\s+[^|]*\|\s*(?P<level>hi|lo)\s*//\s*"
            r"(?:PIN12/)?GPIO18\s*=\s*(?P<function>[^\r\n]+)", raw,
        )
        if match is None:
            raise FanPWMError(f"Cannot verify pinctrl readback for BCM18: {raw!r}")
        return {
            "mux": match["mux"],
            "function": match["function"].strip(),
            "instantaneous_level": match["level"],
            "raw": raw,
        }

    def _read_state(self) -> dict[str, Any]:
        device = self._validate_device()
        attributes = self._read_attributes()
        pin = self._read_pin()
        return {
            "gpio_bcm": GPIO_BCM,
            "physical_pin": PHYSICAL_PIN,
            "pwm_chip": PWM_CHIP,
            "pwm_channel": PWM_CHANNEL,
            "pwm_path": str(self.pwm_path),
            "rp1_device_path": str(device),
            "pwm_configuration": attributes,
            "pin_readback": pin,
            "pwm_mux_confirmed": pin["mux"] == PWM_FUNCTION and pin["function"] == PWM_FUNCTION_NAME,
            "electrical_waveform_measured": False,
            "measured_rpm": None,
            "mechanical_state": "not_measured",
        }

    def read_state(self) -> dict[str, Any]:
        """Read pinmux and software configuration, with no output changes."""
        with self._mutex:
            self._require_lock()
            state = self._read_state()
            self._journal("state_readback", state=state)
            return state

    def verify(self, expected_percent: float) -> dict[str, Any]:
        """Read and check a held operating point, without changing any output.

        This checks the PWM configuration and pinmux only. It does not verify
        an electrical waveform, a fan speed, or mechanical standstill.
        """
        with self._mutex:
            self._require_lock()
            expected = self._percent(expected_percent)
            expected_ns = round(PERIOD_NS * expected / 100)
            try:
                state = self._read_state()
                config = state["pwm_configuration"]
                if not state["pwm_mux_confirmed"] or config["enable"] != 1 or config["duty_cycle_ns"] != expected_ns:
                    raise FanPWMError("Held PWM setting or pinmux changed; recording conditions are unconfirmed.")
                self._journal("setting_verified", expected_percent=expected, state=state)
                return state
            except BaseException as exc:
                self._record_failure("setting_verification_failed", exc, expected_percent=expected)
                raise

    def _write_attribute(self, attribute: str, value: int) -> None:
        if attribute not in {"duty_cycle", "enable"}:
            raise FanPWMError("Only duty_cycle and enable may be written.")
        path = self.pwm_path / attribute
        self._journal("sysfs_write_intent", path=str(path), value=value)
        try:
            path.write_text(str(value), encoding="ascii")
            actual = int(path.read_text().strip())
            self._journal("sysfs_write_readback", path=str(path), expected=value, actual=actual)
            if actual != value:
                raise FanPWMError(f"PWM readback mismatch for {attribute}: {actual} != {value}.")
        except BaseException as exc:
            self._record_failure("sysfs_write_failed", exc, path=str(path), requested_value=value)
            raise

    @staticmethod
    def _percent(value: float) -> float:
        try:
            percent = float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("Duty cycle must be a finite percentage in 0..100.") from exc
        if isinstance(value, bool) or not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError("Duty cycle must be a finite percentage in 0..100.")
        return percent

    def set_percent(self, percent: float) -> dict[str, Any]:
        """Apply an explicitly requested setting; never infer actual rotation.

        On a stale digital/input mux, set a digital Low first, configure zero
        enabled duty, and only then restore a3 and apply the requested target.
        Every write is journalled before execution and checked afterwards.
        Failures stop further commands, without an implicit rollback: the
        partially applied state must be inspected before any recording.
        """
        with self._mutex:
            self._require_lock()
            try:
                requested = self._percent(percent)
            except ValueError as exc:
                self._record_failure("setting_request_rejected", exc, requested_input=repr(percent))
                raise
            target_ns = round(PERIOD_NS * requested / 100)
            self._transaction_id = uuid4().hex
            try:
                self._journal("transaction_begin", requested_percent=requested,
                              requested_duty_cycle_ns=target_ns)
                before = self._read_state()
                self._journal("transaction_preflight", state=before)
                if not before["pwm_mux_confirmed"]:
                    if before["pin_readback"]["mux"] not in {"op", "ip"}:
                        raise FanPWMError("Unexpected alternate pin function; output was not changed.")
                    self._pinctrl("set", str(GPIO_BCM), "op", "dl")
                    low_pin = self._read_pin()
                    if low_pin["mux"] != "op" or low_pin["instantaneous_level"] != "lo":
                        raise FanPWMError("Digital Low could not be confirmed before restoring PWM.")
                    self._write_attribute("duty_cycle", 0)
                    self._write_attribute("enable", 1)
                    self._pinctrl("set", str(GPIO_BCM), PWM_FUNCTION)
                    restored = self._read_pin()
                    if restored["mux"] != PWM_FUNCTION or restored["function"] != PWM_FUNCTION_NAME:
                        raise FanPWMError("PWM pin function could not be restored and confirmed.")
                elif before["pwm_configuration"]["enable"] != 1:
                    self._write_attribute("duty_cycle", 0)
                    self._write_attribute("enable", 1)

                self._write_attribute("duty_cycle", target_ns)
                after = self._read_state()
                if (
                    not after["pwm_mux_confirmed"]
                    or after["pwm_configuration"]["duty_cycle_ns"] != target_ns
                    or after["pwm_configuration"]["enable"] != 1
                ):
                    raise FanPWMError("Final PWM setting or pinmux could not be confirmed.")
                self._journal("transaction_complete", requested_percent=requested, state=after)
                return after
            except BaseException as exc:
                self._record_failure("transaction_failed", exc,
                                     requested_percent=requested,
                                     possible_partial_change=True,
                                     mechanical_state="not_measured",
                                     rollback_performed=False)
                raise
            finally:
                self._transaction_id = None

    def stop(self) -> dict[str, Any]:
        """Explicitly request enabled 0 % PWM; actual standstill needs confirmation."""
        return self.set_percent(0)
