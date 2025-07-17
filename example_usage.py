#!/usr/bin/env python3
"""
Example usage of the BingX Trading Bot

This script demonstrates how to use the trading bot functions
without making actual API calls (for safety).
"""

import asyncio
import logging
from bingx_trading_bot import (
    load_api_config,
    normalize_symbol,
    calculate_safe_stop_loss,
    get_minimum_order_size,
    safe_float,
    calculate_roe,
    colorize,
    get_color_for_value
)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def demonstrate_utility_functions():
    """Demonstrate the utility functions."""
    print("\n" + "="*50)
    print("UTILITY FUNCTIONS DEMONSTRATION")
    print("="*50)
    
    # Symbol normalization
    print("\n📊 Symbol Normalization:")
    symbols = ["BTC/USDT:USDT", "ETH-USDT", "SOL/USDT"]
    for symbol in symbols:
        api_format = normalize_symbol(symbol, to_api=True)
        ccxt_format = normalize_symbol(symbol, to_api=False)
        print(f"  {symbol} -> API: {api_format}, CCXT: {ccxt_format}")
    
    # Safe float conversion
    print("\n🔢 Safe Float Conversion:")
    test_values = ["123.45", "invalid", None, "", 0]
    for val in test_values:
        safe_val = safe_float(val, default=0.0)
        print(f"  {val} -> {safe_val}")
    
    # ROE calculation
    print("\n📈 ROE Calculation:")
    test_cases = [(100, 1000), (-50, 500), (0, 1000)]
    for pnl, margin in test_cases:
        roe = calculate_roe(pnl, margin)
        color = get_color_for_value(roe)
        colored_roe = colorize(f"{roe}%", color)
        print(f"  PnL: ${pnl}, Margin: ${margin} -> ROE: {colored_roe}")
    
    # Minimum order sizes
    print("\n📏 Minimum Order Sizes:")
    test_symbols = ["BTC-USDT", "ETH-USDT", "DOGE-USDT", "FUEL-USDT"]
    for symbol in test_symbols:
        min_size = get_minimum_order_size(symbol, 1000.0, 50000.0)
        print(f"  {symbol}: {min_size}")

def demonstrate_stop_loss_calculation():
    """Demonstrate stop loss calculation."""
    print("\n" + "="*50)
    print("STOP LOSS CALCULATION DEMONSTRATION")
    print("="*50)
    
    # Test scenarios
    scenarios = [
        {
            "name": "BTC Long Position",
            "side": "LONG",
            "entry_price": 50000.0,
            "current_price": 50500.0,
            "liquidation_price": 45000.0,
            "leverage": 10.0
        },
        {
            "name": "ETH Short Position",
            "side": "SHORT",
            "entry_price": 3000.0,
            "current_price": 2950.0,
            "liquidation_price": 3300.0,
            "leverage": 20.0
        },
        {
            "name": "SOL Long Position (High Leverage)",
            "side": "LONG",
            "entry_price": 100.0,
            "current_price": 102.0,
            "liquidation_price": 80.0,
            "leverage": 50.0
        }
    ]
    
    for scenario in scenarios:
        print(f"\n🎯 {scenario['name']}:")
        print(f"  Side: {scenario['side']}")
        print(f"  Entry Price: ${scenario['entry_price']:,.2f}")
        print(f"  Current Price: ${scenario['current_price']:,.2f}")
        print(f"  Liquidation Price: ${scenario['liquidation_price']:,.2f}")
        print(f"  Leverage: {scenario['leverage']}x")
        
        safe_sl = calculate_safe_stop_loss(
            scenario['side'],
            scenario['entry_price'],
            scenario['current_price'],
            scenario['liquidation_price'],
            scenario['leverage']
        )
        
        print(f"  Safe Stop Loss: ${safe_sl:,.2f}")
        
        # Calculate distance from liquidation
        if scenario['side'] == 'LONG':
            distance = ((safe_sl - scenario['liquidation_price']) / scenario['liquidation_price']) * 100
        else:
            distance = ((scenario['liquidation_price'] - safe_sl) / scenario['liquidation_price']) * 100
        
        print(f"  Distance from Liquidation: {distance:.2f}%")

