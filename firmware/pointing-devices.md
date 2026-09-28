# Pointing devices: status and plans

Where the trackpad, the scroll wheel and the mouse-button keys stand in each
firmware, what is known to be wrong, and the planned fixes. Nothing here is
implemented yet unless it says so. Checked against QMK master `b1aea255`
(September 2026) and libhmk `main` `ad426f0` (July 2026).

| | QMK, STM32F446 module (1 kHz) | libhmk, AT32F405 module (8 kHz) |
|---|---|---|
| Mouse-button keys (42, 43) | works | works (`MS_BTN1`/`MS_BTN2`) |
| Scroll wheel | works | not supported: [plan](#libhmk-scroll-wheel) |
| Trackpad | works, blocking reads: [plan](#qmk-trackpad-in-its-own-thread) | not supported: [plan](#libhmk-trackpad) |

The hardware is the same for both modules; every gap below is firmware.

## The problem: blocking trackpad reads

QMK's `azoteq_iqs5xx` driver polls the pad every 11 ms
(`AZOTEQ_IQS5XX_REPORT_RATE` + 1). Each poll reads 10 bytes of base data and
then writes the end-of-communication register, about 15 bytes on the bus or
~0.45 ms at 400 kHz. The calls are blocking: QMK's main loop, which also runs
our hall-effect matrix scan, waits until they finish.

- **Normal case:** keys are held up ~0.45 ms every 11 ms. At 1 kHz that
  mostly goes unnoticed.
- **Clock stretching:** the IQS5xx holds SCL low when it is addressed outside
  its communication window. Its RDY pin would say when to read, but all 24
  module pins are in use, so RDY isn't connected. The worst case is the
  driver's `AZOTEQ_IQS5XX_TIMEOUT_MS`, 10 ms, and keys wait that long too.
  How often this happens with our polling pattern is **not measured**.

**At bring-up:** build with `CONSOLE_ENABLE = yes` and
`POINTING_DEVICE_DEBUG`; the driver prints a warning with the pad's cycle
time whenever it misses its report rate. Time the polls with a logic analyser
on PB6/PB7 if you have one.

## QMK: known tap bug

From reading the code (not confirmed on hardware): in QMK master,
`azoteq_iqs5xx_get_report()` starts from the button state of the previous
report. `pointing_device_send()` keeps buttons between reports, and the driver
sets button 1 on a tap but never clears it. So a tap may leave the left button
held until a mouse-button key is pressed and released. It came in with PR
#26248 (June 2026); PR #26357, which described the risk, was closed unmerged.
The Cirque driver releases its buttons properly. The thread wrapper below fixes
it as a side effect.

## QMK: trackpad in its own thread

QMK runs on ChibiOS. ChibiOS's I2C driver is interrupt/DMA-driven, and
`i2cMasterTransmitTimeout()` only suspends the calling thread. Moving the pad
reads to a worker thread means only that thread waits; the key scan never does.

Plan, about 100–150 lines, one new file (e.g. `trackpad_thread.c`):

1. **Custom driver.** Set `POINTING_DEVICE_DRIVER = custom` in the generated
   `rules.mk` (`hardware/vgacorne/qmk.py`). Compile the stock driver source
   (`drivers/sensors/azoteq_iqs5xx.c` or the Cirque one, following
   `trackpad.MODEL`) and set `I2C_DRIVER_REQUIRED = yes`.
2. **Init.** `pointing_device_driver_init()` runs the stock driver's init in
   the main thread at boot (blocking is fine there), then starts the worker.
3. **Worker thread** (`chThdCreateStatic`, ~512 B stack), in a loop:
   - sleep until the next poll (~10 ms);
   - call the stock `…_get_report()` with an empty report, so it can't carry
     old buttons (the tap-bug fix);
   - under `chSysLock()`, add X/Y/H/V into an accumulator and store the
     current button state;
   - retry the stock init if it failed at boot, e.g. when the pad was plugged
     in late.
4. **Priority.** The worker must run *above* the main thread
   (`NORMALPRIO + 1`). QMK's main loop never sleeps, so a lower-priority
   thread would never run. The worker is asleep, or waiting on the I2C
   interrupt, almost all the time, so it doesn't take time from the keys.
5. **Main thread.** `pointing_device_driver_get_report()` takes the
   accumulated movement, clears it and returns it with the latest buttons, in
   microseconds. Define `POINTING_DEVICE_TASK_THROTTLE_MS` as 1 in `config.h`
   (the Azoteq header otherwise sets it to 11) so reports go out as soon as
   there is data.
6. Nothing else in our firmware uses I2C (settings live in flash), so the bus
   needs no locking.

Test on hardware: tap-to-click presses and releases, two-finger scroll, and
key timing with the pad busy (console or logic analyser). Compare against the
blocking build.

## libhmk: scroll wheel

libhmk only stores ADC samples for mux channels that are keys (`adc_values[key]`
in `src/hardware/<mcu>/analog.c`). The wheel's channel is 0 in the matrix, so
it is scanned and thrown away, and libhmk has no encoder code. Plan, about
60–100 lines:

1. In the ADC interrupt, keep the wheel channel's raw sample next to
   `adc_values`. The wheel's input and channel come from the traced wiring:
   `firmware.Wiring.wheel`, already written to QMK's `he_wiring.h` as
   `HE_WHEEL_INPUT` / `HE_WHEEL_CHANNEL`.
2. Decode the nearest of the four levels (`HE_WHEEL_LEVELS`, from
   `qmk.wheel_levels()`) into the A/B contact states, as `he_matrix.c` does.
3. Count steps with the usual quadrature table (4 transitions per detent).
   Put the count in `mouse_report.wheel`: libhmk's mouse report is TinyUSB's
   `hid_mouse_report_t`, which already has `wheel` and `pan`. Only `buttons`
   is filled today.
4. The wheel settings need a place in libhmk's `keyboard.json` schema and code
   generator for an upstream PR, or `#define`s in the board header for a fork.

It doesn't slow the key scan: the decode is a few comparisons per scan.

## libhmk: trackpad

libhmk is bare-metal, with no threads and no I2C, so the pad read becomes a
state machine: start a transfer, return, and check each main-loop pass whether
it has finished. About 400–600 lines and a few days, mostly I2C debugging on
hardware:

| Piece | Work |
|---|---|
| I2C on the AT32 | Artery's `i2c_application` library (in the AT32F402/405 SDK libhmk builds against; not in libhmk's build yet) has `i2c_memory_read_int/_dma` and `i2c_memory_write_int/_dma` with 16-bit register addresses, which is how the IQS5xx is accessed. Add it to the build, wire the event/error/DMA interrupts, set PB6/PB7 to MUX4, and set up 400 kHz timing. Check `hi2c->status` each pass instead of calling `i2c_wait_end()`. About 100–150 lines. |
| IQS5xx driver | Port QMK's driver: GPL-2.0-or-later, so fine in GPL-3 libhmk. Init can stay blocking at boot. The periodic read becomes: start the 10-byte read, then (when done) start the end-of-comms write, then (when done) decode gestures into X/Y/wheel/buttons. About 200–300 lines. |
| USB report | Fill `x`, `y`, `wheel`, `pan` in the existing mouse report and send it when it changes. About 50 lines. |
| Configuration | I2C pins and pad options: schema and generator for upstream, or board defines for a fork. |
| STM32F446 build | Optional: its I2C hardware differs, and that module has QMK. |

A blocking port would be simpler but costs the 8 kHz key rate: ~0.45 ms per
poll is 3–4 report slots, and a clock stretch up to 80.

Whether libhmk's maintainer wants pointing devices upstream is an open
question; otherwise this lives in a fork. Do the scroll wheel first: it is
small and independent.
