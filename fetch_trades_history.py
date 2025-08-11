#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import ccxt


def to_ccxt_swap(sym: str) -> str:
    # Перетворює "BTCUSDT" у формат "BTC/USDT:USDT"
    s = sym.strip().upper()
    if ":USDT" in s:
        return s
    if "/" in s:
        base, quote = s.split("/")
        return f"{base}/USDT:USDT" if quote == "USDT" else f"{base}/{quote}:USDT"
    if s.endswith("USDT"):
        base = s[:-4]
        return f"{base}/USDT:USDT"
    return s


def parse_since(arg: Optional[str]) -> Optional[int]:
    """
    Приймає:
      - None -> 30 днів тому
      - ціле число -> трактуємо як мілісекунди epoch
      - ISO-дату '2024-07-01' -> в мс
      - '7d', '30d' -> now - X днів
    """
    if not arg:
        return int(time.time() * 1000 - 30 * 24 * 60 * 60 * 1000)
    s = str(arg).strip().lower()
    if s.endswith("d") and s[:-1].isdigit():
        days = int(s[:-1])
        return int(time.time() * 1000 - days * 24 * 60 * 60 * 1000)
    if s.isdigit():
        return int(s)
    try:
        ts = pd.to_datetime(s, utc=True)
        return int(ts.timestamp() * 1000)
    except Exception:
        raise ValueError(f"Cannot parse --since='{arg}'")