def demonstrate_configuration():
    """Demonstrate configuration loading."""
    print("\n" + "="*50)
    print("CONFIGURATION DEMONSTRATION")
    print("="*50)
    
    print("\n⚙️ Loading Configuration:")
    config = load_api_config()
    
    if config:
        print("  ✓ Configuration loaded successfully")
        print(f"  API Key: {'*' * 20}...{config['exchange']['api_key'][-4:]}")
        print(f"  API Secret: {'*' * 20}...{config['exchange']['api_secret'][-4:]}")
        print("  ⚠️  Remember to never share your real API credentials!")
    else:
        print("  ✗ Configuration failed to load")
        print("  Please check your bingx_futures_config.json file")

async def simulate_trading_workflow():
    """Simulate a trading workflow (without actual API calls)."""
    print("\n" + "="*50)
    print("TRADING WORKFLOW SIMULATION")
    print("="*50)
    
    print("\n🚀 Simulating Trading Workflow:")
    
    # Load configuration
    config = load_api_config()
    if not config:
        print("  ❌ Cannot proceed without configuration")
        return
    
    # Simulate position data
    position_data = {
        "symbol": "BTC-USDT",
        "side": "LONG",
        "entry_price": 50000.0,
        "position_size": 0.01,
        "current_price": 50500.0,
        "liquidation_price": 45000.0,
        "leverage": 10.0
    }
    
    print(f"  📊 Position: {position_data['symbol']}")
    print(f"  📈 Side: {position_data['side']}")
    print(f"  💰 Entry Price: ${position_data['entry_price']:,.2f}")
    print(f"  📏 Position Size: {position_data['position_size']}")
    print(f"  💹 Current Price: ${position_data['current_price']:,.2f}")
    print(f"  ⚠️  Liquidation Price: ${position_data['liquidation_price']:,.2f}")
    print(f"  📊 Leverage: {position_data['leverage']}x")
    
    # Calculate stop loss
    safe_sl = calculate_safe_stop_loss(
        position_data['side'],
        position_data['entry_price'],
        position_data['current_price'],
        position_data['liquidation_price'],
        position_data['leverage']
    )
    
    print(f"  🛡️  Calculated Stop Loss: ${safe_sl:,.2f}")
    
    # Calculate current PnL
    if position_data['side'] == 'LONG':
        pnl = (position_data['current_price'] - position_data['entry_price']) * position_data['position_size']
    else:
        pnl = (position_data['entry_price'] - position_data['current_price']) * position_data['position_size']
    
    margin = position_data['entry_price'] * position_data['position_size'] / position_data['leverage']
    roe = calculate_roe(pnl, margin)
    
    color = get_color_for_value(roe)
    colored_roe = colorize(f"{roe:+.2f}%", color)
    
    print(f"  💸 Current PnL: ${pnl:+.2f}")
    print(f"  📊 ROE: {colored_roe}")
    
    print("\n  ✅ Workflow simulation completed successfully!")
    print("  🔔 In a real scenario, this would place a stop loss order via API")

def main():
    """Main function to run all demonstrations."""
    print("🤖 BingX Trading Bot - Example Usage")
    print("This demonstration shows the bot's capabilities without making API calls")
    
    # Run demonstrations
    demonstrate_utility_functions()
    demonstrate_stop_loss_calculation()
    demonstrate_configuration()
    
    # Run async simulation
    asyncio.run(simulate_trading_workflow())
    
    print("\n" + "="*50)
    print("✨ DEMONSTRATION COMPLETE")
    print("="*50)
    print("📚 For more information, see the README.md file")
    print("⚠️  Remember: This is for demonstration only!")
    print("🔒 Never share your API credentials publicly")

if __name__ == "__main__":
    main()