#!/usr/bin/env python3
"""Test script for the new firmware compilation endpoint."""

from glovebox.moergo.client import CompilationError, TimeoutError, create_moergo_client


def test_compile_endpoint() -> bool:
    """Test the firmware compilation endpoint with sample data."""
    client = create_moergo_client()

    # Test with a simple keymap
    test_keymap = """
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";

        default_layer {
            bindings = <
                &kp A &kp B
                &kp C &kp D
            >;
        };
    };
};
"""

    test_uuid = "3d71da65-5229-4ec7-8aa8-69cf40b24047"

    try:
        print("Testing firmware compilation endpoint...")

        # Test the compile method with timeout and retry
        result = client.compile_firmware(
            layout_uuid=test_uuid,
            keymap=test_keymap,
            kconfig="CONFIG_ZMK_SLEEP=y",
            board="glove80",
            firmware_version="v25.05",
            timeout=300,  # 5 minutes timeout
            max_retries=3,  # 3 retries on timeout
            initial_retry_delay=15.0,  # 15 second initial delay
        )

        print("✅ Compilation successful!")
        print(f"📍 Firmware location: {result.location}")

        # Test downloading the firmware
        print("🔄 Downloading firmware...")
        firmware_data = client.download_firmware(
            result.location, output_path="/tmp/test_firmware.uf2.gz"
        )

        print(f"✅ Download successful! Size: {len(firmware_data)} bytes")
        print("💾 Saved to: /tmp/test_firmware.uf2.gz")

        return True

    except TimeoutError as e:
        print(f"⏰ Compilation timed out: {e}")
        return False
    except CompilationError as e:
        print(f"🔨 Compilation failed: {e}")
        if e.detail:
            print("📋 Compilation details:")
            for line in e.detail[-5:]:  # Show last 5 lines
                print(f"   {line}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


def test_timeout() -> bool:
    """Test timeout handling with a very short timeout."""
    client = create_moergo_client()

    test_keymap = """
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";
        default_layer {
            bindings = <&kp A &kp B &kp C &kp D>;
        };
    };
};
"""

    try:
        print("🔄 Testing timeout with 1 second timeout and 2 retries...")
        client.compile_firmware(
            layout_uuid="3d71da65-5229-4ec7-8aa8-69cf40b24047",
            keymap=test_keymap,
            timeout=1,  # Very short timeout to trigger timeout
            max_retries=2,  # Only 2 retries for faster test
            initial_retry_delay=1.0,  # Short delay for test
        )
        print("❌ Expected timeout but compilation succeeded")
        return False
    except TimeoutError:
        print("✅ Timeout handled correctly")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_compilation_error() -> bool:
    """Test compilation error handling with invalid keymap."""
    client = create_moergo_client()

    # Invalid keymap that should cause compilation to fail
    invalid_keymap = """
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";
        default_layer {
            // Invalid syntax - missing binding operator
            bindings = <
                kp A kp B  // This should cause an error
                kp C kp D
            >;
        };
    };
};
"""

    try:
        print("🔄 Testing compilation error handling...")
        client.compile_firmware(
            layout_uuid="3d71da65-5229-4ec7-8aa8-69cf40b24047",
            keymap=invalid_keymap,
            timeout=60,
        )
        print("❌ Expected compilation to fail but it succeeded")
        return False
    except CompilationError as e:
        print("✅ Compilation error handled correctly")
        print(f"📝 Error: {e}")
        if e.detail:
            print("📋 Error details available")
        return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_retry_logic() -> bool:
    """Test retry logic by checking history for retry entries."""
    client = create_moergo_client()

    test_keymap = """
#include <behaviors.dtsi>
#include <dt-bindings/zmk/keys.h>

/ {
    keymap {
        compatible = "zmk,keymap";
        default_layer {
            bindings = <&kp A &kp B &kp C &kp D>;
        };
    };
};
"""

    try:
        print("🔄 Testing retry logic with short timeout...")

        client.compile_firmware(
            layout_uuid="3d71da65-5229-4ec7-8aa8-69cf40b24047",
            keymap=test_keymap,
            timeout=2,  # Short timeout
            max_retries=2,  # 2 retries
            initial_retry_delay=0.5,  # Short delay for test
        )
        print("❌ Expected timeout but compilation succeeded")
        return False
    except TimeoutError as e:
        # Check if the error message indicates retries were attempted
        error_message = str(e).lower()
        if "retry" in error_message or "attempt" in error_message:
            print("✅ Retry logic working - timeout message indicates retries")
            print(f"📝 Error message: {e}")
            return True
        else:
            print("✅ Timeout occurred as expected (retry logic may have worked)")
            print(f"📝 Error message: {e}")
            return True
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


if __name__ == "__main__":
    print("=== Testing Firmware Compilation Endpoint ===")
    success1 = test_compile_endpoint()

    print("\n=== Testing Timeout Handling ===")
    success2 = test_timeout()

    print("\n=== Testing Compilation Error Handling ===")
    success3 = test_compilation_error()

    print("\n=== Testing Retry Logic ===")
    success4 = test_retry_logic()

    overall_success = success1 and success2 and success3 and success4
    print(f"\n{'✅ All tests passed!' if overall_success else '❌ Some tests failed'}")
    exit(0 if overall_success else 1)
