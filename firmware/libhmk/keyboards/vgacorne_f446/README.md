# VGACorne (f446 module)

VGACorne is a hall-effect split Corne (3×6 + 3) whose MCU sits on a
swappable module. The right half's analog muxes are read over a VGA cable.
This keyboard is for the **STM32F446RET6 (USB full speed, 1 kHz)** module.

- **Hardware:** [VGACorne](../../../../README.md)
- **Bootloader:** factory DFU bootloader. To enter it:
  - hold **BOOT** (reachable through the case floor) while plugging in the keyboard,
  - press the `SP_BOOT` binding, or
  - use the web configurator.
- Needs [`detachable.patch`](../../detachable.patch): the VGA cable can be
  plugged and unplugged with the keyboard running. Keep your hands off the
  left half for half a second after plugging it in, while it calibrates.
