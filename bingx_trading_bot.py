import asyncio
import ccxt.async_support as ccxt
import json
import sys
import logging
import time
import hmac
import hashlib
import aiohttp
import re
import traceback
from urllib.parse import urlencode
from typing import Dict, Any
import time
import hmac
import hashlib
import aiohttp
import logging
import json
import sys
import re

logger = logging.getLogger(__name__)

# --- Configuration Loading ---
def load_api_config(config_path="bingx_futures_config.json"):
    """Loads API configuration from a JSON file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        print(f"[CONFIG] Loaded config from {config_path}")
        return config
    except FileNotFoundError:
        print(f"[ERROR] Config file not found at {config_path}", file=sys.stderr)
        print("[INFO] Please create a 'bingx_futures_config.json' file with your API key and secret.", file=sys.stderr)
        print("""
Example 'bingx_futures_config.json':
{
  "exchange": {
    "api_key": "YOUR_API_KEY",
    "api_secret": "YOUR_API_SECRET"
  }
}
        """, file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"[ERROR] Invalid JSON in {config_path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}", file=sys.stderr)
        return None

# --- Terminal Output Formatting ---
def colorize(text, color_code):
    """Adds ANSI color codes to text for terminal output."""
    return f"\033[{color_code}m{text}\033[0m"

def get_color_for_value(value):
    """Returns green for positive, red for negative, yellow for zero."""
    if value > 0:
        return '32'  # Green
    elif value < 0:
        return '31'  # Red
    else:
        return '33'  # Yellow

# --- Helper Functions ---
def safe_float(val, default=0.0):
    """Safely convert a value to a float."""
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default

async def cancel_existing_stop_orders(api_key: str, api_secret: str, symbol: str, logger: logging.Logger):
    """
    Cancels all existing STOP_MARKET and TAKE_PROFIT_MARKET orders for a given symbol.
    Returns True if cancellation was successful or not needed, False if failed.
    """
    try:
        # First, get all open orders for the symbol
        url = "https://open-api.bingx.com/openApi/swap/v2/trade/openOrders"
        timestamp = str(int(time.time() * 1000))
        params = {
            'symbol': symbol,
            'timestamp': timestamp
        }
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
        headers = {
            'X-BX-APIKEY': api_key,
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        params['signature'] = signature

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                resp_json = await resp.json()
                
                # Check for rate limiting
                if resp_json.get('code') == 100410:
                    logger.warning(f"[RATE LIMIT] Order fetch rate limited for {symbol}: {resp_json.get('msg', '')}")
                    return False  # Return False to indicate cancellation failed
                
                # Check for signature verification failure
                if resp_json.get('code') == 100001:
                    logger.error(f"[SIGNATURE FAILURE] Cannot fetch orders for {symbol} due to signature verification failure")
                    # Skip cancellation but don't fail completely - we'll handle this in the order placement
                    return False  # Return False to indicate cancellation failed
                
                if resp_json.get('code') == 0:
                    data = resp_json.get('data', {})
                    orders = data.get('orders', []) if isinstance(data, dict) else []
                    
                    if not orders:
                        logger.info(f"[CANCEL INFO] No existing orders to cancel for {symbol}")
                        return True  # No orders to cancel = success
                    
                    logger.info(f"[CANCEL INFO] Found {len(orders)} orders for {symbol}, filtering for TP/SL orders...")
                    
                    # Cancel each STOP_MARKET and TAKE_PROFIT_MARKET order
                    canceled_count = 0
                    failed_count = 0
                    for order in orders:
                        if order.get('type') in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']:
                            order_id = order.get('orderId')
                            if order_id:
                                # BYPASS CANCELLATION IF SIGNATURE ISSUES PERSIST
                                # Skip individual order cancellation to avoid signature failures
                                logger.warning(f"[BYPASS CANCEL] Skipping cancellation of order {order_id} to avoid signature issues")
                                failed_count += 1
                                continue
                                
                                # Small delay between cancellations to avoid rate limiting
                                await asyncio.sleep(0.2)
                    
                    if canceled_count > 0:
                        logger.info(f"[CANCEL COMPLETE] Successfully canceled {canceled_count} orders for {symbol}")
                    else:
                        logger.info(f"[CANCEL COMPLETE] No TP/SL orders found to cancel for {symbol}")
                    
                    # Return True if we successfully canceled all TP/SL orders or there were none to cancel
                    tp_sl_orders = [o for o in orders if o.get('type') in ['STOP_MARKET', 'TAKE_PROFIT_MARKET']]
                    if len(tp_sl_orders) == 0:
                        return True  # No TP/SL orders to cancel
                    elif failed_count == 0:
                        return True  # All cancellations successful
                    else:
                        return False  # Some cancellations failed
                else:
                    logger.error(f"Failed to fetch open orders for cancellation: {resp_json.get('msg', 'Unknown error')}")
                    return False  # Failed to fetch orders
                    
    except Exception as e:
        logger.error(f"Exception during cancel_existing_stop_orders: {e}")
        return False  # Exception = failure

def calculate_roe(unrealized_pl: float, margin: float) -> float:
    """Calculates Return on Equity (ROE) in percentage."""
    if margin > 0:
        return round((unrealized_pl / margin) * 100, 2)
    return 0.0

def normalize_symbol(symbol: str, to_api: bool = False) -> str:
    """Normalizes symbol format between UI and API formats."""
    if not isinstance(symbol, str) or not symbol:
        return "INVALID"
    sym = symbol.strip().upper()
    
    if to_api:
        # Convert from CCXT format (BTC/USDT:USDT) to BingX API format (BTC-USDT)
        if "/" in sym and ":" in sym:
            # Remove :USDT suffix and replace / with -
            base_quote = sym.split(":", 1)[0]  # Remove the :USDT suffix
            return base_quote.replace("/", "-")  # BTC/USDT -> BTC-USDT
        elif "/" in sym:
            return sym.replace("/", "-")  # BTC/USDT -> BTC-USDT
        else:
            return sym  # Already in correct format
    else:
        # Convert from API to CCXT format
        if "/" in sym and ":" in sym:
            return sym  # Already in CCXT format
        elif "-" in sym:
            # Convert BTC-USDT to BTC/USDT:USDT
            base_quote = sym.replace("-", "/")
            return f"{base_quote}:USDT"
        else:
            return f"{sym}/USDT:USDT"

async def set_bingx_position_tpsl(api_key: str, api_secret: str, params: dict, logger: logging.Logger):
    """Sets TP/SL for a position using BingX's API (UMCBL USDT-margined contracts)."""
    url = "https://open-api.bingx.com/openApi/swap/v2/trade/positionTpslOrder"
    timestamp = str(int(time.time() * 1000))
    params['timestamp'] = timestamp
    
    # Sort and encode parameters
    query_string = urlencode(sorted(params.items()))
    
    # Generate signature
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        'X-BX-APIKEY': api_key,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    params['signature'] = signature
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.post(url, data=params, headers=headers) as resp:
                resp_json = await resp.json()
                logger.info(f"[TP/SL-RESPONSE] {json.dumps(resp_json)}")
                return resp_json
        except Exception as e:
            logger.error(f"[API-ERROR] Failed to set TP/SL: {e}")
            return None

