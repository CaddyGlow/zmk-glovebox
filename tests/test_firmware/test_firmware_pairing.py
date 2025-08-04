"""Tests for firmware pairing service."""

from pathlib import Path

import pytest

from glovebox.firmware.flash.firmware_pairing import (
    FirmwarePairingService,
    create_firmware_pairing_service,
)
from glovebox.firmware.flash.models import (
    FirmwarePair,
    FirmwareSide,
    detect_firmware_side,
    is_split_firmware,
)


class TestFirmwareSideDetection:
    """Test firmware side detection."""

    @pytest.mark.parametrize(
        "filename,expected_side",
        [
            ("glove80_lh.uf2", FirmwareSide.LEFT),
            ("glove80_rh.uf2", FirmwareSide.RIGHT),
            ("firmware_left.uf2", FirmwareSide.LEFT),
            ("firmware_right.uf2", FirmwareSide.RIGHT),
            ("keyboard-left.uf2", FirmwareSide.LEFT),
            ("keyboard-right.uf2", FirmwareSide.RIGHT),
            ("left_firmware.uf2", FirmwareSide.LEFT),
            ("right_firmware.uf2", FirmwareSide.RIGHT),
            ("unified.uf2", FirmwareSide.UNIFIED),
            ("firmware.uf2", FirmwareSide.UNIFIED),
        ],
    )
    def test_detect_firmware_side(
        self, filename: str, expected_side: FirmwareSide
    ) -> None:
        """Test detection of firmware side from filename."""
        path = Path(filename)
        assert detect_firmware_side(path) == expected_side

    def test_is_split_firmware_pair(self, tmp_path: Path) -> None:
        """Test detection of split firmware pairs."""
        left = tmp_path / "keyboard_lh.uf2"
        right = tmp_path / "keyboard_rh.uf2"
        unified = tmp_path / "unified.uf2"

        # Create files
        left.touch()
        right.touch()
        unified.touch()

        # Test valid pair
        assert is_split_firmware([left, right]) is True

        # Test single file
        assert is_split_firmware([unified]) is False

        # Test two unified files
        assert is_split_firmware([unified, unified]) is False

        # Test more than two files
        assert is_split_firmware([left, right, unified]) is False


