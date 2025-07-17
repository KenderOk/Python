#!/usr/bin/env python3
"""
Test script for BingX Trading Bot
Tests core functionality without making actual API calls
"""

import asyncio
import logging
import sys
import os

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bingx_trading_bot import (
    normalize_symbol,
    calculate_safe_stop_loss,
    get_minimum_order_size,
    get_precision,
    safe_float,
    calculate_roe,
    colorize,
    get_color_for_value,
    load_api_config
)

def test_normalize_symbol():
    """Test symbol normalization functionality."""
    print("Testing symbol normalization...")
    
    # Test CCXT to API format conversion
    assert normalize_symbol("BTC/USDT:USDT", to_api=True) == "BTC-USDT"
    assert normalize_symbol("ETH/USDT:USDT", to_api=True) == "ETH-USDT"
    assert normalize_symbol("BTC/USDT", to_api=True) == "BTC-USDT"
    assert normalize_symbol("BTC-USDT", to_api=True) == "BTC-USDT"
    
    # Test API to CCXT format conversion
    assert normalize_symbol("BTC-USDT", to_api=False) == "BTC/USDT:USDT"
    assert normalize_symbol("ETH-USDT", to_api=False) == "ETH/USDT:USDT"
    assert normalize_symbol("BTC/USDT:USDT", to_api=False) == "BTC/USDT:USDT"
    
    # Test invalid inputs
    assert normalize_symbol("", to_api=True) == "INVALID"
    assert normalize_symbol(None, to_api=True) == "INVALID"
    
    print("✓ Symbol normalization tests passed")

def test_calculate_safe_stop_loss():
    """Test safe stop loss calculation."""
    print("Testing safe stop loss calculation...")
    
    # Test LONG position
    entry_price = 50000.0
    current_price = 50500.0
    liquidation_price = 45000.0  # Below entry price for LONG
    leverage = 10.0
    
    sl_price = calculate_safe_stop_loss("LONG", entry_price, current_price, liquidation_price, leverage)
    assert sl_price > liquidation_price, f"SL {sl_price} should be above liquidation {liquidation_price}"
    assert sl_price < current_price, f"SL {sl_price} should be below current {current_price}"
    
    # Test SHORT position
    entry_price = 50000.0
    current_price = 49500.0  # Price moved down (favorable for SHORT)
    liquidation_price = 55000.0  # Above entry price for SHORT
    
    sl_price = calculate_safe_stop_loss("SHORT", entry_price, current_price, liquidation_price, leverage)
    assert sl_price < liquidation_price, f"SL {sl_price} should be below liquidation {liquidation_price}"
    assert sl_price > current_price, f"SL {sl_price} should be above current {current_price}"
    
    print("✓ Safe stop loss calculation tests passed")

def test_get_minimum_order_size():
    """Test minimum order size calculation."""
    print("Testing minimum order size calculation...")
    
    # Test known symbols
    assert get_minimum_order_size("BTC-USDT", 50000.0, 50000.0) >= 0.0001
    assert get_minimum_order_size("ETH-USDT", 3000.0, 3000.0) >= 0.001
    assert get_minimum_order_size("DOGE-USDT", 100.0, 0.1) >= 1.0
    
    # Test unknown symbol (should return default)
    assert get_minimum_order_size("UNKNOWN-USDT", 100.0, 1.0) >= 0.01
    
    print("✓ Minimum order size tests passed")

def test_get_precision():
    """Test precision calculation."""
    print("Testing precision calculation...")
    
    # Test known symbols
    qty_prec, price_prec = get_precision("BTC-USDT", 0.01, 50000.0)
    assert isinstance(qty_prec, int)
    assert isinstance(price_prec, int)
    assert qty_prec >= 0 and price_prec >= 0
    
    # Test unknown symbol (should return defaults)
    qty_prec, price_prec = get_precision("UNKNOWN-USDT", 0.01, 100.0)
    assert qty_prec == 2 and price_prec == 4
    
    print("✓ Precision calculation tests passed")

def test_safe_float():
    """Test safe float conversion."""
    print("Testing safe float conversion...")
    
    assert safe_float("123.45") == 123.45
    assert safe_float("0") == 0.0
    assert safe_float("") == 0.0
    assert safe_float(None) == 0.0
    assert safe_float("invalid", 99.9) == 99.9
    assert safe_float(123.45) == 123.45
    
    print("✓ Safe float conversion tests passed")

def test_calculate_roe():
    """Test ROE calculation."""
    print("Testing ROE calculation...")
    
    assert calculate_roe(100.0, 1000.0) == 10.0
    assert calculate_roe(-50.0, 1000.0) == -5.0
    assert calculate_roe(0.0, 1000.0) == 0.0
    assert calculate_roe(100.0, 0.0) == 0.0
    
    print("✓ ROE calculation tests passed")

def test_colorize():
    """Test terminal colorization."""
    print("Testing terminal colorization...")
    
    colored_text = colorize("test", "32")
    assert "\033[32m" in colored_text
    assert "\033[0m" in colored_text
    assert "test" in colored_text
    
    print("✓ Terminal colorization tests passed")

def test_get_color_for_value():
    """Test color selection for values."""
    print("Testing color selection...")
    
    assert get_color_for_value(10.0) == '32'   # Green for positive
    assert get_color_for_value(-10.0) == '31'  # Red for negative
    assert get_color_for_value(0.0) == '33'    # Yellow for zero
    
    print("✓ Color selection tests passed")

def test_load_api_config():
    """Test configuration loading."""
    print("Testing configuration loading...")
    
    # Test with existing config file
    config = load_api_config()
    assert config is not None
    assert 'exchange' in config
    
    # Test with non-existent file
    config = load_api_config("non_existent_config.json")
    assert config is None
    
    print("✓ Configuration loading tests passed")

def run_all_tests():
    """Run all tests."""
    print("Running BingX Trading Bot Tests...")
    print("=" * 50)
    
    try:
        test_normalize_symbol()
        test_calculate_safe_stop_loss()
        test_get_minimum_order_size()
        test_get_precision()
        test_safe_float()
        test_calculate_roe()
        test_colorize()
        test_get_color_for_value()
        test_load_api_config()
        
        print("=" * 50)
        print("✓ All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)