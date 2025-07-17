# BingX Trading Bot

A comprehensive trading bot for BingX futures trading with advanced stop loss and take profit functionality.

## Features

- **Automated Stop Loss Placement**: Places stop losses with liquidation-aware calculations
- **Position Management**: Tracks and manages futures positions
- **Rate Limiting Handling**: Intelligent retry logic to handle API rate limits
- **Signature Verification**: Secure API communication with BingX
- **Error Recovery**: Robust error handling and fallback mechanisms
- **Leverage-Aware Calculations**: Adjusts stop loss based on leverage settings

## Installation

1. Install required dependencies:
```bash
pip install -r requirements.txt
```

2. Create your configuration file:
```bash
cp bingx_futures_config.json.example bingx_futures_config.json
```

3. Edit the configuration file with your API credentials:
```json
{
  "exchange": {
    "api_key": "YOUR_API_KEY",
    "api_secret": "YOUR_API_SECRET"
  }
}
```

## Usage

### Basic Usage

```python
import asyncio
from bingx_trading_bot import place_fixed_stop_loss, load_api_config

async def main():
    config = load_api_config()
    api_key = config['exchange']['api_key']
    api_secret = config['exchange']['api_secret']
    
    # Place a stop loss for a BTC long position
    success = await place_fixed_stop_loss(
        api_key=api_key,
        api_secret=api_secret,
        symbol="BTC-USDT",
        side="LONG",
        entry_price=50000.0,
        position_size=0.01,
        logger=logger,
        leverage=10
    )
    
    if success:
        print("Stop loss placed successfully")
    else:
        print("Failed to place stop loss")

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced Features

#### Symbol Normalization
```python
from bingx_trading_bot import normalize_symbol

# Convert between CCXT and BingX API formats
api_symbol = normalize_symbol("BTC/USDT:USDT", to_api=True)  # Returns "BTC-USDT"
ccxt_symbol = normalize_symbol("BTC-USDT", to_api=False)     # Returns "BTC/USDT:USDT"
```

#### Position Information
```python
from bingx_trading_bot import get_current_position_info

position_info = await get_current_position_info(api_key, api_secret, "BTC-USDT", logger)
print(f"Available: {position_info.get('available', 0)}")
print(f"Size: {position_info.get('size', 0)}")
print(f"Liquidation Price: {position_info.get('liquidation_price', 0)}")
```

#### Order Management
```python
from bingx_trading_bot import cancel_existing_stop_orders, check_existing_orders

# Cancel existing stop loss and take profit orders
success = await cancel_existing_stop_orders(api_key, api_secret, "BTC-USDT", logger)

# Check for existing orders
has_sl, has_tp = await check_existing_orders(api_key, api_secret, "BTC-USDT", logger)
```

## Functions

### Core Functions

- `place_fixed_stop_loss()`: Places a fixed stop loss order with liquidation protection
- `get_current_position_info()`: Retrieves current position information
- `cancel_existing_stop_orders()`: Cancels existing stop/take profit orders
- `check_existing_orders()`: Checks for existing TP/SL orders

### Utility Functions

- `normalize_symbol()`: Converts between different symbol formats
- `calculate_safe_stop_loss()`: Calculates safe stop loss prices
- `get_minimum_order_size()`: Returns minimum order size for symbols
- `get_precision()`: Returns precision settings for quantity and price
- `safe_float()`: Safely converts values to float

### API Functions

- `set_bingx_position_tpsl()`: Sets TP/SL using BingX position API
- `place_bingx_tpsl_order()`: Places TP/SL orders with retry logic
- `get_actual_available_quantity()`: Gets actual available quantity for orders

## Configuration

The bot requires a JSON configuration file with your BingX API credentials:

```json
{
  "exchange": {
    "api_key": "your_api_key_here",
    "api_secret": "your_api_secret_here"
  }
}
```

## Error Handling

The bot includes comprehensive error handling for:

- Rate limiting with exponential backoff
- Signature verification failures
- Network timeouts and connection issues
- Invalid order parameters
- Insufficient position sizes
- Liquidation price calculations

## Safety Features

- **Liquidation Protection**: Stop losses are automatically adjusted to stay above/below liquidation prices
- **Position Validation**: Verifies position exists before placing orders
- **Minimum Size Checks**: Ensures orders meet minimum size requirements
- **Price Validation**: Validates stop loss prices against current market prices

## Logging

The bot uses Python's logging module for comprehensive logging:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
```

## Rate Limiting

The bot handles BingX rate limits with:
- Intelligent retry logic
- Exponential backoff
- Rate limit detection
- Queue management for multiple requests

## Security

- Secure signature generation using HMAC-SHA256
- API credentials stored in configuration file (not in code)
- Request parameter validation
- Error message sanitization

## Disclaimer

This software is for educational and research purposes only. Trading cryptocurrencies involves substantial risk and may result in significant financial losses. Use at your own risk.

## License

MIT License - See LICENSE file for details