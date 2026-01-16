#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
BingX API Client for Perpetual Futures Trading
Implements authentication and API calls to BingX exchange
"""

import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List
from urllib.parse import urlencode

import requests


class BingXClient:
    """
    BingX API Client for perpetual futures trading
    Handles authentication, request signing, and API calls
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = "https://open-api-vst.bingx.com",
        recv_window_ms: int = 5000,
    ):
        """
        Initialize BingX client
        
        Args:
            api_key: BingX API key
            api_secret: BingX API secret
            base_url: Base URL for BingX API (default: demo trading URL)
            recv_window_ms: Receive window in milliseconds for request validity
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.recv_window_ms = recv_window_ms
        self.session = requests.Session()
        self.session.headers.update({
            "X-BX-APIKEY": self.api_key,
            "Content-Type": "application/json",
        })

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """
        Generate HMAC SHA256 signature for request
        
        Args:
            params: Request parameters
            
        Returns:
            Hex signature string
        """
        query_string = urlencode(sorted(params.items()))
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return signature

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to BingX API
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            params: Request parameters
            signed: Whether to sign the request
            
        Returns:
            JSON response as dictionary
        """
        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            params["recvWindow"] = self.recv_window_ms
            params["signature"] = self._generate_signature(params)

        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, params=params, timeout=30)
            elif method.upper() == "POST":
                response = self.session.post(url, params=params, timeout=30)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, params=params, timeout=30)
            else:
                return {"code": -1, "msg": f"Unsupported HTTP method: {method}"}

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"code": -1, "msg": f"Request failed: {str(e)}"}
        except Exception as e:
            return {"code": -1, "msg": f"Unexpected error: {str(e)}"}

    def get_trades(
        self,
        symbol: Optional[str] = None,
        startTime: Optional[int] = None,
        endTime: Optional[int] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """
        Get trade fills history
        
        Args:
            symbol: Trading pair symbol (e.g., "BTC-USDT")
            startTime: Start timestamp in milliseconds
            endTime: End timestamp in milliseconds
            limit: Number of records to return
            
        Returns:
            API response with trade fills
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        if startTime:
            params["startTime"] = startTime
        if endTime:
            params["endTime"] = endTime
        if limit:
            params["limit"] = limit

        return self._request("GET", "/openApi/swap/v2/user/trades", params)

    def get_all_orders(
        self,
        symbol: str,
        startTs: Optional[int] = None,
        endTs: Optional[int] = None,
        pageSize: int = 100,
    ) -> Dict[str, Any]:
        """
        Get all orders history
        
        Args:
            symbol: Trading pair symbol
            startTs: Start timestamp in milliseconds
            endTs: End timestamp in milliseconds
            pageSize: Number of records per page
            
        Returns:
            API response with orders
        """
        params = {"symbol": symbol}
        if startTs:
            params["startTs"] = startTs
        if endTs:
            params["endTs"] = endTs
        if pageSize:
            params["pageSize"] = pageSize

        return self._request("GET", "/openApi/swap/v2/user/allOrders", params)

    def get_position_history(
        self,
        symbol: str,
        startTs: Optional[int] = None,
        endTs: Optional[int] = None,
        pageIndex: int = 1,
        pageSize: int = 100,
    ) -> Dict[str, Any]:
        """
        Get position history
        
        Args:
            symbol: Trading pair symbol
            startTs: Start timestamp in milliseconds
            endTs: End timestamp in milliseconds
            pageIndex: Page number
            pageSize: Number of records per page
            
        Returns:
            API response with position history
        """
        params = {
            "symbol": symbol,
            "pageIndex": pageIndex,
            "pageSize": pageSize,
        }
        if startTs:
            params["startTs"] = startTs
        if endTs:
            params["endTs"] = endTs

        return self._request("GET", "/openApi/swap/v1/user/positionHistory", params)

    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel a normal order
        
        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel
            
        Returns:
            API response
        """
        params = {
            "symbol": symbol,
            "orderId": order_id,
        }
        return self._request("DELETE", "/openApi/swap/v2/trade/order", params)

    def cancel_stop_loss(self, symbol: str, stop_loss_id: str) -> Dict[str, Any]:
        """
        Cancel a stop loss order (trigger order)
        
        This uses the correct API endpoint for canceling trigger orders (stop loss/take profit).
        The endpoint is different from regular order cancellation.
        
        Args:
            symbol: Trading pair symbol
            stop_loss_id: Stop loss order ID to cancel
            
        Returns:
            API response
        """
        params = {
            "symbol": symbol,
            "stopLossId": stop_loss_id,
        }
        # Use the correct endpoint for canceling trigger orders (stop loss/take profit)
        # The v2 endpoint is for trigger orders, not v1 or regular order endpoints
        return self._request("DELETE", "/openApi/swap/v2/trade/stopLoss", params)

    def cancel_all_trigger_orders(self, symbol: str) -> Dict[str, Any]:
        """
        Cancel all trigger orders (stop loss/take profit) for a symbol
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            API response
        """
        params = {"symbol": symbol}
        return self._request("DELETE", "/openApi/swap/v2/trade/allStopLoss", params)

    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get open orders
        
        Args:
            symbol: Trading pair symbol (optional, if not provided returns all symbols)
            
        Returns:
            API response with open orders
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/trade/openOrders", params)

    def get_trigger_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get trigger orders (stop loss/take profit)
        
        Args:
            symbol: Trading pair symbol (optional)
            
        Returns:
            API response with trigger orders
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return self._request("GET", "/openApi/swap/v2/trade/stopLoss/openOrders", params)
