{ firmware, ... }:

firmware.combine_uf2 {
  glove80_left = firmware.build {
    board = "glove80_lh";
    keymap = "glove80.keymap";
    kconfig = "glove80.conf";
  };
  glove80_right = firmware.build {
    board = "glove80_rh";
    keymap = "glove80.keymap";
    kconfig = "glove80.conf";
  };
}