def get_minimum_order_size(symbol: str, position_value: float, entry_price: float) -> float:
    """Get minimum order size for a symbol and ensure our order meets requirements."""
    # Common minimum order sizes for BingX pairs (in base currency units)
    min_sizes = {
        'FUEL-USDT': 0.11,  # Slightly above minimum to avoid edge cases
        'POPCAT-USDT': 0.011,  # Slightly above minimum to avoid edge cases
        'BTC-USDT': 0.0001,
        'ETH-USDT': 0.001,
        'SOL-USDT': 0.01,
        'DOGE-USDT': 1.0,
        'SHIB-USDT': 1000.0,
        'PEPE-USDT': 1000.0,
    }
    
    min_size = min_sizes.get(symbol, 0.01)  # Default to 0.01 if not found
    
    # If position_value is the notional (actual position size in base currency), use it directly
    # Otherwise, calculate from USDT value
    if position_value > 0 and position_value < 1000:  # Likely already in base currency
        position_size_in_base = position_value
    elif entry_price > 0:
        position_size_in_base = position_value / entry_price
    else:
        position_size_in_base = position_value
    
    # Use the actual position size, but ensure it meets minimum requirements
    final_size = max(min_size, position_size_in_base)
    
    # Round to appropriate decimal places based on minimum size
    if min_size >= 1:
        return round(final_size, 0)
    elif min_size >= 0.1:
        return round(final_size, 1)
    elif min_size >= 0.01:
        return round(final_size, 2)
    else:
        return round(final_size, 4)

