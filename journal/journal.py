#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Trade Journal for logging and tracking trades
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class TradeJournal:
    """Simple trade journal for logging trade open/close events"""

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize trade journal
        
        Args:
            log_dir: Directory to store journal files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.journal_file = self.log_dir / "trade_journal.json"
        self.trades = self._load_trades()

    def _load_trades(self) -> List[Dict[str, Any]]:
        """Load trades from journal file"""
        if self.journal_file.exists():
            try:
                with open(self.journal_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_trades(self):
        """Save trades to journal file"""
        try:
            with open(self.journal_file, "w", encoding="utf-8") as f:
                json.dump(self.trades, f, indent=2)
        except Exception as e:
            print(f"Failed to save journal: {e}")

    def generate_trade_id(self) -> str:
        """Generate a unique trade ID"""
        return f"trade_{int(datetime.now().timestamp() * 1000)}"

    def get_open_trades(self) -> List[Dict[str, Any]]:
        """Get all open trades"""
        return [t for t in self.trades if t.get("status") == "open"]

    def log_open(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        price: float,
        stop_loss: float,
        take_profits: List[float],
        quantity: float,
        leverage: float,
        tags: List[str],
        confidence: int,
        notes: Optional[str],
        setup: str,
        screenshot: Optional[str],
        source: str,
    ):
        """
        Log trade open event
        
        Args:
            trade_id: Unique trade identifier
            symbol: Trading symbol
            side: Trade side (LONG/SHORT)
            price: Entry price
            stop_loss: Stop loss price
            take_profits: List of take profit prices
            quantity: Position size
            leverage: Leverage used
            tags: List of tags
            confidence: Confidence level
            notes: Trade notes
            setup: Trade setup description
            screenshot: Screenshot path
            source: Source of the trade
        """
        trade = {
            "trade_id": trade_id,
            "symbol": symbol,
            "side": side.upper(),
            "price": price,
            "stop_loss": stop_loss,
            "take_profits": take_profits,
            "quantity": quantity,
            "leverage": leverage,
            "tags": tags,
            "confidence": confidence,
            "notes": notes,
            "setup": setup,
            "screenshot": screenshot,
            "source": source,
            "open_time": datetime.now().isoformat(),
            "status": "open",
        }
        self.trades.append(trade)
        self._save_trades()

    def log_close(
        self,
        trade_id: str,
        exit_price: float,
        realized_pnl: float,
        realized_pnl_percent: float,
        fees: float,
        exit_reason: str,
        exit_notes: Optional[str],
        exit_screenshot: Optional[str],
    ):
        """
        Log trade close event
        
        Args:
            trade_id: Trade identifier
            exit_price: Exit price
            realized_pnl: Realized profit/loss
            realized_pnl_percent: Realized PnL percentage
            fees: Trading fees
            exit_reason: Reason for exit
            exit_notes: Exit notes
            exit_screenshot: Exit screenshot path
        """
        for trade in self.trades:
            if trade.get("trade_id") == trade_id:
                trade["exit_price"] = exit_price
                trade["realized_pnl"] = realized_pnl
                trade["realized_pnl_percent"] = realized_pnl_percent
                trade["fees"] = fees
                trade["exit_reason"] = exit_reason
                trade["exit_notes"] = exit_notes
                trade["exit_screenshot"] = exit_screenshot
                trade["close_time"] = datetime.now().isoformat()
                trade["status"] = "closed"
                self._save_trades()
                break