class TestFirmwarePairingService:
    """Test firmware pairing service."""

    @pytest.fixture
    def pairing_service(self) -> FirmwarePairingService:
        """Create a pairing service."""
        return create_firmware_pairing_service()

    def test_detect_firmware_pairs(
        self, pairing_service: FirmwarePairingService, tmp_path: Path
    ) -> None:
        """Test detection of firmware pairs from file list."""
        # Create test files
        left1 = tmp_path / "keyboard_lh.uf2"
        right1 = tmp_path / "keyboard_rh.uf2"
        left2 = tmp_path / "other_left.uf2"
        right2 = tmp_path / "other_right.uf2"
        unified = tmp_path / "unified.uf2"

        for f in [left1, right1, left2, right2, unified]:
            f.touch()

        # Test detection
        pairs = pairing_service.detect_firmware_pairs(
            [left1, right1, left2, right2, unified]
        )

        assert len(pairs) == 2
        # Check that pairs are correctly matched
        pair_bases = {pair.base_name for pair in pairs}
        assert "keyboard" in pair_bases or "keyboard_" in pair_bases
        assert "other" in pair_bases or "other_" in pair_bases

    def test_detect_duplicate_side_error(
        self, pairing_service: FirmwarePairingService, tmp_path: Path
    ) -> None:
        """Test that duplicate sides raise an error."""
        left1 = tmp_path / "keyboard_lh.uf2"
        left2 = tmp_path / "keyboard_left.uf2"

        left1.touch()
        left2.touch()

        with pytest.raises(ValueError, match="Duplicate left firmware"):
            pairing_service.detect_firmware_pairs([left1, left2])

    def test_match_device_to_side(
        self, pairing_service: FirmwarePairingService
    ) -> None:
        """Test matching devices to their sides."""
        # Test serial number patterns
        assert (
            pairing_service.match_device_to_side("GLV80-LEFT-001", "device")
            == FirmwareSide.LEFT
        )
        assert (
            pairing_service.match_device_to_side("GLV80-RIGHT-002", "device")
            == FirmwareSide.RIGHT
        )
        assert (
            pairing_service.match_device_to_side("GLV80_LH_001", "device")
            == FirmwareSide.LEFT
        )
        assert (
            pairing_service.match_device_to_side("GLV80_RH_002", "device")
            == FirmwareSide.RIGHT
        )

        # Test device name patterns
        assert (
            pairing_service.match_device_to_side("serial", "left_device")
            == FirmwareSide.LEFT
        )
        assert (
            pairing_service.match_device_to_side("serial", "right_device")
            == FirmwareSide.RIGHT
        )

        # Test odd/even convention
        assert (
            pairing_service.match_device_to_side("GLV80-001", "device")
            == FirmwareSide.LEFT
        )
        assert (
            pairing_service.match_device_to_side("GLV80-002", "device")
            == FirmwareSide.RIGHT
        )

        # Test unknown
        assert pairing_service.match_device_to_side("unknown", "device") is None

    def test_validate_pairing(self, pairing_service: FirmwarePairingService) -> None:
        """Test firmware-device pairing validation."""
        # Matching sides should be valid
        assert (
            pairing_service.validate_pairing(FirmwareSide.LEFT, FirmwareSide.LEFT)
            is True
        )
        assert (
            pairing_service.validate_pairing(FirmwareSide.RIGHT, FirmwareSide.RIGHT)
            is True
        )

        # Mismatched sides should be invalid
        assert (
            pairing_service.validate_pairing(FirmwareSide.LEFT, FirmwareSide.RIGHT)
            is False
        )
        assert (
            pairing_service.validate_pairing(FirmwareSide.RIGHT, FirmwareSide.LEFT)
            is False
        )

        # Unified firmware can go to any device
        assert (
            pairing_service.validate_pairing(FirmwareSide.UNIFIED, FirmwareSide.LEFT)
            is True
        )
        assert (
            pairing_service.validate_pairing(FirmwareSide.UNIFIED, FirmwareSide.RIGHT)
            is True
        )
        assert pairing_service.validate_pairing(FirmwareSide.UNIFIED, None) is True

        # Unknown device side allows any firmware (user responsibility)
        assert pairing_service.validate_pairing(FirmwareSide.LEFT, None) is True
        assert pairing_service.validate_pairing(FirmwareSide.RIGHT, None) is True

    def test_extract_base_name(self, pairing_service: FirmwarePairingService) -> None:
        """Test base name extraction from firmware files."""
        # Test various naming patterns
        test_cases = [
            (Path("keyboard_lh.uf2"), FirmwareSide.LEFT, "keyboard"),
            (Path("keyboard_rh.uf2"), FirmwareSide.RIGHT, "keyboard"),
            (Path("firmware_left.uf2"), FirmwareSide.LEFT, "firmware"),
            (Path("firmware_right.uf2"), FirmwareSide.RIGHT, "firmware"),
            (Path("my-keyboard-left.uf2"), FirmwareSide.LEFT, "my-keyboard"),
            (Path("my-keyboard-right.uf2"), FirmwareSide.RIGHT, "my-keyboard"),
        ]

        for path, side, expected_base in test_cases:
            base = pairing_service._extract_base_name(path, side)
            assert base == expected_base

    def test_suggest_pairing_order(
        self, pairing_service: FirmwarePairingService, tmp_path: Path
    ) -> None:
        """Test pairing order suggestions."""
        # Create test pairs
        left = tmp_path / "keyboard_lh.uf2"
        right = tmp_path / "keyboard_rh.uf2"
        left.touch()
        right.touch()

        pair = FirmwarePair(left=left, right=right, base_name="keyboard")
        suggestions = pairing_service.suggest_pairing_order([pair])

        assert len(suggestions) == 1
        assert suggestions[0][0] == pair
        assert "left side first" in suggestions[0][1].lower()


class TestFirmwarePair:
    """Test FirmwarePair model."""

    def test_firmware_pair_validation(self, tmp_path: Path) -> None:
        """Test FirmwarePair validation."""
        left = tmp_path / "left.uf2"
        right = tmp_path / "right.uf2"
        left.touch()
        right.touch()

        # Valid pair
        pair = FirmwarePair(left=left, right=right)
        assert pair.left == left
        assert pair.right == right
        assert pair.base_name != ""

        # Non-existent files should raise error
        with pytest.raises(ValueError, match="Left firmware file not found"):
            FirmwarePair(left=tmp_path / "missing.uf2", right=right)

        with pytest.raises(ValueError, match="Right firmware file not found"):
            FirmwarePair(left=left, right=tmp_path / "missing.uf2")

    def test_firmware_pair_base_name_extraction(self, tmp_path: Path) -> None:
        """Test automatic base name extraction."""
        left = tmp_path / "keyboard_lh.uf2"
        right = tmp_path / "keyboard_rh.uf2"
        left.touch()
        right.touch()

        pair = FirmwarePair(left=left, right=right)
        assert pair.base_name == "keyboard"