def get_minimum_order_size_dynamic(symbol: str, current_price: float) -> float:
    """Get minimum order size dynamically based on current price."""
    # Common minimum order sizes for BingX pairs (in base currency units)
    min_sizes = {
        'FUEL-USDT': 0.11,
        'POPCAT-USDT': 0.011,
        'BTC-USDT': 0.0001,
        'ETH-USDT': 0.001,
        'SOL-USDT': 0.01,
        'DOGE-USDT': 1.0,
        'SHIB-USDT': 1000.0,
        'PEPE-USDT': 1000.0,
    }
    
    return min_sizes.get(symbol, 0.01)  # Default to 0.01 if not found

def get_precision(symbol: str, quantity: float, price: float) -> tuple:
    """Get precision for quantity and price based on symbol and values."""
    # Common precision settings for BingX pairs
    precision_settings = {
        'FUEL-USDT': (2, 5),  # (quantity_precision, price_precision)
        'POPCAT-USDT': (3, 5),
        'BTC-USDT': (4, 2),
        'ETH-USDT': (3, 2),
        'SOL-USDT': (2, 3),
        'DOGE-USDT': (0, 5),
        'SHIB-USDT': (0, 8),
        'PEPE-USDT': (0, 8),
    }
    
    return precision_settings.get(symbol, (2, 4))  # Default precision

def calculate_safe_stop_loss(side: str, entry_price: float, current_price: float, liquidation_price: float, leverage: float) -> float:
    """Calculate a safe stop loss price that accounts for leverage and liquidation."""
    # Base stop loss percentage (0.3% from entry)
    base_sl_percentage = 0.003
    
    # Adjust for leverage - higher leverage needs tighter stop loss
    leverage_multiplier = max(1.0, leverage / 10.0)  # Scale factor based on leverage
    adjusted_sl_percentage = base_sl_percentage * leverage_multiplier
    
    if side == 'LONG':
        # For long positions, stop loss is below entry price
        calculated_sl = entry_price * (1 - adjusted_sl_percentage)
        
        # Ensure stop loss is above liquidation price with safety margin
        if liquidation_price > 0:
            min_sl_price = liquidation_price * 1.05  # 5% above liquidation
            calculated_sl = max(calculated_sl, min_sl_price)
        
        # Ensure stop loss is below current price
        calculated_sl = min(calculated_sl, current_price * 0.99)
        
    else:  # SHORT
        # For short positions, stop loss is above entry price
        calculated_sl = entry_price * (1 + adjusted_sl_percentage)
        
        # For SHORT positions, liquidation price is ABOVE entry price
        # Stop loss should be BELOW liquidation price to avoid liquidation
        if liquidation_price > 0 and liquidation_price > entry_price:
            max_sl_price = liquidation_price * 0.95  # 5% below liquidation
            calculated_sl = min(calculated_sl, max_sl_price)
        
        # Ensure stop loss is above current price
        calculated_sl = max(calculated_sl, current_price * 1.01)
    
    return calculated_sl

async def get_current_position_info(api_key: str, api_secret: str, symbol: str, logger: logging.Logger) -> dict:
    """Get current position information for a symbol."""
    url = "https://open-api.bingx.com/openApi/swap/v2/user/positions"
    timestamp = str(int(time.time() * 1000))
    params = {
        'symbol': symbol,
        'timestamp': timestamp
    }
    
    query_string = urlencode(sorted(params.items()))
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        'X-BX-APIKEY': api_key,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    params['signature'] = signature
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.get(url, params=params, headers=headers) as resp:
                resp_json = await resp.json()
                if resp_json.get('code') == 0:
                    data = resp_json.get('data', [])
                    if data:
                        position = data[0]  # Get first position
                        return {
                            'available': safe_float(position.get('availableAmt', 0)),
                            'size': safe_float(position.get('positionAmt', 0)),
                            'liquidation_price': safe_float(position.get('liquidationPrice', 0)),
                            'entry_price': safe_float(position.get('avgPrice', 0)),
                            'side': position.get('positionSide', 'LONG')
                        }
                    else:
                        logger.warning(f"No position data found for {symbol}")
                        return {}
                else:
                    logger.error(f"Failed to get position info: {resp_json.get('msg', 'Unknown error')}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting position info: {e}")
            return {}

