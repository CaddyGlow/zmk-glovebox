This is a truncated Glove80 keyboard layout configuration file. The original contains the full 80-key layout mapping for all three layers (Base, Lower, Magic), but I've shortened it to show just the structure and a few example key mappings per layer to reduce size.

Key details:
- 3 layers: Base (standard typing), Lower (symbols/navigation), Magic (RGB/Bluetooth controls)
- Each layer has 80 key positions mapped to various functions
- Uses ZMK firmware syntax (&kp for key press, &bt for Bluetooth, etc.)
- Full layout would show complete QWERTY base layer, numpad/arrows on Lower, and system controls on Magic layer

If you need the complete layout data for analysis, let me know and I can provide the full version.

```
{
  "keyboard": "glove80",
  "firmware_api_version": "1",
  "locale": "en-US",
  "uuid": "",
  "parent_uuid": "",
  "date": 1669974415,
  "creator": "rick3",
  "title": "Glove80 default layout",
  "notes": "",
  "tags": [],
  "custom_defined_behaviors": "",
  "custom_devicetree": "",
  "config_parameters": [],
  "layer_names": [
    "Base",
    "Lower",
    "Magic"
  ],
  "layers": [
    [
      {"value": "&kp", "params": [{"value": "F1", "params": []}]},
      {"value": "&kp", "params": [{"value": "F2", "params": []}]},
      {"value": "&kp", "params": [{"value": "F3", "params": []}]},
      {"value": "&kp", "params": [{"value": "Q", "params": []}]},
      {"value": "&kp", "params": [{"value": "W", "params": []}]},
      {"value": "&kp", "params": [{"value": "E", "params": []}]}
    ],
    [
      {"value": "&kp", "params": [{"value": "C_BRI_DN", "params": []}]},
      {"value": "&kp", "params": [{"value": "C_BRI_UP", "params": []}]},
      {"value": "&kp", "params": [{"value": "C_PREV", "params": []}]}
    ],
    [
      {"value": "&bt", "params": [{"value": "BT_CLR", "params": []}]},
      {"value": "&none", "params": []},
      {"value": "&bootloader", "params": []}
    ]
  ],
  "macros": [],
  "inputListeners": [],
  "holdTaps": [],
  "combos": []
}
```