def flatten_trades(trades: List[Dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for t in trades:
        fee_cost, fee_ccy = None, None
        fee = t.get("fee", {})
        if isinstance(fee, dict):
            fee_cost = fee.get("cost")
            fee_ccy = fee.get("currency")
        rows.append(
            {
                "timestamp": t.get("timestamp"),
                "datetime": t.get("datetime"),
                "symbol": t.get("symbol"),
                "id": t.get("id"),
                "order": t.get("order"),
                "side": t.get("side"),
                "takerOrMaker": t.get("takerOrMaker"),
                "price": t.get("price"),
                "amount": t.get("amount"),
                "cost": t.get("cost"),
                "fee": fee_cost,
                "feeCurrency": fee_ccy,
                "info": t.get("info"),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df.sort_values(["timestamp", "id"], inplace=True, kind="mergesort")
    return df


def fetch_my_trades_for_symbol(
    exchange, symbol: str, since_ms: Optional[int], limit_per_call: int, sleep_sec: float,
) -> List[Dict[str, Any]]:
    """
    Пагінує угоди за timestamp (since) для одного символа.
    """
    all_trades = []
    cursor = since_ms
    while True:
        batch = exchange.fetch_my_trades(symbol=symbol, since=cursor, limit=limit_per_call)
        if not batch:
            break
        all_trades.extend(batch)
        last_ts = max([t["timestamp"] for t in batch if t.get("timestamp")])
        # уникнути зациклення
        if cursor is not None and last_ts is not None and last_ts <= cursor:
            break
        cursor = (last_ts or cursor or 0) + 1
        if len(batch) < limit_per_call:
            break
        time.sleep(sleep_sec)
    return all_trades


def main():
    ap = argparse.ArgumentParser(description="Fetch account trade history and save to logs/trades-h.csv")
    ap.add_argument("--exchange", default="bingx", help="ccxt exchange id (default: bingx)")
    ap.add_argument("--apiKey", default=os.getenv("BINGX_API_KEY"))
    ap.add_argument("--secret", default=(os.getenv("BINGX_API_SECRET") or os.getenv("BINGX_SECRET")))
    ap.add_argument("--symbols", nargs="*", help="optional list of symbols, e.g. BTCUSDT ETHUSDT")
    ap.add_argument("--since", default="30d", help="start time, e.g. '2024-07-01', '30d' or epoch-ms")
    ap.add_argument("--limit", type=int, default=1000, help="limit per API call")
    ap.add_argument("--sleep", type=float, default=0.3, help="sleep between calls")
    ap.add_argument("--out", default="logs/trades-h.csv", help="output CSV file")
    ap.add_argument("--append", action="store_true", help="append to existing CSV (dedupe)")
    ap.add_argument("--replace", action="store_true", help="overwrite existing file if present")
    ap.add_argument("--bingx-demo", action="store_true", help="use BingX demo REST API (not ccxt)")
    ap.add_argument("--config", default="config/settings.yaml", help="YAML config file for keys/base_url")
    ap.add_argument("--source", choices=["auto", "fills", "orders"], default="auto", help="demo data source")
    ap.add_argument("--journal", action="store_true", help="enable trade journal integration")
    args = ap.parse_args()

    if args.bingx_demo:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        try:
            from data_providers.bingx_client import BingXClient
        except ImportError as e:
            raise SystemExit(f"BingXClient not available: {e}")
        try:
            from journal.journal import TradeJournal
        except ImportError:
            TradeJournal = None
        import yaml
        cfg_base_url = None
        if args.config and os.path.exists(args.config):
            with open(args.config, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            ex_cfg = (cfg.get("exchange") or {})
            if not args.apiKey:
                env_name = str(ex_cfg.get("apiKey_env", "BINGX_API_KEY"))
                args.apiKey = ex_cfg.get("apiKey") or os.getenv(env_name) or os.getenv("BINGX_API_KEY")
            if not args.secret:
                env_name_s = str(ex_cfg.get("secret_env", "BINGX_API_SECRET"))
                args.secret = ex_cfg.get("secret") or os.getenv(env_name_s) or os.getenv("BINGX_API_SECRET") or os.getenv("BINGX_SECRET")
            cfg_base_url = ex_cfg.get("base_url")
        if not args.apiKey or not args.secret:
            raise SystemExit("API keys required.")
        base_url = cfg_base_url or "https://open-api-vst.bingx.com"
        bx = BingXClient(base_url=base_url, recv_window_ms=5000, api_key=args.apiKey, api_secret=args.secret)
        since_ms = parse_since(args.since)
        
        def to_bx(sym: str) -> str:
            s = sym.strip().upper()
            if s.endswith("-USDT"):
                return s  # Already in BingX format
            if "/" in s:
                return f"{s.split('/')[0]}-USDT"
            if s.endswith("USDT") and not s.endswith("-USDT"):
                return f"{s[:-4]}-USDT"
            return s.replace(":USDT", "").replace("/USDT", "-USDT")

        if args.symbols:
            bx_symbols = [to_bx(s) for s in args.symbols]
        else:
            bx_symbols = []
            if args.config and os.path.exists(args.config):
                try:
                    with open(args.config, "r", encoding="utf-8") as f:
                        cfgf = yaml.safe_load(f) or {}
                    ds = cfgf.get("data", {}).get("symbols") or []
                    bx_symbols = [to_bx(s) for s in ds]
                except Exception:
                    pass
            if not bx_symbols:
                bx_symbols = ["BTC-USDT", "ETH-USDT", "BCH-USDT"]

        use_orders = (args.source == "orders")
        use_fills = (args.source in ("auto", "fills"))
        records = []
        found_any = False
        
        print(f"[DEMO] base_url={base_url} symbols={len(bx_symbols)} since={since_ms} source={args.source}")
        
        # Per-symbol retrieval with fallback
        for s in bx_symbols:
            try:
                resp = None
                if use_fills:
                    resp = bx.get_trades(symbol=s, startTime=since_ms, endTime=int(time.time() * 1000), limit=args.limit)
                if (resp is None or (isinstance(resp, dict) and resp.get("code") not in (0, "0"))) and use_orders:
                    resp = bx.get_all_orders(symbol=s, startTs=since_ms, endTs=int(time.time() * 1000), pageSize=min(100, args.limit))
                if not isinstance(resp, dict):
                    print(f"[DEMO] {s}: unexpected response type: {type(resp)}")
                    continue
                if resp.get("code") not in (0, "0"):
                    msg = resp.get("msg") or resp.get("message") or "unknown error"
                    print(f"[DEMO] {s}: code={resp.get('code')} msg={msg}")
                    continue
                data = resp.get("data")
                if isinstance(data, dict) and "list" in data:
                    data = data.get("list")
                if data is None:
                    data = resp.get("list") or []
                if data:
                    found_any = True
                for it in data:
                    if not isinstance(it, dict):
                        continue
                    ts = int(it.get("time") or it.get("timestamp") or it.get("transactTime") or it.get("updateTime") or 0)
                    price = float(it.get("price") or it.get("avgPrice") or it.get("fillPrice") or it.get("avgExecutedPrice") or 0.0)
                    qty = float(it.get("qty") or it.get("executedQty") or it.get("quantity") or it.get("executedVolume") or 0.0)
                    fee = float(it.get("commission") or it.get("fee") or it.get("fees") or it.get("commissionAmount") or 0.0)
                    side = str(it.get("side") or it.get("direction") or it.get("orderSide") or "").upper()
                    realized = float(it.get("realizedPnl") or it.get("pnl") or it.get("realized") or it.get("realizedProfitLoss") or 0.0)
                    records.append({
                        "timestamp": ts,
                        "datetime": pd.to_datetime(ts, unit="ms", utc=True).isoformat(),
                        "symbol": it.get("symbol") or s,
                        "side": side,
                        "price": price,
                        "amount": qty,
                        "fee": fee,
                        "realizedPnl": realized,
                        "info": it,
                        "isTwap": it.get("isTwap"),
                        "mainOrderId": it.get("mainOrderId"),
                    })
            except Exception as e:
                print(f"[DEMO] {s}: {e}")
                continue

        # Global fills fallback if no data found
        if not found_any and args.source in ("auto", "fills"):
            try:
                resp_all = bx.get_trades(startTime=since_ms, endTime=int(time.time() * 1000), limit=args.limit)
                if isinstance(resp_all, dict) and resp_all.get("code") in (0, "0"):
                    data = resp_all.get("data")
                    if isinstance(data, dict) and "list" in data:
                        data = data.get("list")
                    if data is None:
                        data = resp_all.get("list") or []
                    for it in data:
                        if not isinstance(it, dict):
                            continue
                        ts = int(it.get("time") or it.get("timestamp") or it.get("transactTime") or it.get("updateTime") or 0)
                        price = float(it.get("price") or it.get("avgPrice") or it.get("fillPrice") or 0.0)
                        qty = float(it.get("qty") or it.get("executedQty") or it.get("quantity") or 0.0)
                        fee = float(it.get("commission") or it.get("fee") or it.get("fees") or 0.0)
                        side = str(it.get("side") or it.get("direction") or "").upper()
                        realized = float(it.get("realizedPnl") or it.get("pnl") or it.get("realized") or 0.0)
                        records.append({
                            "timestamp": ts,
                            "datetime": pd.to_datetime(ts, unit="ms", utc=True).isoformat(),
                            "symbol": it.get("symbol") or "",
                            "side": side,
                            "price": price,
                            "amount": qty,
                            "fee": fee,
                            "realizedPnl": realized,
                            "info": it,
                            "isTwap": it.get("isTwap"),
                            "mainOrderId": it.get("mainOrderId"),
                        })
            except Exception as e:
                print(f"[DEMO] global: {e}")

        # Position history fallback
        if not records:
            for s in bx_symbols:
                try:
                    ph = bx.get_position_history(symbol=s, startTs=since_ms, endTs=int(time.time() * 1000), pageIndex=1, pageSize=100)
                    if not isinstance(ph, dict) or ph.get("code") not in (0, "0"):
                        if isinstance(ph, dict):
                            print(f"[DEMO][posHist] {s}: code={ph.get('code')} msg={ph.get('msg') or ph.get('message')}")
                        continue
                    pdata = ph.get("data")
                    if isinstance(pdata, str):
                        try:
                            import json as _json
                            pdata = _json.loads(pdata)
                        except Exception:
                            pdata = []
                    if isinstance(pdata, dict):
                        for k in ("positionHistory","list","rows","records","positions","items","data"):
                            if k in pdata and isinstance(pdata.get(k), list):
                                pdata = pdata.get(k)
                                break
                        if isinstance(pdata, dict):
                            pdata = [pdata]
                    if pdata is None:
                        pdata = ph.get("list")
                    if not isinstance(pdata, list) or not pdata:
                        continue
                    for it in pdata:
                        if not isinstance(it, dict):
                            continue
                        ts = int(it.get("updateTime") or it.get("timestamp") or it.get("time") or it.get("closeTime") or 0)
                        rpnl = float(it.get("realized") or it.get("realizedPnl") or it.get("pnl") or it.get("realizedProfit") or 0.0)
                        side_raw = str(it.get("positionSide") or it.get("side") or it.get("direction") or "").upper()
                        price = float(it.get("closePrice") or it.get("avgPrice") or it.get("price") or it.get("exitPrice") or 0.0)
                        qty = float(it.get("closeQty") or it.get("qty") or it.get("quantity") or it.get("closeQuantity") or 0.0)
                        side = "SELL" if side_raw == "LONG" else ("BUY" if side_raw == "SHORT" else side_raw)
                        records.append({
                            "timestamp": ts,
                            "datetime": pd.to_datetime(ts, unit="ms", utc=True).isoformat(),
                            "symbol": s,
                            "side": side,
                            "price": price,
                            "amount": qty,
                            "fee": float(it.get("fee") or it.get("closeFee") or it.get("commission") or 0.0),
                            "realizedPnl": rpnl,
                            "info": it,
                        })
                except Exception as e:
                    print(f"[DEMO] posHist {s}: {e}")

        if not records:
            print("[INFO] No trades fetched (demo). Nothing to write.")
            return

        df = pd.DataFrame(records)
        out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.append and out_path.exists() and not args.replace:
            try:
                df_old = pd.read_csv(out_path)
                df_all = pd.concat([df_old, df], ignore_index=True)
                df_all.drop_duplicates(subset=["timestamp","symbol","price","amount"], inplace=True)
                df_all.sort_values(["timestamp","symbol"], inplace=True, kind="mergesort")
                df_all.to_csv(out_path, index=False)
                print(f"[OK] appended {len(df)} (total {len(df_all)}) -> {out_path}")
            except Exception as e:
                print(f"[WARN] append failed: {e}; writing new")
                df.to_csv(out_path, index=False)
        else:
            df.to_csv(out_path, index=False)
            print(f"[OK] wrote {len(df)} -> {out_path}")

        # Journal integration
        if args.journal and TradeJournal is not None:
            tj = TradeJournal(Path("logs").as_posix())
            norm = lambda bx: bx.replace("-", "").replace(":USDT", "").replace("/USDT", "USDT")
            for _, r in df.iterrows():
                try:
                    realized = float(r.get("realizedPnl") or 0.0)
                    if realized == 0.0:
                        continue
                    bx_sym = str(r.get("symbol"))
                    side = str(r.get("side") or "").upper()
                    pos_side = "long" if side == "SELL" else ("short" if side == "BUY" else None)
                    if pos_side is None:
                        continue
                    sym_plain = norm(bx_sym)
                    opens = tj.get_open_trades()
                    cands = [t for t in opens if t.get("symbol") == sym_plain and str(t.get("side", "")).upper() == pos_side.upper()]
                    if cands:
                        cands.sort(key=lambda t: t.get("open_time", ""))
                        tid = cands[-1].get("trade_id")
                    else:
                        tid = tj.generate_trade_id()
                        tj.log_open(tid, sym_plain, pos_side.upper(), float(r["price"]), 0.0, [], float(r["amount"]), 0.0, ["hist_tool"], 1, None, "imported", None, "hist_tool")
                    tj.log_close(str(tid), float(r["price"]), realized, 0.0, float(r.get("fee") or 0.0), "hist_tool", None, None)
                except Exception:
                    continue
        return

    # ...existing code for ccxt/live branch...


if __name__ == "__main__":
    main()