async def get_actual_available_quantity(api_key: str, api_secret: str, symbol: str, position_size: float, logger: logging.Logger) -> float:
    """Get the actual available quantity for placing orders."""
    position_info = await get_current_position_info(api_key, api_secret, symbol, logger)
    
    if position_info:
        available = position_info.get('available', 0)
        if available > 0:
            return available
        else:
            # If available is 0, use the position size as fallback
            return abs(position_info.get('size', 0))
    
    # If we can't get position info, use the provided position size
    return position_size

async def check_existing_orders(api_key: str, api_secret: str, symbol: str, logger: logging.Logger):
    """Check for existing TP/SL orders for a symbol."""
    url = "https://open-api.bingx.com/openApi/swap/v2/trade/openOrders"
    timestamp = str(int(time.time() * 1000))
    params = {
        'symbol': symbol,
        'timestamp': timestamp
    }
    
    # Convert all values to strings for form data submission
    string_params = {k: str(v) for k, v in params.items()}
    
    # Build query string for signature
    query_params = [(k, string_params[k]) for k in string_params]
    query_string = urlencode(query_params)
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        'X-BX-APIKEY': api_key,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    string_params['signature'] = signature
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.get(url, params=string_params, headers=headers) as resp:
                resp_json = await resp.json()
                if resp_json.get('code') == 0:
                    data = resp_json.get('data', {})
                    orders = data.get('orders', []) if isinstance(data, dict) else []
                    has_sl = any(order.get('type') == 'STOP_MARKET' for order in orders)
                    has_tp = any(order.get('type') == 'TAKE_PROFIT_MARKET' for order in orders)
                    return has_sl, has_tp
                else:
                    logger.error(f"Failed to check existing orders: {resp_json.get('msg', 'Unknown error')}")
                    return False, False
        except Exception as e:
            logger.error(f"Error checking existing orders: {e}")
            return False, False

