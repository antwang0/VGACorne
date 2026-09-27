# VGACorne (at32 module)

VGACorne is a hall-effect split Corne (3×6 + 3) whose MCU sits on a
swappable module. The right half's analog muxes are read over a VGA cable.
This keyboard is for the **AT32F405RCT7 (USB high speed, 8 kHz)** module.

- **Hardware:** [VGACorne](../../../../README.md)
- **Bootloader:** factory DFU bootloader. To enter it:
  - hold **BOOT** (reachable through the case floor) while plugging in the keyboard,
  - press the `SP_BOOT` binding, or
  - use the web configurator.
- Connect the VGA cable **before** USB: rest values are calibrated at start-up.