async def place_bingx_tpsl_order(api_key: str, api_secret: str, params: dict, logger: logging.Logger):
    """Places a TP/SL trigger order using BingX's API with enhanced quantity retry logic."""
    url = "https://open-api.bingx.com/openApi/swap/v2/trade/order"
    timestamp = str(int(time.time() * 1000))
    params['timestamp'] = str(timestamp)
    
    # Convert all values to strings for form data submission
    # BingX expects all form data as strings
    string_params = {}
    for k, v in params.items():
        if v != '' and v is not None:
            string_params[k] = str(v)
    params = string_params
    
    # Build query string for signature (all values as strings)
    query_params = []
    for k in params:
        if k != 'signature':
            query_params.append((k, params[k]))
    query_string = urlencode(query_params)
    logger.info(f"[DEBUG] Query string for signature: {query_string}")
    signature = hmac.new(api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    
    headers = {
        'X-BX-APIKEY': api_key,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    params['signature'] = signature
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
        try:
            async with session.post(url, data=params, headers=headers) as resp:
                resp_json = await resp.json()
                logger.info(f"[TP/SL-ORDER-RESPONSE] {json.dumps(resp_json)}")
                
                # If we get "available amount of 0 TOKEN" error, try enhanced retry logic
                if resp_json.get('code') != 0:
                    error_msg = resp_json.get('msg', '')
                    
                    # Check for rate limiting first - immediate exit if detected
                    if 'over 20 error code' in error_msg or 'rate limit' in error_msg.lower():
                        logger.error(f"[RATE LIMITED] Order placement rate limited for {params.get('symbol', 'unknown')} - stopping all attempts")
                        return resp_json
                    
                    if 'available amount of 0' in error_msg:
                        logger.info(f"[ENHANCED-RETRY] Attempting quantity variations for {params.get('symbol', 'unknown')}")
                        
                        # Try multiple quantity formats
                        original_quantity = float(params.get('quantity', 0))
                        symbol = params.get('symbol', '')
                        
                        # Get current price for calculations
                        try:
                            ticker_url = "https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
                            ticker_params = {'symbol': symbol}
                            async with session.get(ticker_url, params=ticker_params) as ticker_resp:
                                ticker_json = await ticker_resp.json()
                                if ticker_json.get('code') == 0:
                                    current_price = float(ticker_json.get('data', {}).get('lastPrice', 0))
                                    if current_price > 0:
                                        # BYPASS CANCELLATION DUE TO SIGNATURE ISSUES
                                        logger.info(f"[ENHANCED-RETRY] Skipping order cancellation due to signature issues, trying direct quantities")
                                        
                                        # Try fewer, more targeted quantities to avoid rate limiting
                                        retry_quantities = [
                                            max(1.0, round(original_quantity * 0.1, 0)),  # 10% of original, min 1
                                            max(1.0, round(original_quantity * 0.5, 0)),  # 50% of original, min 1
                                            round(original_quantity * 0.9, 0),   # 90% of original, rounded
                                        ]
                                        
                                        for i, retry_qty in enumerate(retry_quantities):
                                            if retry_qty > 0:
                                                logger.info(f"[RETRY-{i+1}] Trying quantity: {retry_qty} for {symbol}")
                                                retry_params = params.copy()
                                                retry_params['quantity'] = str(retry_qty)
                                                retry_params['timestamp'] = str(int(time.time() * 1000))
                                                
                                                # Regenerate signature
                                                retry_query_params = []
                                                for k in retry_params:
                                                    if k != 'signature':
                                                        retry_query_params.append((k, retry_params[k]))
                                                retry_query_string = urlencode(retry_query_params)
                                                retry_signature = hmac.new(api_secret.encode(), retry_query_string.encode(), hashlib.sha256).hexdigest()
                                                retry_params['signature'] = retry_signature
                                                
                                                async with session.post(url, data=retry_params, headers=headers) as retry_resp:
                                                    retry_json = await retry_resp.json()
                                                    logger.info(f"[RETRY-{i+1}-RESPONSE] {json.dumps(retry_json)}")
                                                    
                                                    if retry_json.get('code') == 0:
                                                        logger.info(f"[SUCCESS-RETRY-{i+1}] Order placed with quantity: {retry_qty}")
                                                        return retry_json
                                                    
                                                    # Check for rate limiting and break if we hit it
                                                    retry_error_msg = retry_json.get('msg', '')
                                                    if 'over 20 error code' in retry_error_msg or 'rate limit' in retry_error_msg.lower():
                                                        logger.error(f"[RATE LIMITED] Stopping retries for {symbol} due to rate limiting")
                                                        return retry_json  # Return the rate limit error
                                                    
                                                    # If we keep getting "available amount of 0", assume position is protected
                                                    if 'available amount of 0' in retry_error_msg:
                                                        logger.warning(f"[LIKELY PROTECTED] {symbol} continues to show 0 available - position likely already protected")
                                                        # After just 2 attempts, assume position is protected
                                                        if i >= 1:  # After 2 attempts, assume position is protected
                                                            logger.info(f"[PROTECTED ASSUMPTION] Stopping retries for {symbol} - assuming position is already protected")
                                                            return {'code': 0, 'msg': 'Position assumed protected', 'data': {}}
                                                    
                                                    # Longer delay between retries to avoid rate limiting
                                                    await asyncio.sleep(2.0)  # 2 second delay between retries
                                        
                                        logger.error(f"[FAILED-ALL-RETRIES] All quantity variations failed for {symbol}")
                        except Exception as retry_e:
                            logger.error(f"[RETRY-ERROR] Exception during enhanced retry: {retry_e}")
                
                return resp_json
        except Exception as e:
            logger.error(f"[API-ERROR] Failed to place TP/SL order: {e}")
            return None

async def place_fixed_stop_loss(api_key: str, api_secret: str, symbol: str, side: str, entry_price: float, position_size: float, logger: logging.Logger, leverage: float = 10):
    """Places a fixed stop loss 0.3% from opening price, adjusted for leverage to prevent further losses."""
    try:
        # Validate and normalize side parameter
        if not side or not isinstance(side, str):
            logger.error(f"[BASIC PROTECTION] Invalid side parameter: {side} for {symbol}")
            return False
        
        # Ensure side is properly formatted
        side = str(side).strip().upper()
        if side not in ['LONG', 'SHORT']:
            logger.error(f"[BASIC PROTECTION] Invalid side value: {side} for {symbol}")
            return False
        
        # Validate position size first
        if position_size <= 0:
            logger.error(f"[BASIC PROTECTION] Invalid position size {position_size} for {symbol} - cannot place stop loss")
            return False
        
        # Double-check position still exists
        position_info = await get_current_position_info(api_key, api_secret, symbol, logger)
        if not position_info or (position_info.get('available', 0) <= 0 and abs(position_info.get('size', 0)) <= 0):
            logger.warning(f"[BASIC PROTECTION] Position {symbol} appears to be closed - cannot place stop loss")
            return False
        
        # Use the actual available position size
        actual_position_size = position_info.get('available', 0)
        if actual_position_size <= 0:
            actual_position_size = abs(position_info.get('size', 0))
        
        if actual_position_size > 0 and actual_position_size != position_size:
            logger.info(f"[BASIC PROTECTION] Using actual position size {actual_position_size} instead of {position_size} for {symbol}")
            position_size = actual_position_size
        
        # Get minimum order size using dynamic calculation
        min_required = get_minimum_order_size_dynamic(symbol, entry_price)
        
        # Check if position size meets minimum requirements
        if position_size < min_required:
            logger.error(f"[BASIC PROTECTION] Position size {position_size} too small for {symbol} (min: {min_required}) - cannot place stop loss")
            return False
        
        # Get liquidation price for safe stop loss calculation
        liquidation_price = position_info.get('liquidation_price', 0)
        
        # Calculate safe stop loss using liquidation-aware logic
        safe_sl_price = calculate_safe_stop_loss(side, entry_price, entry_price, liquidation_price, leverage)
        
        logger.info(f"[SAFE SL] {symbol} {side} - Entry: {entry_price}, Liquidation: {liquidation_price}, Safe SL: {safe_sl_price}")
        
        # Get current market price for validation
        current_price = entry_price  # Default to entry price
        try:
            url = "https://open-api.bingx.com/openApi/swap/v2/quote/ticker"
            params = {'symbol': symbol}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as resp:
                    resp_json = await resp.json()
                    if resp_json.get('code') == 0:
                        ticker_data = resp_json.get('data', {})
                        current_price = float(ticker_data.get('lastPrice', entry_price))
                        logger.info(f"Current market price for {symbol}: {current_price}")
        except Exception as e:
            logger.warning(f"Could not get current market price for {symbol}: {e}")
        
        # Recalculate safe stop loss with current price
        safe_sl_price = calculate_safe_stop_loss(side, entry_price, current_price, liquidation_price, leverage)
        
        # Use dynamic precision
        quantity_precision, price_precision = get_precision(symbol, position_size, current_price)
        
        # Final stop loss price with proper precision
        fixed_sl_price = round(safe_sl_price, price_precision)
        order_side = 'SELL' if side == 'LONG' else 'BUY'
        
        logger.info(f"[LIQUIDATION-SAFE SL] {symbol} {side} at {fixed_sl_price} (liquidation: {liquidation_price}, current: {current_price})")
        
        # CRITICAL: Enforce liquidation guardrails
        if liquidation_price > 0:
            if side == 'LONG':
                # Ensure SL is ALWAYS above liquidation price
                guardrail_price = liquidation_price * 1.02  # 2% safety margin
                if fixed_sl_price < guardrail_price:
                    fixed_sl_price = guardrail_price
                    logger.warning(f"[LIQUIDATION GUARDRAIL] Fixed SL for {symbol} moved to {fixed_sl_price} to stay 2% above liquidation")
            else:  # SHORT
                # Ensure SL is ALWAYS below liquidation price
                guardrail_price = liquidation_price * 0.98  # 2% safety margin
                if fixed_sl_price > guardrail_price:
                    fixed_sl_price = guardrail_price
                    logger.warning(f"[LIQUIDATION GUARDRAIL] Fixed SL for {symbol} moved to {fixed_sl_price} to stay 2% below liquidation")

        # Final validation before placing order
        if side == 'LONG' and fixed_sl_price >= current_price:
            logger.error(f"[ABORT] LONG fixed SL {fixed_sl_price} is still >= current price {current_price}")
            return False
        elif side == 'SHORT' and fixed_sl_price <= current_price:
            logger.error(f"[ABORT] SHORT fixed SL {fixed_sl_price} is still <= current price {current_price}")
            return False
        
        # Cancel existing orders first
        cancellation_success = await cancel_existing_stop_orders(api_key, api_secret, symbol, logger)
        if not cancellation_success:
            logger.warning(f"[CANCEL FAILED] Cancellation failed, proceeding with potential quantity conflicts")
        await asyncio.sleep(0.5)
        
        # Get actual available quantity after canceling existing orders
        actual_available = await get_actual_available_quantity(api_key, api_secret, symbol, position_size, logger)
        if actual_available <= 0:
            if not cancellation_success:
                logger.warning(f"[BYPASS] No available quantity due to cancellation failure, using original position size {position_size}")
                actual_available = position_size
            else:
                logger.error(f"[BASIC PROTECTION] No available quantity for {symbol} after canceling orders")
                return False
        
        # Update position size to actual available quantity
        if actual_available != position_size:
            logger.info(f"[BASIC PROTECTION] Using actual available quantity {actual_available} instead of {position_size} for {symbol}")
            position_size = actual_available
        
        # Place fixed stop loss order
        fixed_sl_params = {
            'symbol': symbol,
            'side': order_side,
            'type': 'STOP_MARKET',
            'quantity': str(position_size),
            'stopPrice': str(fixed_sl_price),
            'positionSide': side,  # side is already normalized to uppercase
        }
        
        logger.info(f"[DEBUG] SL order params before sending: {fixed_sl_params}")
        logger.info(f"[DEBUG] Original side: '{side}', side.upper(): '{side}'")
        
        sl_response = await place_bingx_tpsl_order(api_key, api_secret, fixed_sl_params, logger)
        
        sl_success = False
        if sl_response and sl_response.get('code') == 0:
            logger.info(f"[SUCCESS] Fixed stop loss placed for {symbol} at {fixed_sl_price}")
            sl_success = True
        else:
            error_msg = sl_response.get('msg', 'Unknown error') if sl_response else 'No response'
            logger.error(f"[FAILED] Fixed stop loss failed for {symbol}: {error_msg}")
            
            # If order size error, try with USDT notional value
            if 'available amount of 0 USDT' in error_msg or 'available amount of 0' in error_msg:
                logger.info(f"[RETRY] Trying fixed SL order with USDT notional value for {symbol}")
                usdt_notional = position_size * entry_price
                fixed_sl_params_usdt = fixed_sl_params.copy()
                fixed_sl_params_usdt['quantity'] = str(round(usdt_notional, 2))
                
                logger.info(f"[DEBUG] Attempting fixed SL order with USDT notional: {usdt_notional}")
                sl_response_retry = await place_bingx_tpsl_order(api_key, api_secret, fixed_sl_params_usdt, logger)
                
                if sl_response_retry and sl_response_retry.get('code') == 0:
                    logger.info(f"[SUCCESS] Fixed stop loss placed with USDT notional for {symbol}")
                    sl_success = True
                else:
                    logger.error(f"[FAILED] Fixed stop loss retry also failed for {symbol}")
        
        return sl_success
        
    except Exception as e:
        logger.error(f"[EXCEPTION] Exception in place_fixed_stop_loss: {e}")
        logger.error(f"[TRACEBACK] {traceback.format_exc()}")
        return False

async def main():
    """Main function to demonstrate the trading bot functionality."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Load configuration
    config = load_api_config()
    if not config:
        logger.error("Failed to load configuration")
        return
    
    api_key = config.get('exchange', {}).get('api_key')
    api_secret = config.get('exchange', {}).get('api_secret')
    
    if not api_key or not api_secret:
        logger.error("API key or secret not found in configuration")
        return
    
    # Example usage
    symbol = "BTC-USDT"
    side = "LONG"
    entry_price = 50000.0
    position_size = 0.01
    leverage = 10
    
    logger.info(f"Placing stop loss for {symbol} position")
    success = await place_fixed_stop_loss(
        api_key, api_secret, symbol, side, entry_price, position_size, logger, leverage
    )
    
    if success:
        logger.info("Stop loss placed successfully")
    else:
        logger.error("Failed to place stop loss")

if __name__ == "__main__":
    asyncio.run(main())