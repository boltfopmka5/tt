#!/usr/bin/env python3
"""
Bybit Professional Day Trading Signal Scanner - ENHANCED VERSION
Таймфреймы: 1ч, 2ч, 4ч | 35+ стратегий | 25+ индикаторов | 15+ свечных паттернов
Оптимизирован для дейтрейдинга с высокоточными сигналами
"""
import telebot
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')
import mplfinance as mpf
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import os
os.chdir('/opt/bot')
from datetime import datetime
from pybit.unified_trading import HTTP
#import talib
from scipy import stats
import json

# ======================== TELEGRAM КОНФИГУРАЦИЯ ========================
TELEGRAM_BOT_TOKEN = "8544101804:AAERVv4TUsPTiBvePsyW0GAhnE0-pdLRoMc"  # Токен вашего бота
TELEGRAM_CHAT_ID = "-1003715048435"  # ID группы (с минусом)
TELEGRAM_THREAD_ID = 18  # ID темы (опционально, если тема не нужна - оставьте None)
# ==============================================================

# ======================== РАСШИРЕННАЯ КОНФИГУРАЦИЯ ========================
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "AVAXUSDT", "MATICUSDT", "LINKUSDT", "UNIUSDT"]
TIMEFRAMES = ["60", "120", "240"]  # 1ч, 2ч, 4ч для дейтрейдинга
CANDLES_LIMIT = 500  # Увеличено для лучшего анализа
MIN_CONFIDENCE_SCORE = 70  # Повышено для точности
MIN_RR_RATIO = 2.5  # Улучшенное соотношение риск/прибыль
MAX_DAILY_TRADES = 12
MAX_DAILY_LOSS_PERCENT = 5.0
MIN_VOLUME_RATIO = 1.3  # Минимальное отношение объема
USE_AI_FILTER = True  # Использовать AI-подобную фильтрацию сигналов
MAX_CORRELATION = 0.7  # Максимальная корреляция между сигналами
# ==============================================================

class DataFetcher:
    """Улучшенный загрузчик данных с кэшированием и предзагрузкой"""
    
    def __init__(self):
        self.session = HTTP(testnet=False)
        self.cache = {}
        self.cache_time = {}
        self.prefetch_data = {}
    
    async def get_klines(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        cache_key = f"{symbol}_{timeframe}"
        now = datetime.now()
        
        if cache_key in self.cache and (now - self.cache_time[cache_key]).seconds < 20:
            return self.cache[cache_key]
        
        try:
            resp = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=timeframe,
                limit=limit
            )
            if resp["retCode"] != 0:
                return pd.DataFrame()
            
            data = resp["result"]["list"]
            df = pd.DataFrame(data, columns=["timestamp", "open", "high", "low", "close", "volume", "turnover"])
            
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=["open", "high", "low", "close", "volume"])
            
            if len(df) < 50:
                return pd.DataFrame()
            
            df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
            df = df.iloc[::-1].reset_index(drop=True)
            
            # Добавляем процентные изменения
            df["returns"] = df["close"].pct_change()
            df["log_returns"] = np.log(df["close"] / df["close"].shift(1))
            
            self.cache[cache_key] = df
            self.cache_time[cache_key] = now
            return df
            
        except Exception as e:
            print(f"⚠️ Ошибка {symbol} {timeframe}: {e}")
            return pd.DataFrame()
    
    async def prefetch_all(self, symbols: List[str], timeframe: str, limit: int):
        """Предзагрузка данных для всех символов"""
        tasks = [self.get_klines(symbol, timeframe, limit) for symbol in symbols]
        await asyncio.gather(*tasks)


class AdvancedIndicators:
    """Расширенный набор индикаторов с использованием TA-Lib где возможно"""
    
    @staticmethod
    def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Добавляет все индикаторы в DataFrame"""
        if df.empty or len(df) < 50:
            return df
        
        df_result = df.copy()
        close = df["close"].values
        high = df["high"].values
        low = df["low"].values
        volume = df["volume"].values
        
        # ===== ТРЕНДОВЫЕ ИНДИКАТОРЫ (расширенные) =====
        # EMA (5, 8, 13, 21, 34, 50, 89, 144, 200) - числа Фибоначчи
        for period in [5, 8, 13, 21, 34, 50, 89, 144, 200]:
            df_result[f"ema{period}"] = df["close"].ewm(span=period, adjust=False).mean()
        
        # SMA (20, 50, 100, 200)
        for period in [20, 50, 100, 200]:
            df_result[f"sma{period}"] = df["close"].rolling(window=period).mean()
        
        # HMA (Hull Moving Average) - быстрая MA
        df_result["hma"] = AdvancedIndicators._calc_hma(df["close"], 20)
        
        # TEMA (Triple EMA)
        df_result["tema"] = AdvancedIndicators._calc_tema(df["close"], 20)
        
        # MACD с расширенными параметрами
        exp1 = df["close"].ewm(span=12, adjust=False).mean()
        exp2 = df["close"].ewm(span=26, adjust=False).mean()
        df_result["macd"] = exp1 - exp2
        df_result["macd_signal"] = df_result["macd"].ewm(span=9, adjust=False).mean()
        df_result["macd_hist"] = df_result["macd"] - df_result["macd_signal"]
        df_result["macd_hist_direction"] = np.where(df_result["macd_hist"] > df_result["macd_hist"].shift(1), 1, -1)
        
        # MACD 2 (более быстрый)
        exp1_fast = df["close"].ewm(span=6, adjust=False).mean()
        exp2_fast = df["close"].ewm(span=13, adjust=False).mean()
        df_result["macd_fast"] = exp1_fast - exp2_fast
        df_result["macd_signal_fast"] = df_result["macd_fast"].ewm(span=5, adjust=False).mean()
        
        # ===== ОСЦИЛЛЯТОРЫ (расширенные) =====
        # RSI (7, 14, 21, 28)
        for period in [7, 14, 21, 28]:
            df_result[f"rsi{period}"] = AdvancedIndicators._calc_rsi(df["close"], period)
        
        # Stochastic RSI
        df_result["stoch_rsi_k"], df_result["stoch_rsi_d"] = AdvancedIndicators._calc_stoch_rsi(df["close"], 14, 14, 3, 3)
        
        # Ultimate Oscillator
        df_result["ultimate_osc"] = AdvancedIndicators._calc_ultimate_oscillator(df["high"], df["low"], df["close"])
        
        # Awesome Oscillator
        df_result["ao"] = AdvancedIndicators._calc_awesome_oscillator(df["high"], df["low"])
        
        # Stochastic (5,3,3), (14,3,3), (21,5,5)
        for period in [5, 14, 21]:
            df_result[f"stoch_k_{period}"] = AdvancedIndicators._calc_stochastic(df["high"], df["low"], df["close"], period)
            df_result[f"stoch_d_{period}"] = df_result[f"stoch_k_{period}"].rolling(3).mean()
        
        # CCI (14, 20, 50)
        for period in [14, 20, 50]:
            df_result[f"cci{period}"] = AdvancedIndicators._calc_cci(df["high"], df["low"], df["close"], period)
        
        # MFI (Money Flow Index)
        df_result["mfi14"] = AdvancedIndicators._calc_mfi(df["high"], df["low"], df["close"], df["volume"], 14)
        
        # Williams %R
        df_result["williams_r"] = AdvancedIndicators._calc_williams_r(df["high"], df["low"], df["close"], 14)
        
        # RAVI (Range Action Verification Index)
        df_result["ravi"] = AdvancedIndicators._calc_ravi(df["close"])
        
        # ===== ВОЛАТИЛЬНОСТЬ (расширенная) =====
        # Bollinger Bands с разными параметрами
        for period, std in [(20, 2), (20, 2.5), (50, 2)]:
            bb_middle = df["close"].rolling(window=period).mean()
            bb_std = df["close"].rolling(window=period).std()
            df_result[f"bb_upper_{period}_{std}"] = bb_middle + (bb_std * std)
            df_result[f"bb_middle_{period}"] = bb_middle
            df_result[f"bb_lower_{period}_{std}"] = bb_middle - (bb_std * std)
        
        # Основные BB
        df_result["bb_width"] = (df_result["bb_upper_20_2"] - df_result["bb_lower_20_2"]) / df_result["bb_middle_20"]
        df_result["bb_position"] = (df["close"] - df_result["bb_lower_20_2"]) / (df_result["bb_upper_20_2"] - df_result["bb_lower_20_2"])
        df_result["bb_bandwidth"] = df_result["bb_width"]
        df_result["bb_percent_b"] = df_result["bb_position"]
        
        # Keltner Channels
        atr_20 = AdvancedIndicators._calc_atr(df["high"], df["low"], df["close"], 20)
        df_result["kc_upper_ema20"] = df_result["ema21"] + (atr_20 * 1.5)
        df_result["kc_lower_ema20"] = df_result["ema21"] - (atr_20 * 1.5)
        df_result["kc_upper_ema34"] = df_result["ema34"] + (atr_20 * 2)
        df_result["kc_lower_ema34"] = df_result["ema34"] - (atr_20 * 2)
        
        # Donchian Channels
        df_result["dc_upper_20"] = df["high"].rolling(window=20).max()
        df_result["dc_lower_20"] = df["low"].rolling(window=20).min()
        df_result["dc_middle_20"] = (df_result["dc_upper_20"] + df_result["dc_lower_20"]) / 2
        
        # ATR (7, 14, 21)
        for period in [7, 14, 21]:
            df_result[f"atr{period}"] = AdvancedIndicators._calc_atr(df["high"], df["low"], df["close"], period)
        
        df_result["atr_percent"] = (df_result["atr14"] / df["close"]) * 100
        
        # Average True Range normalized
        df_result["atr_norm"] = df_result["atr14"] / df["close"]
        
        # Historical Volatility
        df_result["hv_10"] = df["returns"].rolling(window=10).std() * np.sqrt(365)
        df_result["hv_20"] = df["returns"].rolling(window=20).std() * np.sqrt(365)
        
        # Parkinson Volatility
        df_result["parkinson_vol"] = AdvancedIndicators._calc_parkinson_volatility(df["high"], df["low"], 20)
        
        # ===== ОБЪЕМНЫЕ ИНДИКАТОРЫ (расширенные) =====
        # Volume SMA
        for period in [10, 20, 50]:
            df_result[f"volume_sma{period}"] = df["volume"].rolling(window=period).mean()
        
        df_result["volume_ratio"] = df["volume"] / df_result["volume_sma20"]
        df_result["volume_ratio"] = df_result["volume_ratio"].replace([np.inf, -np.inf], 1).clip(0, 5)
        
        # Volume Weighted RSI
        df_result["vw_rsi"] = AdvancedIndicators._calc_vw_rsi(df["close"], df["volume"], 14)
        
        # OBV и его варианты
        df_result["obv"] = AdvancedIndicators._calc_obv(df["close"], df["volume"])
        df_result["obv_ema13"] = df_result["obv"].ewm(span=13, adjust=False).mean()
        df_result["obv_ema34"] = df_result["obv"].ewm(span=34, adjust=False).mean()
        df_result["obv_trend"] = np.where(df_result["obv"] > df_result["obv_ema13"], 1, -1)
        
        # Volume Profile (улучшенный)
        df_result["vp_high"] = df["volume"].where(df["close"] > df["close"].shift(1), 0)
        df_result["vp_low"] = df["volume"].where(df["close"] < df["close"].shift(1), 0)
        df_result["vp_ratio"] = df_result["vp_high"].rolling(20).sum() / df_result["vp_low"].rolling(20).sum()
        
        # Money Flow Index (уже есть, добавим сигнал)
        df_result["mfi_signal"] = np.where(df_result["mfi14"] < 20, 1, np.where(df_result["mfi14"] > 80, -1, 0))
        
        # Accumulation/Distribution
        df_result["ad"] = AdvancedIndicators._calc_accumulation_distribution(df["high"], df["low"], df["close"], df["volume"])
        df_result["ad_ema"] = df_result["ad"].ewm(span=20, adjust=False).mean()
        
        # Chaikin Money Flow
        df_result["cmf"] = AdvancedIndicators._calc_chaikin_money_flow(df["high"], df["low"], df["close"], df["volume"], 20)
        
        # VWAP и его улучшенная версия
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df_result["vwap"] = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()
        df_result["vwap_std"] = df_result["vwap"].rolling(20).std()
        df_result["vwap_distance"] = ((df["close"] - df_result["vwap"]) / df_result["vwap"]) * 100
        df_result["vwap_zscore"] = (df["close"] - df_result["vwap"]) / df_result["vwap_std"]
        
        # Anchored VWAP (последние 20 свечей)
        df_result["vwap_20"] = (typical_price.tail(20) * df["volume"].tail(20)).sum() / df["volume"].tail(20).sum()
        
        # ===== ДИВЕРГЕНЦИИ (расширенные) =====
        df_result["rsi_divergence"] = AdvancedIndicators._detect_divergence(df, df_result["rsi14"], "rsi")
        df_result["macd_divergence"] = AdvancedIndicators._detect_divergence(df, df_result["macd"], "macd")
        df_result["obv_divergence"] = AdvancedIndicators._detect_divergence(df, df_result["obv"], "obv")
        df_result["mfi_divergence"] = AdvancedIndicators._detect_divergence(df, df_result["mfi14"], "mfi")
        df_result["stoch_divergence"] = AdvancedIndicators._detect_divergence(df, df_result["stoch_k_14"], "stoch")
        
        # ===== ФИЛЬТРЫ ТРЕНДА (расширенные) =====
        # ADX (7, 14, 21)
        for period in [7, 14, 21]:
            df_result[f"adx{period}"] = AdvancedIndicators._calc_adx(df["high"], df["low"], df["close"], period)
        
        df_result["di_plus"] = AdvancedIndicators._calc_di_plus(df["high"], df["low"], df["close"], 14)
        df_result["di_minus"] = AdvancedIndicators._calc_di_minus(df["high"], df["low"], df["close"], 14)
        df_result["adx_cross"] = np.where((df_result["di_plus"] > df_result["di_minus"]) & 
                                          (df_result["adx14"] > 25), 1,
                                          np.where((df_result["di_minus"] > df_result["di_plus"]) & 
                                                   (df_result["adx14"] > 25), -1, 0))
        
        # Choppiness Index
        for period in [14, 20]:
            df_result[f"choppiness_{period}"] = AdvancedIndicators._calc_choppiness(df["high"], df["low"], df["close"], period)
        
        # SuperTrend
        df_result["supertrend"], df_result["supertrend_direction"] = AdvancedIndicators._calc_supertrend(df["high"], df["low"], df["close"], 10, 3)
        
        # Vortex Indicator
        df_result["vortex_plus"], df_result["vortex_minus"] = AdvancedIndicators._calc_vortex(df["high"], df["low"], df["close"], 14)
        
        # Elder's Force Index
        df_result["force_index"] = df["close"].diff() * df["volume"]
        df_result["force_index_ema"] = df_result["force_index"].ewm(span=13, adjust=False).mean()
        
        # ===== ПРОГНОЗНЫЕ МОДЕЛИ =====
        # Linear Regression Slope
        df_result["linreg_slope_20"] = AdvancedIndicators._calc_linreg_slope(df["close"], 20)
        df_result["linreg_r2_20"] = AdvancedIndicators._calc_linreg_r2(df["close"], 20)
        
        # Kalman Filter (упрощенный)
        df_result["kalman"] = AdvancedIndicators._calc_kalman_filter(df["close"])
        
        # Z-Score (относительно SMA)
        df_result["zscore_20"] = (df["close"] - df_result["sma20"]) / df["close"].rolling(20).std()
        df_result["zscore_50"] = (df["close"] - df_result["sma50"]) / df["close"].rolling(50).std()
        
        # Fibonacci Retracement Levels (автоматические)
        high_20 = df["high"].rolling(20).max()
        low_20 = df["low"].rolling(20).min()
        df_result["fib_0.236"] = high_20 - (high_20 - low_20) * 0.236
        df_result["fib_0.382"] = high_20 - (high_20 - low_20) * 0.382
        df_result["fib_0.5"] = high_20 - (high_20 - low_20) * 0.5
        df_result["fib_0.618"] = high_20 - (high_20 - low_20) * 0.618
        df_result["fib_0.786"] = high_20 - (high_20 - low_20) * 0.786
        
        # Pivot Points
        df_result["pivot_high"] = AdvancedIndicators._calc_pivot_high(df["high"], 5, 2)
        df_result["pivot_low"] = AdvancedIndicators._calc_pivot_low(df["low"], 5, 2)
        
        # Заполняем NaN
        numeric_cols = df_result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            df_result[col] = df_result[col].ffill().bfill().fillna(0)
        
        return df_result
    
    # ==================== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ====================
    
    @staticmethod
    def _calc_hma(close: pd.Series, period: int) -> pd.Series:
        """Hull Moving Average"""
        half_period = int(period / 2)
        sqrt_period = int(np.sqrt(period))
        
        wma_half = close.rolling(window=half_period).apply(
            lambda x: np.sum(x * np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1))
        )
        wma_full = close.rolling(window=period).apply(
            lambda x: np.sum(x * np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1))
        )
        
        hma_raw = 2 * wma_half - wma_full
        hma = hma_raw.rolling(window=sqrt_period).apply(
            lambda x: np.sum(x * np.arange(1, len(x) + 1)) / np.sum(np.arange(1, len(x) + 1))
        )
        
        return hma.ffill().bfill()
    
    @staticmethod
    def _calc_tema(close: pd.Series, period: int) -> pd.Series:
        """Triple Exponential Moving Average"""
        ema1 = close.ewm(span=period, adjust=False).mean()
        ema2 = ema1.ewm(span=period, adjust=False).mean()
        ema3 = ema2.ewm(span=period, adjust=False).mean()
        tema = 3 * ema1 - 3 * ema2 + ema3
        return tema.ffill().bfill()
    
    @staticmethod
    def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_stoch_rsi(close: pd.Series, rsi_period: int, stoch_period: int, k_period: int, d_period: int) -> Tuple[pd.Series, pd.Series]:
        """Stochastic RSI"""
        rsi = AdvancedIndicators._calc_rsi(close, rsi_period)
        min_rsi = rsi.rolling(window=stoch_period).min()
        max_rsi = rsi.rolling(window=stoch_period).max()
        
        stoch_rsi = (rsi - min_rsi) / (max_rsi - min_rsi) * 100
        k = stoch_rsi.rolling(window=k_period).mean()
        d = k.rolling(window=d_period).mean()
        
        return k.ffill().bfill().fillna(50), d.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_ultimate_oscillator(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
        """Ultimate Oscillator"""
        bp = close - pd.concat([low.shift(1), close.shift(1)], axis=1).min(axis=1)
        tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
        
        avg7 = bp.rolling(7).sum() / tr.rolling(7).sum()
        avg14 = bp.rolling(14).sum() / tr.rolling(14).sum()
        avg28 = bp.rolling(28).sum() / tr.rolling(28).sum()
        
        uo = 100 * (4 * avg7 + 2 * avg14 + avg28) / 7
        return uo.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_awesome_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
        """Awesome Oscillator"""
        median_price = (high + low) / 2
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        return ao.ffill().bfill().fillna(0)
    
    @staticmethod
    def _calc_ravi(close: pd.Series) -> pd.Series:
        """Range Action Verification Index"""
        long_ma = close.rolling(65).mean()
        short_ma = close.rolling(28).mean()
        ravi = (short_ma - long_ma) / long_ma * 100
        return ravi.ffill().bfill().fillna(0)
    
    @staticmethod
    def _calc_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr.ffill().bfill().fillna(tr.mean())
    
    @staticmethod
    def _calc_stochastic(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        lowest_low = low.rolling(window=period).min()
        highest_high = high.rolling(window=period).max()
        k = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        return k.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: abs(x - x.mean()).mean())
        cci = (tp - sma) / (0.015 * mad)
        return cci.ffill().bfill().fillna(0)
    
    @staticmethod
    def _calc_mfi(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        positive_flow = money_flow.where(typical_price > typical_price.shift(), 0).rolling(window=period).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(), 0).rolling(window=period).sum()
        mfi = 100 - (100 / (1 + positive_flow / negative_flow))
        return mfi.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        wr = -100 * ((highest_high - close) / (highest_high - lowest_low))
        return wr.ffill().bfill().fillna(-50)
    
    @staticmethod
    def _calc_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        return obv
    
    @staticmethod
    def _calc_vw_rsi(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        """Volume Weighted RSI"""
        weighted_close = close * volume
        delta = weighted_close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        vw_rsi = 100 - (100 / (1 + rs))
        return vw_rsi.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_accumulation_distribution(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Accumulation/Distribution Line"""
        clv = ((close - low) - (high - close)) / (high - low)
        clv = clv.fillna(0)
        ad = (clv * volume).cumsum()
        return ad
    
    @staticmethod
    def _calc_chaikin_money_flow(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        """Chaikin Money Flow"""
        mfm = ((close - low) - (high - close)) / (high - low)
        mfm = mfm.fillna(0)
        mfv = mfm * volume
        cmf = mfv.rolling(window=period).sum() / volume.rolling(window=period).sum()
        return cmf.ffill().bfill().fillna(0)
    
    @staticmethod
    def _detect_divergence(price_df: pd.DataFrame, indicator: pd.Series, name: str) -> pd.Series:
        """Обнаружение дивергенций: -1 бычья, 1 медвежья, 0 нет"""
        divergence = pd.Series(0, index=price_df.index)
        
        if len(price_df) < 30:
            return divergence
        
        for i in range(10, len(price_df)):
            # Медвежья дивергенция (цена выше, индикатор ниже)
            price_highs = price_df["high"].iloc[i-15:i].max()
            ind_highs = indicator.iloc[i-15:i].max()
            
            if price_df["high"].iloc[i] > price_highs and indicator.iloc[i] < ind_highs:
                divergence.iloc[i] = 1
            
            # Бычья дивергенция (цена ниже, индикатор выше)
            price_lows = price_df["low"].iloc[i-15:i].min()
            ind_lows = indicator.iloc[i-15:i].min()
            
            if price_df["low"].iloc[i] < price_lows and indicator.iloc[i] > ind_lows:
                divergence.iloc[i] = -1
        
        return divergence
    
    @staticmethod
    def _calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm = plus_dm.clip(lower=0)
        minus_dm = minus_dm.clip(upper=0).abs()
        
        atr = AdvancedIndicators._calc_atr(high, low, close, period)
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        return adx.ffill().bfill().fillna(25)
    
    @staticmethod
    def _calc_di_plus(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        plus_dm = high.diff().clip(lower=0)
        atr = AdvancedIndicators._calc_atr(high, low, close, period)
        return 100 * (plus_dm.rolling(window=period).mean() / atr).ffill().bfill().fillna(20)
    
    @staticmethod
    def _calc_di_minus(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        minus_dm = low.diff().clip(upper=0).abs()
        atr = AdvancedIndicators._calc_atr(high, low, close, period)
        return 100 * (minus_dm.rolling(window=period).mean() / atr).ffill().bfill().fillna(20)
    
    @staticmethod
    def _calc_choppiness(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        atr_sum = AdvancedIndicators._calc_atr(high, low, close, period).rolling(window=period).sum()
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        choppiness = 100 * np.log10(atr_sum / (highest_high - lowest_low)) / np.log10(period)
        choppiness = choppiness.clip(0, 100)
        return choppiness.ffill().bfill().fillna(50)
    
    @staticmethod
    def _calc_supertrend(high: pd.Series, low: pd.Series, close: pd.Series, period: int, multiplier: float) -> Tuple[pd.Series, pd.Series]:
        """SuperTrend Indicator"""
        atr = AdvancedIndicators._calc_atr(high, low, close, period)
        
        hl2 = (high + low) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=int)
        
        for i in range(period, len(close)):
            if i == period:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = 1
            else:
                if direction.iloc[i-1] == 1:
                    if close.iloc[i] <= lower_band.iloc[i]:
                        direction.iloc[i] = -1
                        supertrend.iloc[i] = upper_band.iloc[i]
                    else:
                        direction.iloc[i] = 1
                        supertrend.iloc[i] = max(lower_band.iloc[i], supertrend.iloc[i-1])
                else:
                    if close.iloc[i] >= upper_band.iloc[i]:
                        direction.iloc[i] = 1
                        supertrend.iloc[i] = lower_band.iloc[i]
                    else:
                        direction.iloc[i] = -1
                        supertrend.iloc[i] = min(upper_band.iloc[i], supertrend.iloc[i-1])
        
        supertrend = supertrend.ffill().bfill()
        direction = direction.ffill().bfill().fillna(0)
        
        return supertrend, direction
    
    @staticmethod
    def _calc_vortex(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> Tuple[pd.Series, pd.Series]:
        """Vortex Indicator"""
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        
        vm_plus = (high - low.shift()).abs()
        vm_minus = (low - high.shift()).abs()
        
        vortex_plus = vm_plus.rolling(window=period).sum() / tr.rolling(window=period).sum()
        vortex_minus = vm_minus.rolling(window=period).sum() / tr.rolling(window=period).sum()
        
        return vortex_plus.ffill().bfill().fillna(1), vortex_minus.ffill().bfill().fillna(1)
    
    @staticmethod
    def _calc_linreg_slope(close: pd.Series, period: int) -> pd.Series:
        """Linear Regression Slope"""
        slopes = []
        x = np.arange(period)
        
        for i in range(len(close)):
            if i < period:
                slopes.append(0)
            else:
                y = close.iloc[i-period:i].values
                slope, _, _, _, _ = stats.linregress(x, y)
                slopes.append(slope)
        
        return pd.Series(slopes, index=close.index)
    
    @staticmethod
    def _calc_linreg_r2(close: pd.Series, period: int) -> pd.Series:
        """Linear Regression R-squared"""
        r2s = []
        x = np.arange(period)
        
        for i in range(len(close)):
            if i < period:
                r2s.append(0)
            else:
                y = close.iloc[i-period:i].values
                _, _, r_value, _, _ = stats.linregress(x, y)
                r2s.append(r_value ** 2)
        
        return pd.Series(r2s, index=close.index)
    
    @staticmethod
    def _calc_kalman_filter(close: pd.Series) -> pd.Series:
        """Упрощенный Kalman Filter"""
        kalman = pd.Series(index=close.index, dtype=float)
        
        q = 0.0001  # process variance
        r = 0.01    # estimate error variance
        p = 1.0     # initial error covariance
        x = close.iloc[0]  # initial state
        
        for i in range(len(close)):
            # prediction
            x_pred = x
            p_pred = p + q
            
            # update
            k = p_pred / (p_pred + r)
            x = x_pred + k * (close.iloc[i] - x_pred)
            p = (1 - k) * p_pred
            
            kalman.iloc[i] = x
        
        return kalman
    
    @staticmethod
    def _calc_parkinson_volatility(high: pd.Series, low: pd.Series, period: int) -> pd.Series:
        """Parkinson Historical Volatility"""
        ratio = np.log(high / low) ** 2
        parkinson = np.sqrt((1 / (4 * np.log(2))) * ratio.rolling(window=period).mean())
        return parkinson.ffill().bfill().fillna(0)
    
    @staticmethod
    def _calc_pivot_high(high: pd.Series, left: int, right: int) -> pd.Series:
        """Определение pivot high"""
        pivot = pd.Series(0.0, index=high.index, dtype=float)  # Изменено на float
    
        for i in range(left, len(high) - right):
            if all(high.iloc[i] >= high.iloc[i-j] for j in range(1, left+1)) and \
                all(high.iloc[i] >= high.iloc[i+j] for j in range(1, right+1)):
                pivot.iloc[i] = float(high.iloc[i])  # Явное преобразование в float
    
        return pivot

    @staticmethod
    def _calc_pivot_low(low: pd.Series, left: int, right: int) -> pd.Series:
        """Определение pivot low"""
        pivot = pd.Series(0.0, index=low.index, dtype=float)  # Изменено на float
    
        for i in range(left, len(low) - right):
            if all(low.iloc[i] <= low.iloc[i-j] for j in range(1, left+1)) and \
                all(low.iloc[i] <= low.iloc[i+j] for j in range(1, right+1)):
                pivot.iloc[i] = float(low.iloc[i])  # Явное преобразование в float
    
        return pivot


class CandlePatterns:
    """15+ улучшенных свечных паттернов"""
    
    @staticmethod
    def detect_all(df: pd.DataFrame) -> Dict[str, bool]:
        """Детектирует все свечные паттерны"""
        if len(df) < 5:
            return {}
        
        patterns = {}
        
        # Базовые паттерны
        patterns.update(CandlePatterns._detect_single_candle(df))
        patterns.update(CandlePatterns._detect_two_candle(df))
        patterns.update(CandlePatterns._detect_three_candle(df))
        patterns.update(CandlePatterns._detect_reversal_patterns(df))
        patterns.update(CandlePatterns._detect_continuation_patterns(df))
        
        # Дополнительные паттерны
        patterns.update(CandlePatterns._detect_harami(df))
        patterns.update(CandlePatterns._detect_piercing(df))
        patterns.update(CandlePatterns._detect_dark_cloud(df))
        patterns.update(CandlePatterns._detect_kicker(df))
        patterns.update(CandlePatterns._detect_three_inside(df))
        patterns.update(CandlePatterns._detect_three_outside(df))
        
        return patterns
    
    @staticmethod
    def _detect_single_candle(df: pd.DataFrame) -> Dict[str, bool]:
        """Одиночные свечные паттерны"""
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        body = abs(last["close"] - last["open"])
        upper_wick = last["high"] - max(last["close"], last["open"])
        lower_wick = min(last["close"], last["open"]) - last["low"]
        total_range = last["high"] - last["low"]
        
        patterns = {}
        
        if total_range > 0:
            # Молот (Hammer)
            patterns["hammer"] = (lower_wick > body * 2) and (upper_wick < body * 0.5) and (last["close"] > last["open"])
            
            # Повешенный (Hanging Man)
            patterns["hanging_man"] = (lower_wick > body * 2) and (upper_wick < body * 0.5) and (last["close"] < last["open"])
            
            # Падающая звезда (Shooting Star)
            patterns["shooting_star"] = (upper_wick > body * 2) and (lower_wick < body * 0.5) and (last["close"] < last["open"])
            
            # Перевернутый молот (Inverted Hammer)
            patterns["inverted_hammer"] = (upper_wick > body * 2) and (lower_wick < body * 0.5) and (last["close"] > last["open"])
            
            # Доджи (Doji)
            patterns["doji"] = body <= total_range * 0.1
            
            # Длинная нога доджи (Long Legged Doji)
            patterns["long_legged_doji"] = (body <= total_range * 0.05) and (upper_wick > total_range * 0.4) and (lower_wick > total_range * 0.4)
            
            # Надгробный камень (Gravestone Doji)
            patterns["gravestone_doji"] = (body <= total_range * 0.05) and (lower_wick <= total_range * 0.1) and (upper_wick > total_range * 0.7)
            
            # Стрекоза (Dragonfly Doji)
            patterns["dragonfly_doji"] = (body <= total_range * 0.05) and (upper_wick <= total_range * 0.1) and (lower_wick > total_range * 0.7)
            
            # Спиннинг топ (Spinning Top)
            patterns["spinning_top"] = (body <= total_range * 0.4) and (upper_wick > body * 0.5) and (lower_wick > body * 0.5)
        
        # Маробозу (Marubozu)
        patterns["bullish_marubozu"] = (last["close"] > last["open"]) and (upper_wick <= body * 0.05) and (lower_wick <= body * 0.05)
        patterns["bearish_marubozu"] = (last["close"] < last["open"]) and (upper_wick <= body * 0.05) and (lower_wick <= body * 0.05)
        
        return patterns
    
    @staticmethod
    def _detect_two_candle(df: pd.DataFrame) -> Dict[str, bool]:
        """Двухсвечные паттерны"""
        if len(df) < 2:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        patterns = {}
        
        # Бычье поглощение (Bullish Engulfing)
        patterns["bullish_engulf"] = (prev["close"] < prev["open"]) and (last["close"] > last["open"]) and \
                                     (last["open"] < prev["close"]) and (last["close"] > prev["open"])
        
        # Медвежье поглощение (Bearish Engulfing)
        patterns["bearish_engulf"] = (prev["close"] > prev["open"]) and (last["close"] < last["open"]) and \
                                     (last["open"] > prev["close"]) and (last["close"] < prev["open"])
        
        # Твизз боттом (Tweezer Bottom)
        patterns["tweezer_bottom"] = (prev["low"] == last["low"]) and (prev["close"] < prev["open"]) and (last["close"] > last["open"])
        
        # Твизз топ (Tweezer Top)
        patterns["tweezer_top"] = (prev["high"] == last["high"]) and (prev["close"] > prev["open"]) and (last["close"] < last["open"])
        
        return patterns
    
    @staticmethod
    def _detect_three_candle(df: pd.DataFrame) -> Dict[str, bool]:
        """Трехсвечные паттерны"""
        if len(df) < 3:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        patterns = {}
        
        # Утренняя звезда (Morning Star)
        patterns["morning_star"] = (prev2["close"] < prev2["open"]) and \
                                   (abs(prev["close"] - prev["open"]) <= (prev["high"] - prev["low"]) * 0.3) and \
                                   (last["close"] > last["open"]) and \
                                   (last["close"] > (prev2["open"] + prev2["close"]) / 2)
        
        # Вечерняя звезда (Evening Star)
        patterns["evening_star"] = (prev2["close"] > prev2["open"]) and \
                                   (abs(prev["close"] - prev["open"]) <= (prev["high"] - prev["low"]) * 0.3) and \
                                   (last["close"] < last["open"]) and \
                                   (last["close"] < (prev2["open"] + prev2["close"]) / 2)
        
        # Три белых солдата (Three White Soldiers)
        patterns["three_soldiers"] = (df.iloc[-3]["close"] > df.iloc[-3]["open"]) and \
                                     (df.iloc[-2]["close"] > df.iloc[-2]["open"]) and \
                                     (df.iloc[-1]["close"] > df.iloc[-1]["open"]) and \
                                     (df.iloc[-2]["close"] > df.iloc[-3]["close"]) and \
                                     (df.iloc[-1]["close"] > df.iloc[-2]["close"]) and \
                                     (df.iloc[-2]["open"] > df.iloc[-3]["open"]) and \
                                     (df.iloc[-1]["open"] > df.iloc[-2]["open"])
        
        # Три черных вороны (Three Black Crows)
        patterns["three_crows"] = (df.iloc[-3]["close"] < df.iloc[-3]["open"]) and \
                                  (df.iloc[-2]["close"] < df.iloc[-2]["open"]) and \
                                  (df.iloc[-1]["close"] < df.iloc[-1]["open"]) and \
                                  (df.iloc[-2]["close"] < df.iloc[-3]["close"]) and \
                                  (df.iloc[-1]["close"] < df.iloc[-2]["close"]) and \
                                  (df.iloc[-2]["open"] < df.iloc[-3]["open"]) and \
                                  (df.iloc[-1]["open"] < df.iloc[-2]["open"])
        
        return patterns
    
    @staticmethod
    def _detect_reversal_patterns(df: pd.DataFrame) -> Dict[str, bool]:
        """Разворотные паттерны"""
        if len(df) < 5:
            return {}
        
        patterns = {}
        
        # Двойное дно (Double Bottom)
        lows = df["low"].tail(20).values
        if len(lows) >= 4:
            first_bottom = min(lows[:len(lows)//2])
            second_bottom = min(lows[len(lows)//2:])
            middle_high = max(df["high"].tail(20).iloc[len(lows)//2 - 2:len(lows)//2 + 2])
            
            patterns["double_bottom"] = (abs(first_bottom - second_bottom) / first_bottom < 0.02) and \
                                        (df["close"].iloc[-1] > middle_high)
        
        # Двойная вершина (Double Top)
        highs = df["high"].tail(20).values
        if len(highs) >= 4:
            first_top = max(highs[:len(highs)//2])
            second_top = max(highs[len(highs)//2:])
            middle_low = min(df["low"].tail(20).iloc[len(highs)//2 - 2:len(highs)//2 + 2])
            
            patterns["double_top"] = (abs(first_top - second_top) / first_top < 0.02) and \
                                     (df["close"].iloc[-1] < middle_low)
        
        return patterns
    
    @staticmethod
    def _detect_continuation_patterns(df: pd.DataFrame) -> Dict[str, bool]:
        """Паттерны продолжения тренда"""
        if len(df) < 3:
            return {}
        
        patterns = {}
        
        # Бычий флаг (Bull Flag) - упрощенный
        prev_high = max(df["high"].iloc[-6:-3])
        prev_low = min(df["low"].iloc[-6:-3])
        curr_high = max(df["high"].iloc[-3:])
        curr_low = min(df["low"].iloc[-3:])
        
        patterns["bull_flag"] = (df["close"].iloc[-1] > df["open"].iloc[-1]) and \
                                (curr_high < prev_high) and (curr_low > prev_low) and \
                                (df["close"].iloc[-1] > df["ema21"].iloc[-1])
        
        # Медвежий флаг (Bear Flag)
        patterns["bear_flag"] = (df["close"].iloc[-1] < df["open"].iloc[-1]) and \
                                (curr_high < prev_high) and (curr_low > prev_low) and \
                                (df["close"].iloc[-1] < df["ema21"].iloc[-1])
        
        return patterns
    
    @staticmethod
    def _detect_harami(df: pd.DataFrame) -> Dict[str, bool]:
        """Harami паттерны"""
        if len(df) < 2:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        patterns = {}
        
        # Бычий Harami
        patterns["bullish_harami"] = (prev["close"] < prev["open"]) and \
                                     (last["close"] > last["open"]) and \
                                     (last["high"] < prev["open"]) and \
                                     (last["low"] > prev["close"])
        
        # Медвежий Harami
        patterns["bearish_harami"] = (prev["close"] > prev["open"]) and \
                                     (last["close"] < last["open"]) and \
                                     (last["high"] < prev["close"]) and \
                                     (last["low"] > prev["open"])
        
        return patterns
    
    @staticmethod
    def _detect_piercing(df: pd.DataFrame) -> Dict[str, bool]:
        """Piercing Line паттерн"""
        if len(df) < 2:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        patterns = {}
        
        # Piercing Line
        patterns["piercing_line"] = (prev["close"] < prev["open"]) and \
                                    (last["close"] > last["open"]) and \
                                    (last["open"] < prev["close"]) and \
                                    (last["close"] > (prev["open"] + prev["close"]) / 2)
        
        return patterns
    
    @staticmethod
    def _detect_dark_cloud(df: pd.DataFrame) -> Dict[str, bool]:
        """Dark Cloud Cover паттерн"""
        if len(df) < 2:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        patterns = {}
        
        # Dark Cloud Cover
        patterns["dark_cloud"] = (prev["close"] > prev["open"]) and \
                                 (last["close"] < last["open"]) and \
                                 (last["open"] > prev["close"]) and \
                                 (last["close"] < (prev["open"] + prev["close"]) / 2)
        
        return patterns
    
    @staticmethod
    def _detect_kicker(df: pd.DataFrame) -> Dict[str, bool]:
        """Kicker Signal паттерн"""
        if len(df) < 2:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        patterns = {}
        
        # Бычий Kicker
        patterns["bullish_kicker"] = (prev["close"] < prev["open"]) and \
                                     (last["close"] > last["open"]) and \
                                     (last["open"] > prev["close"])
        
        # Медвежий Kicker
        patterns["bearish_kicker"] = (prev["close"] > prev["open"]) and \
                                     (last["close"] < last["open"]) and \
                                     (last["open"] < prev["close"])
        
        return patterns
    
    @staticmethod
    def _detect_three_inside(df: pd.DataFrame) -> Dict[str, bool]:
        """Three Inside паттерны"""
        if len(df) < 3:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        patterns = {}
        
        # Three Inside Up
        patterns["three_inside_up"] = (prev2["close"] < prev2["open"]) and \
                                      (prev["close"] > prev["open"]) and \
                                      (prev["high"] < prev2["open"]) and \
                                      (prev["low"] > prev2["close"]) and \
                                      (last["close"] > last["open"]) and \
                                      (last["close"] > prev2["open"])
        
        # Three Inside Down
        patterns["three_inside_down"] = (prev2["close"] > prev2["open"]) and \
                                        (prev["close"] < prev["open"]) and \
                                        (prev["high"] < prev2["close"]) and \
                                        (prev["low"] > prev2["open"]) and \
                                        (last["close"] < last["open"]) and \
                                        (last["close"] < prev2["close"])
        
        return patterns
    
    @staticmethod
    def _detect_three_outside(df: pd.DataFrame) -> Dict[str, bool]:
        """Three Outside паттерны"""
        if len(df) < 3:
            return {}
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        prev2 = df.iloc[-3]
        
        patterns = {}
        
        # Three Outside Up
        patterns["three_outside_up"] = (prev2["close"] < prev2["open"]) and \
                                       (prev["close"] > prev["open"]) and \
                                       (prev["open"] < prev2["close"]) and \
                                       (prev["close"] > prev2["open"]) and \
                                       (last["close"] > last["open"]) and \
                                       (last["close"] > prev["high"])
        
        # Three Outside Down
        patterns["three_outside_down"] = (prev2["close"] > prev2["open"]) and \
                                         (prev["close"] < prev["open"]) and \
                                         (prev["open"] > prev2["close"]) and \
                                         (prev["close"] < prev2["open"]) and \
                                         (last["close"] < last["open"]) and \
                                         (last["close"] < prev["low"])
        
        return patterns


class MultiTimeframeAnalyzer:
    """Расширенный мульти-таймфрейм анализ для 1ч, 2ч, 4ч"""
    
    @staticmethod
    async def analyze(fetcher: DataFetcher, symbol: str) -> Dict:
        """Анализирует тренды на разных таймфреймах с детальными метриками"""
        
        tf_data = {}
        
        for tf in TIMEFRAMES:
            df = await fetcher.get_klines(symbol, tf, 150)
            if df.empty or len(df) < 50:
                tf_data[tf] = {
                    "trend": "NEUTRAL",
                    "strength": 0,
                    "momentum": 0,
                    "adx": 0,
                    "rsi": 50
                }
                continue
            
            # Определяем тренд с несколькими индикаторами
            ema8 = df["close"].ewm(span=8, adjust=False).mean()
            ema21 = df["close"].ewm(span=21, adjust=False).mean()
            ema50 = df["close"].ewm(span=50, adjust=False).mean()
            ema200 = df["close"].ewm(span=200, adjust=False).mean()
            
            # MACD тренд
            macd = df["close"].ewm(span=12, adjust=False).mean() - df["close"].ewm(span=26, adjust=False).mean()
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            macd_trend = 1 if macd.iloc[-1] > macd_signal.iloc[-1] else -1
            
            # ADX для силы тренда
            adx = AdvancedIndicators._calc_adx(df["high"], df["low"], df["close"], 14)
            adx_value = adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 25
            
            # RSI для импульса
            rsi = AdvancedIndicators._calc_rsi(df["close"], 14).iloc[-1]
            
            # Определяем направление тренда
            bullish_score = 0
            bearish_score = 0
            
            # EMA условия
            if ema8.iloc[-1] > ema21.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            if ema21.iloc[-1] > ema50.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            if ema50.iloc[-1] > ema200.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # Цена относительно MA
            if df["close"].iloc[-1] > ema21.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # MACD
            if macd_trend == 1:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # RSI
            if rsi > 50:
                bullish_score += 0.5
            elif rsi < 50:
                bearish_score += 0.5
            
            # ADX направление
            di_plus = AdvancedIndicators._calc_di_plus(df["high"], df["low"], df["close"], 14)
            di_minus = AdvancedIndicators._calc_di_minus(df["high"], df["low"], df["close"], 14)
            if di_plus.iloc[-1] > di_minus.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
            
            # Определяем тренд
            if bullish_score > bearish_score + 1.5:
                trend = "BULLISH"
            elif bearish_score > bullish_score + 1.5:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
            
            # Сила тренда
            strength = abs(bullish_score - bearish_score) / 6.5
            
            # Импульс
            momentum = (df["close"].iloc[-1] - df["close"].iloc[-6]) / df["close"].iloc[-6] * 100 if len(df) >= 6 else 0
            
            tf_data[tf] = {
                "trend": trend,
                "strength": strength,
                "momentum": momentum,
                "adx": adx_value,
                "rsi": rsi,
                "bullish_score": bullish_score,
                "bearish_score": bearish_score
            }
        
        # Расчет согласованности таймфреймов
        bullish_count = sum(1 for v in tf_data.values() if v["trend"] == "BULLISH")
        bearish_count = sum(1 for v in tf_data.values() if v["trend"] == "BEARISH")
        total_tfs = len(TIMEFRAMES)
        
        # Взвешенное большинство (4ч важнее)
        weighted_score = 0
        for tf in TIMEFRAMES:
            weight = 3 if tf == "240" else 2 if tf == "120" else 1
            if tf_data[tf]["trend"] == "BULLISH":
                weighted_score += weight
            elif tf_data[tf]["trend"] == "BEARISH":
                weighted_score -= weight
        
        majority = "LONG" if weighted_score > 0 else "SHORT" if weighted_score < 0 else "NEUTRAL"
        
        # Определяем лучший таймфрейм для входа
        best_tf = max(TIMEFRAMES, key=lambda x: tf_data[x]["strength"])
        
        return {
            "1h": tf_data.get("60", {}),
            "2h": tf_data.get("120", {}),
            "4h": tf_data.get("240", {}),
            "majority": majority,
            "strength": max(bullish_count, bearish_count) / total_tfs,
            "weighted_score": weighted_score,
            "best_tf": best_tf,
            "consensus": "HIGH" if bullish_count == total_tfs or bearish_count == total_tfs else \
                        "MEDIUM" if max(bullish_count, bearish_count) >= total_tfs - 1 else "LOW"
        }


class SignalGenerator:
    """Улучшенная генерация сигналов по 35+ стратегиям"""
    
    def __init__(self, df: pd.DataFrame, patterns: Dict, mtf: Dict, symbol: str):
        self.df = df
        self.last = df.iloc[-1]
        self.prev = df.iloc[-2]
        self.prev2 = df.iloc[-3] if len(df) > 2 else df.iloc[-1]
        self.prev3 = df.iloc[-4] if len(df) > 3 else df.iloc[-1]
        self.patterns = patterns
        self.mtf = mtf
        self.symbol = symbol
        self.signal_weights = {}
    
    def generate_all_signals(self) -> List[Dict]:
        """Генерирует все возможные сигналы"""
        signals = []
        
        # ===== 1. RSI СТРАТЕГИИ (расширенные) =====
        signals.extend(self._rsi_signals_enhanced())
        
        # ===== 2. MACD СТРАТЕГИИ =====
        signals.extend(self._macd_signals_enhanced())
        
        # ===== 3. BOLLINGER BANDS =====
        signals.extend(self._bollinger_signals_enhanced())
        
        # ===== 4. EMA КРОССОВЕРЫ =====
        signals.extend(self._ema_signals_enhanced())
        
        # ===== 5. СВЕЧНЫЕ ПАТТЕРНЫ =====
        signals.extend(self._candle_signals_enhanced())
        
        # ===== 6. STOCHASTIC =====
        signals.extend(self._stochastic_signals_enhanced())
        
        # ===== 7. ОБЪЕМНЫЕ СТРАТЕГИИ =====
        signals.extend(self._volume_signals_enhanced())
        
        # ===== 8. TREND (ADX + DMI) =====
        signals.extend(self._trend_signals_enhanced())
        
        # ===== 9. ДИВЕРГЕНЦИИ =====
        signals.extend(self._divergence_signals_enhanced())
        
        # ===== 10. SUPERSTRATEGY (комбинации) =====
        signals.extend(self._super_strategies())
        
        # ===== 11. KELTNER CHANNELS =====
        signals.extend(self._keltner_signals_enhanced())
        
        # ===== 12. DONCHIAN CHANNELS =====
        signals.extend(self._donchian_signals())
        
        # ===== 13. VORTEX INDICATOR =====
        signals.extend(self._vortex_signals())
        
        # ===== 14. ULTIMATE OSCILLATOR =====
        signals.extend(self._ultimate_osc_signals())
        
        # ===== 15. CHAIKIN MONEY FLOW =====
        signals.extend(self._cmf_signals())
        
        # ===== 16. STOCHASTIC RSI =====
        signals.extend(self._stoch_rsi_signals())
        
        # ===== 17. SUPER TREND =====
        signals.extend(self._supertrend_signals())
        
        # ===== 18. VWAP STRATEGIES =====
        signals.extend(self._vwap_signals_enhanced())
        
        # ===== 19. FIBONACCI RETRACEMENT =====
        signals.extend(self._fibonacci_signals())
        
        # ===== 20. ELDER'S FORCE INDEX =====
        signals.extend(self._force_index_signals())
        
        # ===== 21. CHOPPINESS INDEX =====
        signals.extend(self._choppiness_signals())
        
        # ===== 22. WILLIAMS %R =====
        signals.extend(self._williams_signals_enhanced())
        
        # ===== 23. MFI =====
        signals.extend(self._mfi_signals_enhanced())
        
        # ===== 24. CCI =====
        signals.extend(self._cci_signals_enhanced())
        
        # ===== 25. MTF ПОДТВЕРЖДЕНИЕ =====
        signals.extend(self._mtf_signals_enhanced())
        
        # ===== 26. AI-LIKE ENSEMBLE SIGNALS =====
        signals.extend(self._ensemble_signals())
        
        # Фильтрация и сортировка
        valid = [s for s in signals if s and s["confidence"] >= MIN_CONFIDENCE_SCORE]
        
        # Удаляем дубликаты по направлению и стратегии
        unique_signals = {}
        for s in valid:
            key = f"{s['symbol']}_{s['direction']}_{s['strategy'].split('_')[0]}"
            if key not in unique_signals or unique_signals[key]["confidence"] < s["confidence"]:
                unique_signals[key] = s
        
        # Сортировка по уверенности
        sorted_signals = sorted(unique_signals.values(), key=lambda x: (-x["confidence"], -x["rr_ratio"]))
        
        # Применяем корреляционный фильтр
        if USE_AI_FILTER:
            sorted_signals = self._apply_correlation_filter(sorted_signals)
        
        return sorted_signals
    
    def _apply_correlation_filter(self, signals: List[Dict]) -> List[Dict]:
        """Фильтр для удаления высококоррелированных сигналов"""
        if len(signals) <= 1:
            return signals
        
        filtered = []
        for sig in signals:
            correlated = False
            for existing in filtered:
                # Проверяем корреляцию по символу и направлению
                if sig["symbol"] == existing["symbol"] and sig["direction"] == existing["direction"]:
                    # Если стратегии похожи, оставляем только одну с высшей уверенностью
                    if self._is_similar_strategy(sig["strategy"], existing["strategy"]):
                        correlated = True
                        break
            if not correlated:
                filtered.append(sig)
        
        return filtered[:MAX_DAILY_TRADES]
    
    def _is_similar_strategy(self, strat1: str, strat2: str) -> bool:
        """Проверяет похожесть стратегий"""
        similar_groups = [
            ["RSI", "Stoch", "Williams", "MFI", "CCI"],
            ["MACD", "MACD_hist", "MACD_cross"],
            ["BB", "Bollinger", "Keltner"],
            ["Divergence", "RSI_divergence", "MACD_divergence"],
            ["SuperTrend", "ADX", "Vortex"]
        ]
        
        for group in similar_groups:
            if any(g in strat1 for g in group) and any(g in strat2 for g in group):
                return True
        return False
    
    # ==================== РАСШИРЕННЫЕ МЕТОДЫ СИГНАЛОВ ====================
    
    def _rsi_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # RSI 14 классический
        rsi14 = self.last["rsi14"]
        prev_rsi14 = self.prev["rsi14"]
        
        # Выход из перепроданности
        if prev_rsi14 <= 30 and rsi14 > 30:
            conf = 80
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.mtf["majority"] == "LONG":
                conf += 5
            signals.append(self._create_signal("LONG", "RSI_exit_oversold",
                f"RSI14 вышел из зоны перепроданности: {rsi14:.1f} -> {rsi14:.1f}", conf))
        
        # Выход из перекупленности
        elif prev_rsi14 >= 70 and rsi14 < 70:
            conf = 80
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.mtf["majority"] == "SHORT":
                conf += 5
            signals.append(self._create_signal("SHORT", "RSI_exit_overbought",
                f"RSI14 вышел из зоны перекупленности: {rsi14:.1f} -> {rsi14:.1f}", conf))
        
        # RSI дивергенция усилена
        if self.last["rsi_divergence"] == -1:
            conf = 90
            if self.last["volume_ratio"] > 1.3:
                conf += 5
            signals.append(self._create_signal("LONG", "RSI_divergence_bull_strong",
                f"Бычья дивергенция RSI14 на {self.mtf['best_tf']}м", conf))
        elif self.last["rsi_divergence"] == 1:
            conf = 90
            if self.last["volume_ratio"] > 1.3:
                conf += 5
            signals.append(self._create_signal("SHORT", "RSI_divergence_bear_strong",
                f"Медвежья дивергенция RSI14 на {self.mtf['best_tf']}м", conf))
        
        # RSI 7 быстрый с подтверждением
        if self.last["rsi7"] < 25 and self.last["rsi21"] < 30:
            signals.append(self._create_signal("LONG", "RSI_multi_oversold",
                f"Мульти-таймфрейм RSI перепродан (7:{self.last['rsi7']:.0f},21:{self.last['rsi21']:.0f})", 80))
        elif self.last["rsi7"] > 75 and self.last["rsi21"] > 70:
            signals.append(self._create_signal("SHORT", "RSI_multi_overbought",
                f"Мульти-таймфрейм RSI перекуплен (7:{self.last['rsi7']:.0f},21:{self.last['rsi21']:.0f})", 80))
        
        # RSI тренд
        if self.last["rsi14"] > 50 and self.prev["rsi14"] <= 50:
            signals.append(self._create_signal("LONG", "RSI_above_50",
                f"RSI14 поднялся выше 50 ({self.last['rsi14']:.1f})", 75))
        elif self.last["rsi14"] < 50 and self.prev["rsi14"] >= 50:
            signals.append(self._create_signal("SHORT", "RSI_below_50",
                f"RSI14 опустился ниже 50 ({self.last['rsi14']:.1f})", 75))
        
        return signals
    
    def _macd_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # MACD пересечение с подтверждением
        if self.prev["macd"] <= self.prev["macd_signal"] and self.last["macd"] > self.last["macd_signal"]:
            conf = 85
            if self.last["macd_hist"] > 0:
                conf += 5
            if self.last["volume_ratio"] > 1.2:
                conf += 5
            if self.last["macd_divergence"] == -1:
                conf += 5
            
            signals.append(self._create_signal("LONG", "MACD_golden_cross",
                f"MACD золотой крест (Hist: {self.last['macd_hist']:.2e})", conf))
        
        elif self.prev["macd"] >= self.prev["macd_signal"] and self.last["macd"] < self.last["macd_signal"]:
            conf = 85
            if self.last["macd_hist"] < 0:
                conf += 5
            if self.last["volume_ratio"] > 1.2:
                conf += 5
            if self.last["macd_divergence"] == 1:
                conf += 5
            
            signals.append(self._create_signal("SHORT", "MACD_death_cross",
                f"MACD крест смерти (Hist: {self.last['macd_hist']:.2e})", conf))
        
        # Быстрый MACD
        if self.prev["macd_fast"] <= self.prev["macd_signal_fast"] and self.last["macd_fast"] > self.last["macd_signal_fast"]:
            signals.append(self._create_signal("LONG", "MACD_fast_cross",
                "Быстрый MACD дал сигнал вверх", 80))
        elif self.prev["macd_fast"] >= self.prev["macd_signal_fast"] and self.last["macd_fast"] < self.last["macd_signal_fast"]:
            signals.append(self._create_signal("SHORT", "MACD_fast_cross",
                "Быстрый MACD дал сигнал вниз", 80))
        
        # Гистограмма MACD разворачивается после экстремума
        if self.last["macd_hist_direction"] == 1 and self.prev["macd_hist_direction"] == -1 and self.last["macd_hist"] < 0:
            signals.append(self._create_signal("LONG", "MACD_hist_bottom",
                "Гистограмма MACD развернулась вверх от минимума", 85))
        elif self.last["macd_hist_direction"] == -1 and self.prev["macd_hist_direction"] == 1 and self.last["macd_hist"] > 0:
            signals.append(self._create_signal("SHORT", "MACD_hist_top",
                "Гистограмма MACD развернулась вниз от максимума", 85))
        
        return signals
    
    def _bollinger_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Отскок от полос с объемом
        if self.last["close"] < self.last["bb_lower_20_2"] and self.last["close"] > self.prev["close"]:
            conf = 85
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.last["bb_width"] > 0.08:
                conf += 5
            signals.append(self._create_signal("LONG", "BB_oversold_bounce",
                f"Отскок от нижней полосы BB (ширина: {self.last['bb_width']:.3f})", conf))
        
        elif self.last["close"] > self.last["bb_upper_20_2"] and self.last["close"] < self.prev["close"]:
            conf = 85
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.last["bb_width"] > 0.08:
                conf += 5
            signals.append(self._create_signal("SHORT", "BB_overbought_bounce",
                f"Отскок от верхней полосы BB (ширина: {self.last['bb_width']:.3f})", conf))
        
        # BB Squeeze breakout
        if self.last["bb_width"] < 0.05 and self.last["bb_width"] > self.prev["bb_width"]:
            # Определяем направление пробоя
            if self.last["close"] > self.last["bb_middle_20"]:
                signals.append(self._create_signal("LONG", "BB_squeeze_up",
                    f"Сжатие BB с пробоем вверх (ширина: {self.last['bb_width']:.3f})", 80))
            elif self.last["close"] < self.last["bb_middle_20"]:
                signals.append(self._create_signal("SHORT", "BB_squeeze_down",
                    f"Сжатие BB с пробоем вниз (ширина: {self.last['bb_width']:.3f})", 80))
        
        # BB положение 0-1 экстремумы
        if self.last["bb_position"] < 0.05:
            signals.append(self._create_signal("LONG", "BB_extreme_low",
                f"Цена на нижней границе BB (поз: {self.last['bb_position']:.3f})", 75))
        elif self.last["bb_position"] > 0.95:
            signals.append(self._create_signal("SHORT", "BB_extreme_high",
                f"Цена на верхней границе BB (поз: {self.last['bb_position']:.3f})", 75))
        
        return signals
    
    def _ema_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Золотой/смертельный крест
        if self.prev["ema21"] <= self.prev["ema50"] and self.last["ema21"] > self.last["ema50"]:
            conf = 85
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.mtf["majority"] == "LONG":
                conf += 5
            signals.append(self._create_signal("LONG", "EMA_golden_cross",
                f"Золотой крест: EMA21 выше EMA50 (объем: x{self.last['volume_ratio']:.1f})", conf))
        
        elif self.prev["ema21"] >= self.prev["ema50"] and self.last["ema21"] < self.last["ema50"]:
            conf = 85
            if self.last["volume_ratio"] > 1.5:
                conf += 5
            if self.mtf["majority"] == "SHORT":
                conf += 5
            signals.append(self._create_signal("SHORT", "EMA_death_cross",
                f"Смертельный крест: EMA21 ниже EMA50 (объем: x{self.last['volume_ratio']:.1f})", conf))
        
        # EMA 8/21 кроссовер
        if self.prev["ema8"] <= self.prev["ema21"] and self.last["ema8"] > self.last["ema21"]:
            signals.append(self._create_signal("LONG", "EMA8_21_cross_up",
                "Быстрый EMA8 пересек EMA21 вверх", 75))
        elif self.prev["ema8"] >= self.prev["ema21"] and self.last["ema8"] < self.last["ema21"]:
            signals.append(self._create_signal("SHORT", "EMA8_21_cross_down",
                "Быстрый EMA8 пересек EMA21 вниз", 75))
        
        # HMA направление
        hma_dir = self.last["hma"] - self.prev["hma"]
        if hma_dir > 0 and self.prev["hma"] - self.prev2["hma"] <= 0:
            signals.append(self._create_signal("LONG", "HMA_reversal_up",
                "HMA (Hull MA) развернулся вверх", 80))
        elif hma_dir < 0 and self.prev["hma"] - self.prev2["hma"] >= 0:
            signals.append(self._create_signal("SHORT", "HMA_reversal_down",
                "HMA (Hull MA) развернулся вниз", 80))
        
        return signals
    
    def _candle_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Высоко-уверенные паттерны
        high_confidence = {
            "bullish_engulf": ("LONG", 95, "Бычье поглощение - очень сильный сигнал"),
            "bearish_engulf": ("SHORT", 95, "Медвежье поглощение - очень сильный сигнал"),
            "three_soldiers": ("LONG", 90, "Три белых солдата - сильный бычий тренд"),
            "three_crows": ("SHORT", 90, "Три черных вороны - сильный медвежий тренд"),
            "morning_star": ("LONG", 88, "Утренняя звезда - разворот вверх"),
            "evening_star": ("SHORT", 88, "Вечерняя звезда - разворот вниз"),
            "piercing_line": ("LONG", 85, "Piercing Line - бычий разворот"),
            "dark_cloud": ("SHORT", 85, "Dark Cloud Cover - медвежий разворот"),
            "bullish_kicker": ("LONG", 90, "Бычий Kicker - сильный разворот"),
            "bearish_kicker": ("SHORT", 90, "Медвежий Kicker - сильный разворот"),
            "three_inside_up": ("LONG", 85, "Three Inside Up - подтвержденный бычий разворот"),
            "three_inside_down": ("SHORT", 85, "Three Inside Down - подтвержденный медвежий разворот"),
            "hammer": ("LONG", 85, "Молот - разворот вверх"),
            "hanging_man": ("SHORT", 80, "Повешенный - разворот вниз"),
            "shooting_star": ("SHORT", 85, "Падающая звезда - разворот вниз"),
            "inverted_hammer": ("LONG", 80, "Перевернутый молот - разворот вверх"),
            "bullish_harami": ("LONG", 75, "Бычий Harami"),
            "bearish_harami": ("SHORT", 75, "Медвежий Harami")
        }
        
        for pattern_name, (direction, base_conf, reason) in high_confidence.items():
            if self.patterns.get(pattern_name):
                conf = base_conf
                if self.last["volume_ratio"] > 1.5:
                    conf = min(100, conf + 5)
                if direction == "LONG" and self.mtf["majority"] == "LONG":
                    conf = min(100, conf + 5)
                elif direction == "SHORT" and self.mtf["majority"] == "SHORT":
                    conf = min(100, conf + 5)
                signals.append(self._create_signal(direction, pattern_name, reason, conf))
        
        # Двойное дно/вершина
        if self.patterns.get("double_bottom"):
            signals.append(self._create_signal("LONG", "DoubleBottom",
                "Двойное дно - сильный разворотной паттерн", 90))
        if self.patterns.get("double_top"):
            signals.append(self._create_signal("SHORT", "DoubleTop",
                "Двойная вершина - сильный разворотной паттерн", 90))
        
        # Флаги
        if self.patterns.get("bull_flag"):
            signals.append(self._create_signal("LONG", "BullFlag",
                "Бычий флаг - паттерн продолжения тренда", 80))
        if self.patterns.get("bear_flag"):
            signals.append(self._create_signal("SHORT", "BearFlag",
                "Медвежий флаг - паттерн продолжения тренда", 80))
        
        return signals
    
    def _stochastic_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Быстрый Stochastic
        k_fast = self.last["stoch_k_5"]
        d_fast = self.last["stoch_d_5"]
        
        # Выход из перепроданности
        if k_fast < 20 and k_fast > d_fast:
            signals.append(self._create_signal("LONG", "Stoch_fast_oversold",
                f"Быстрый Stochastic K={k_fast:.1f} вышел из перепроданности", 75))
        elif k_fast > 80 and k_fast < d_fast:
            signals.append(self._create_signal("SHORT", "Stoch_fast_overbought",
                f"Быстрый Stochastic K={k_fast:.1f} вышел из перекупленности", 75))
        
        # Медленный Stochastic (14)
        k_slow = self.last["stoch_k_14"]
        d_slow = self.last["stoch_d_14"]
        
        if k_slow < 20 and k_slow > d_slow:
            conf = 80
            if self.last["volume_ratio"] > 1.3:
                conf += 5
            signals.append(self._create_signal("LONG", "Stoch_slow_oversold",
                f"Медленный Stochastic K={k_slow:.1f} вышел из перепроданности", conf))
        elif k_slow > 80 and k_slow < d_slow:
            conf = 80
            if self.last["volume_ratio"] > 1.3:
                conf += 5
            signals.append(self._create_signal("SHORT", "Stoch_slow_overbought",
                f"Медленный Stochastic K={k_slow:.1f} вышел из перекупленности", conf))
        
        # Stochastic Divergence
        if self.last["stoch_divergence"] == -1:
            signals.append(self._create_signal("LONG", "Stoch_divergence_bull",
                "Бычья дивергенция Stochastic", 85))
        elif self.last["stoch_divergence"] == 1:
            signals.append(self._create_signal("SHORT", "Stoch_divergence_bear",
                "Медвежья дивергенция Stochastic", 85))
        
        return signals
    
    def _volume_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Экстремальный объем
        if self.last["volume_ratio"] > 2.0:
            if self.last["close"] > self.last["open"]:
                conf = 85
                if self.last["volume_ratio"] > 3.0:
                    conf = 90
                signals.append(self._create_signal("LONG", "Volume_explosion_up",
                    f"Взрывной объем x{self.last['volume_ratio']:.1f} на бычьей свече", conf))
            elif self.last["close"] < self.last["open"]:
                conf = 85
                if self.last["volume_ratio"] > 3.0:
                    conf = 90
                signals.append(self._create_signal("SHORT", "Volume_explosion_down",
                    f"Взрывной объем x{self.last['volume_ratio']:.1f} на медвежьей свече", conf))
        
        # OBV подтверждение
        if self.last["obv_trend"] == 1 and self.last["close"] > self.last["ema21"] and self.prev["close"] <= self.prev["ema21"]:
            signals.append(self._create_signal("LONG", "OBV_confirmation",
                "OBV подтвердил восходящий тренд", 80))
        elif self.last["obv_trend"] == -1 and self.last["close"] < self.last["ema21"] and self.prev["close"] >= self.prev["ema21"]:
            signals.append(self._create_signal("SHORT", "OBV_confirmation",
                "OBV подтвердил нисходящий тренд", 80))
        
        # CMF (Chaikin Money Flow)
        if self.last["cmf"] > 0.1 and self.prev["cmf"] <= 0.1:
            signals.append(self._create_signal("LONG", "CMF_positive",
                f"Chaikin Money Flow положительный ({self.last['cmf']:.3f})", 75))
        elif self.last["cmf"] < -0.1 and self.prev["cmf"] >= -0.1:
            signals.append(self._create_signal("SHORT", "CMF_negative",
                f"Chaikin Money Flow отрицательный ({self.last['cmf']:.3f})", 75))
        
        # Volume Profile
        if self.last["vp_ratio"] > 1.5:
            signals.append(self._create_signal("LONG", "Volume_profile_bull",
                f"Объемный профиль показывает накопление (ratio: {self.last['vp_ratio']:.2f})", 70))
        elif self.last["vp_ratio"] < 0.67:
            signals.append(self._create_signal("SHORT", "Volume_profile_bear",
                f"Объемный профиль показывает распределение (ratio: {self.last['vp_ratio']:.2f})", 70))
        
        return signals
    
    def _trend_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # ADX сильный тренд с направлением
        if self.last["adx14"] > 25:
            if self.last["di_plus"] > self.last["di_minus"]:
                conf = 80
                if self.last["adx14"] > 35:
                    conf = 85
                if self.last["adx14"] > 45:
                    conf = 90
                signals.append(self._create_signal("LONG", "ADX_strong_up",
                    f"Сильный восходящий тренд (ADX={self.last['adx14']:.1f}, DMI+={self.last['di_plus']:.1f})", conf))
            elif self.last["di_minus"] > self.last["di_plus"]:
                conf = 80
                if self.last["adx14"] > 35:
                    conf = 85
                if self.last["adx14"] > 45:
                    conf = 90
                signals.append(self._create_signal("SHORT", "ADX_strong_down",
                    f"Сильный нисходящий тренд (ADX={self.last['adx14']:.1f}, DMI-={self.last['di_minus']:.1f})", conf))
        
        # ADX пересечение
        if self.prev["di_plus"] <= self.prev["di_minus"] and self.last["di_plus"] > self.last["di_minus"]:
            signals.append(self._create_signal("LONG", "DMI_cross_up",
                f"DMI+ пересек DMI- вверх (ADX={self.last['adx14']:.1f})", 80))
        elif self.prev["di_plus"] >= self.prev["di_minus"] and self.last["di_plus"] < self.last["di_minus"]:
            signals.append(self._create_signal("SHORT", "DMI_cross_down",
                f"DMI- пересек DMI+ вниз (ADX={self.last['adx14']:.1f})", 80))
        
        # ADX растет
        if self.last["adx14"] > self.prev["adx14"] and self.last["adx14"] > 20:
            if self.last["di_plus"] > self.last["di_minus"]:
                signals.append(self._create_signal("LONG", "ADX_growing_up",
                    f"ADX растет, тренд усиливается ({self.last['adx14']:.1f} -> {self.last['adx14']:.1f})", 75))
            elif self.last["di_minus"] > self.last["di_plus"]:
                signals.append(self._create_signal("SHORT", "ADX_growing_down",
                    f"ADX растет, тренд усиливается ({self.prev['adx14']:.1f} -> {self.last['adx14']:.1f})", 75))
        
        return signals
    
    def _divergence_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Множественные дивергенции - самые сильные сигналы
        div_count_bull = 0
        div_count_bear = 0
        
        if self.last["rsi_divergence"] == -1:
            div_count_bull += 1
        if self.last["macd_divergence"] == -1:
            div_count_bull += 1
        if self.last["obv_divergence"] == -1:
            div_count_bull += 1
        if self.last["mfi_divergence"] == -1:
            div_count_bull += 1
        if self.last["stoch_divergence"] == -1:
            div_count_bull += 1
        
        if self.last["rsi_divergence"] == 1:
            div_count_bear += 1
        if self.last["macd_divergence"] == 1:
            div_count_bear += 1
        if self.last["obv_divergence"] == 1:
            div_count_bear += 1
        if self.last["mfi_divergence"] == 1:
            div_count_bear += 1
        if self.last["stoch_divergence"] == 1:
            div_count_bear += 1
        
        if div_count_bull >= 3:
            signals.append(self._create_signal("LONG", "Multiple_divergences_bull",
                f"{div_count_bull} индикатора показывают бычью дивергенцию", 95))
        elif div_count_bear >= 3:
            signals.append(self._create_signal("SHORT", "Multiple_divergences_bear",
                f"{div_count_bear} индикаторов показывают медвежью дивергенцию", 95))
        elif div_count_bull >= 2:
            signals.append(self._create_signal("LONG", "Double_divergence_bull",
                f"2 индикатора показывают бычью дивергенцию", 88))
        elif div_count_bear >= 2:
            signals.append(self._create_signal("SHORT", "Double_divergence_bear",
                f"2 индикатора показывают медвежью дивергенцию", 88))
        
        return signals
    
    def _super_strategies(self) -> List[Dict]:
        """Комбинированные стратегии с несколькими подтверждениями"""
        signals = []
        
        # SUPER LONG - несколько условий
        long_conditions = 0
        short_conditions = 0
        
        # RSI
        if self.last["rsi14"] < 35 and self.last["rsi7"] < 30:
            long_conditions += 1
        if self.last["rsi14"] > 65 and self.last["rsi7"] > 70:
            short_conditions += 1
        
        # MACD
        if self.last["macd"] > self.last["macd_signal"] and self.last["macd_hist"] > 0:
            long_conditions += 1
        if self.last["macd"] < self.last["macd_signal"] and self.last["macd_hist"] < 0:
            short_conditions += 1
        
        # BB
        if self.last["close"] < self.last["bb_lower_20_2"]:
            long_conditions += 1
        if self.last["close"] > self.last["bb_upper_20_2"]:
            short_conditions += 1
        
        # Volume
        if self.last["volume_ratio"] > 1.3 and self.last["close"] > self.last["open"]:
            long_conditions += 1
        if self.last["volume_ratio"] > 1.3 and self.last["close"] < self.last["open"]:
            short_conditions += 1
        
        # MTF
        if self.mtf["majority"] == "LONG":
            long_conditions += 1
        elif self.mtf["majority"] == "SHORT":
            short_conditions += 1
        
        # SuperTrend
        if "supertrend_direction" in self.last:
            if self.last["supertrend_direction"] == 1:
                long_conditions += 1
            elif self.last["supertrend_direction"] == -1:
                short_conditions += 1
        
        # VWAP
        if self.last["vwap_zscore"] < -1:
            long_conditions += 1
        if self.last["vwap_zscore"] > 1:
            short_conditions += 1
        
        # Принимаем решение
        if long_conditions >= 5:
            conf = 80 + min(15, (long_conditions - 4) * 3)
            signals.append(self._create_signal("LONG", "SuperStrategy_Bull",
                f"Мощный бычий сигнал ({long_conditions}/8 условий)", min(100, conf)))
        elif short_conditions >= 5:
            conf = 80 + min(15, (short_conditions - 4) * 3)
            signals.append(self._create_signal("SHORT", "SuperStrategy_Bear",
                f"Мощный медвежий сигнал ({short_conditions}/8 условий)", min(100, conf)))
        
        return signals
    
    def _keltner_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Прорыв канала Кельтнера
        if self.prev["close"] <= self.prev["kc_upper_ema20"] and self.last["close"] > self.last["kc_upper_ema20"]:
            if self.last["volume_ratio"] > 1.3:
                signals.append(self._create_signal("LONG", "Keltner_breakout_vol",
                    f"Прорыв Keltner вверх с объемом x{self.last['volume_ratio']:.1f}", 85))
            else:
                signals.append(self._create_signal("LONG", "Keltner_breakout",
                    "Прорыв верхней границы канала Кельтнера", 75))
        
        elif self.prev["close"] >= self.prev["kc_lower_ema20"] and self.last["close"] < self.last["kc_lower_ema20"]:
            if self.last["volume_ratio"] > 1.3:
                signals.append(self._create_signal("SHORT", "Keltner_breakdown_vol",
                    f"Прорыв Keltner вниз с объемом x{self.last['volume_ratio']:.1f}", 85))
            else:
                signals.append(self._create_signal("SHORT", "Keltner_breakdown",
                    "Прорыв нижней границы канала Кельтнера", 75))
        
        return signals
    
    def _donchian_signals(self) -> List[Dict]:
        signals = []
        
        # Прорыв Donchian канала
        if self.prev["close"] <= self.prev["dc_upper_20"] and self.last["close"] > self.last["dc_upper_20"]:
            signals.append(self._create_signal("LONG", "Donchian_breakout",
                f"Прорыв верхней границы Donchian (20-период)", 80))
        elif self.prev["close"] >= self.prev["dc_lower_20"] and self.last["close"] < self.last["dc_lower_20"]:
            signals.append(self._create_signal("SHORT", "Donchian_breakdown",
                f"Прорыв нижней границы Donchian (20-период)", 80))
        
        return signals
    
    def _vortex_signals(self) -> List[Dict]:
        signals = []
        
        if "vortex_plus" in self.last and "vortex_minus" in self.last:
            # Vortex пересечение
            if self.prev["vortex_plus"] <= self.prev["vortex_minus"] and self.last["vortex_plus"] > self.last["vortex_minus"]:
                signals.append(self._create_signal("LONG", "Vortex_cross_up",
                    f"Vortex+ пересек Vortex- вверх (VI+={self.last['vortex_plus']:.3f})", 80))
            elif self.prev["vortex_plus"] >= self.prev["vortex_minus"] and self.last["vortex_plus"] < self.last["vortex_minus"]:
                signals.append(self._create_signal("SHORT", "Vortex_cross_down",
                    f"Vortex- пересек Vortex+ вниз (VI-={self.last['vortex_minus']:.3f})", 80))
            
            # Сильный тренд по Vortex
            if self.last["vortex_plus"] > 1.05 and self.last["vortex_minus"] < 0.95:
                signals.append(self._create_signal("LONG", "Vortex_strong_bull",
                    f"Сильный бычий тренд по Vortex (VI+={self.last['vortex_plus']:.3f})", 75))
            elif self.last["vortex_minus"] > 1.05 and self.last["vortex_plus"] < 0.95:
                signals.append(self._create_signal("SHORT", "Vortex_strong_bear",
                    f"Сильный медвежий тренд по Vortex (VI-={self.last['vortex_minus']:.3f})", 75))
        
        return signals
    
    def _ultimate_osc_signals(self) -> List[Dict]:
        signals = []
        
        if "ultimate_osc" in self.last:
            uo = self.last["ultimate_osc"]
            prev_uo = self.prev["ultimate_osc"]
            
            # Перепроданность/перекупленность
            if prev_uo <= 30 and uo > 30:
                signals.append(self._create_signal("LONG", "UltimateOsc_oversold",
                    f"Ultimate Oscillator вышел из зоны перепроданности ({uo:.1f})", 80))
            elif prev_uo >= 70 and uo < 70:
                signals.append(self._create_signal("SHORT", "UltimateOsc_overbought",
                    f"Ultimate Oscillator вышел из зоны перекупленности ({uo:.1f})", 80))
            
            # Дивергенция упрощенная
            if uo > prev_uo and self.last["close"] < self.prev["close"]:
                signals.append(self._create_signal("LONG", "UltimateOsc_div_bull",
                    "Бычья дивергенция Ultimate Oscillator", 85))
            elif uo < prev_uo and self.last["close"] > self.prev["close"]:
                signals.append(self._create_signal("SHORT", "UltimateOsc_div_bear",
                    "Медвежья дивергенция Ultimate Oscillator", 85))
        
        return signals
    
    def _cmf_signals(self) -> List[Dict]:
        signals = []
        
        if "cmf" in self.last:
            cmf = self.last["cmf"]
            prev_cmf = self.prev["cmf"]
            
            if cmf > 0 and prev_cmf <= 0:
                signals.append(self._create_signal("LONG", "CMF_cross_up",
                    f"Chaikin Money Flow стал положительным ({cmf:.3f})", 80))
            elif cmf < 0 and prev_cmf >= 0:
                signals.append(self._create_signal("SHORT", "CMF_cross_down",
                    f"Chaikin Money Flow стал отрицательным ({cmf:.3f})", 80))
            
            # Экстремальные значения
            if cmf > 0.2:
                signals.append(self._create_signal("LONG", "CMF_high_accumulation",
                    f"Высокое накопление по CMF ({cmf:.3f})", 75))
            elif cmf < -0.2:
                signals.append(self._create_signal("SHORT", "CMF_high_distribution",
                    f"Высокое распределение по CMF ({cmf:.3f})", 75))
        
        return signals
    
    def _stoch_rsi_signals(self) -> List[Dict]:
        signals = []
        
        if "stoch_rsi_k" in self.last:
            k = self.last["stoch_rsi_k"]
            d = self.last["stoch_rsi_d"]
            
            if k < 20 and k > d:
                signals.append(self._create_signal("LONG", "StochRSI_oversold",
                    f"Stochastic RSI K={k:.1f} вышел из перепроданности", 80))
            elif k > 80 and k < d:
                signals.append(self._create_signal("SHORT", "StochRSI_overbought",
                    f"Stochastic RSI K={k:.1f} вышел из перекупленности", 80))
            
            # Кроссовер
            if self.prev["stoch_rsi_k"] <= self.prev["stoch_rsi_d"] and k > d:
                signals.append(self._create_signal("LONG", "StochRSI_cross_up",
                    f"Stochastic RSI дал сигнал вверх (K={k:.1f}, D={d:.1f})", 85))
            elif self.prev["stoch_rsi_k"] >= self.prev["stoch_rsi_d"] and k < d:
                signals.append(self._create_signal("SHORT", "StochRSI_cross_down",
                    f"Stochastic RSI дал сигнал вниз (K={k:.1f}, D={d:.1f})", 85))
        
        return signals
    
    def _supertrend_signals(self) -> List[Dict]:
        signals = []
        
        if "supertrend_direction" in self.last:
            curr_dir = self.last["supertrend_direction"]
            prev_dir = self.prev["supertrend_direction"] if "supertrend_direction" in self.prev else 0
            
            # Смена направления
            if prev_dir != curr_dir:
                if curr_dir == 1:
                    signals.append(self._create_signal("LONG", "SuperTrend_buy",
                        "SuperTrend сменил направление на BUY", 85))
                elif curr_dir == -1:
                    signals.append(self._create_signal("SHORT", "SuperTrend_sell",
                        "SuperTrend сменил направление на SELL", 85))
            
            # Подтверждение тренда
            if curr_dir == 1 and self.mtf["majority"] == "LONG":
                signals.append(self._create_signal("LONG", "SuperTrend_confirmed",
                    "SuperTrend подтверждает восходящий тренд с MTF", 80))
            elif curr_dir == -1 and self.mtf["majority"] == "SHORT":
                signals.append(self._create_signal("SHORT", "SuperTrend_confirmed",
                    "SuperTrend подтверждает нисходящий тренд с MTF", 80))
        
        return signals
    
    def _vwap_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # VWAP кроссовер
        if self.prev["close"] <= self.prev["vwap"] and self.last["close"] > self.last["vwap"]:
            if self.last["volume_ratio"] > 1.3:
                signals.append(self._create_signal("LONG", "VWAP_cross_volume",
                    f"Цена пересекла VWAP вверх с объемом x{self.last['volume_ratio']:.1f}", 80))
            else:
                signals.append(self._create_signal("LONG", "VWAP_cross_up",
                    "Цена пересекла VWAP снизу вверх", 75))
        
        elif self.prev["close"] >= self.prev["vwap"] and self.last["close"] < self.last["vwap"]:
            if self.last["volume_ratio"] > 1.3:
                signals.append(self._create_signal("SHORT", "VWAP_cross_volume",
                    f"Цена пересекла VWAP вниз с объемом x{self.last['volume_ratio']:.1f}", 80))
            else:
                signals.append(self._create_signal("SHORT", "VWAP_cross_down",
                    "Цена пересекла VWAP сверху вниз", 75))
        
        # VWAP Z-score
        zscore = self.last["vwap_zscore"]
        prev_zscore = self.prev["vwap_zscore"]
        
        if prev_zscore < -2 and zscore > -2:
            signals.append(self._create_signal("LONG", "VWAP_zbounce_up",
                f"Цена отскочила от VWAP (Z-score: {zscore:.2f} -> {zscore:.2f})", 80))
        elif prev_zscore > 2 and zscore < 2:
            signals.append(self._create_signal("SHORT", "VWAP_zbounce_down",
                f"Цена отскочила от VWAP (Z-score: {prev_zscore:.2f} -> {zscore:.2f})", 80))
        
        return signals
    
    def _fibonacci_signals(self) -> List[Dict]:
        signals = []
        
        # Цена на уровнях Фибоначчи
        close = self.last["close"]
        
        # 0.618 - сильный уровень
        if abs(close - self.last["fib_0.618"]) / close < 0.005:
            if self.last["close"] > self.prev["close"]:
                signals.append(self._create_signal("LONG", "Fib_618_support",
                    "Цена на уровне Фибоначчи 0.618 (поддержка)", 85))
            elif self.last["close"] < self.prev["close"]:
                signals.append(self._create_signal("SHORT", "Fib_618_resistance",
                    "Цена на уровне Фибоначчи 0.618 (сопротивление)", 85))
        
        # 0.786 - экстремальный уровень
        elif abs(close - self.last["fib_0.786"]) / close < 0.005:
            if self.last["close"] > self.prev["close"]:
                signals.append(self._create_signal("LONG", "Fib_786_bounce",
                    "Отскок от уровня Фибоначчи 0.786", 90))
            elif self.last["close"] < self.prev["close"]:
                signals.append(self._create_signal("SHORT", "Fib_786_reject",
                    "Отбой от уровня Фибоначчи 0.786", 90))
        
        return signals
    
    def _force_index_signals(self) -> List[Dict]:
        signals = []
        
        if "force_index" in self.last and "force_index_ema" in self.last:
            fi = self.last["force_index"]
            fi_ema = self.last["force_index_ema"]
            prev_fi = self.prev["force_index"] if "force_index" in self.prev else 0
            
            # Кроссовер
            if prev_fi <= fi_ema and fi > fi_ema:
                signals.append(self._create_signal("LONG", "ForceIndex_cross_up",
                    "Force Index пересек сигнальную линию вверх", 80))
            elif prev_fi >= fi_ema and fi < fi_ema:
                signals.append(self._create_signal("SHORT", "ForceIndex_cross_down",
                    "Force Index пересек сигнальную линию вниз", 80))
            
            # Экстремумы
            if fi < -1000000 and fi > prev_fi:  # масштаб зависит от символа
                signals.append(self._create_signal("LONG", "ForceIndex_extreme",
                    "Force Index на экстремально низком уровне", 75))
            elif fi > 1000000 and fi < prev_fi:
                signals.append(self._create_signal("SHORT", "ForceIndex_extreme",
                    "Force Index на экстремально высоком уровне", 75))
        
        return signals
    
    def _choppiness_signals(self) -> List[Dict]:
        signals = []
        
        if "choppiness_14" in self.last:
            chop = self.last["choppiness_14"]
            prev_chop = self.prev["choppiness_14"]
            
            # Выход из флэта (начало тренда)
            if prev_chop > 61.8 and chop < 61.8:
                direction = "LONG" if self.last["close"] > self.last["ema21"] else "SHORT"
                signals.append(self._create_signal(direction, "Choppiness_exit",
                    f"Выход из флэта (Choppiness: {prev_chop:.1f} -> {chop:.1f})", 80))
            
            # Вход во флэт (осторожно)
            if prev_chop < 38.2 and chop > 38.2:
                signals.append(self._create_signal(None, "Choppiness_enter",
                    f"Вход во флэт - избегайте сделок (Choppiness: {chop:.1f})", 0))
        
        return signals
    
    def _williams_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        wr = self.last["williams_r"]
        prev_wr = self.prev["williams_r"]
        
        # Выход из зон
        if prev_wr <= -80 and wr > -80:
            signals.append(self._create_signal("LONG", "Williams_oversold_exit",
                f"Williams %R вышел из перепроданности ({wr:.1f})", 80))
        elif prev_wr >= -20 and wr < -20:
            signals.append(self._create_signal("SHORT", "Williams_overbought_exit",
                f"Williams %R вышел из перекупленности ({wr:.1f})", 80))
        
        return signals
    
    def _mfi_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        mfi = self.last["mfi14"]
        prev_mfi = self.prev["mfi14"]
        
        # Дивергенция MFI
        if self.last["mfi_divergence"] == -1:
            signals.append(self._create_signal("LONG", "MFI_divergence_bull",
                f"Бычья дивергенция MFI ({mfi:.1f})", 85))
        elif self.last["mfi_divergence"] == 1:
            signals.append(self._create_signal("SHORT", "MFI_divergence_bear",
                f"Медвежья дивергенция MFI ({mfi:.1f})", 85))
        
        # Зоны
        if prev_mfi <= 20 and mfi > 20:
            signals.append(self._create_signal("LONG", "MFI_oversold_exit",
                f"MFI вышел из зоны перепроданности ({mfi:.1f})", 80))
        elif prev_mfi >= 80 and mfi < 80:
            signals.append(self._create_signal("SHORT", "MFI_overbought_exit",
                f"MFI вышел из зоны перекупленности ({mfi:.1f})", 80))
        
        return signals
    
    def _cci_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        cci = self.last["cci20"]
        prev_cci = self.prev["cci20"]
        
        # Классические уровни CCI
        if prev_cci <= -100 and cci > -100:
            signals.append(self._create_signal("LONG", "CCI_oversold_exit",
                f"CCI вышел из зоны перепроданности ({cci:.1f})", 80))
        elif prev_cci >= 100 and cci < 100:
            signals.append(self._create_signal("SHORT", "CCI_overbought_exit",
                f"CCI вышел из зоны перекупленности ({cci:.1f})", 80))
        
        # Тренд CCI
        if cci > 100 and prev_cci <= 100:
            signals.append(self._create_signal("LONG", "CCI_break_100",
                f"CCI пробил уровень +100 ({cci:.1f})", 85))
        elif cci < -100 and prev_cci >= -100:
            signals.append(self._create_signal("SHORT", "CCI_break_minus100",
                f"CCI пробил уровень -100 ({cci:.1f})", 85))
        
        return signals
    
    def _mtf_signals_enhanced(self) -> List[Dict]:
        signals = []
        
        # Полное согласование всех таймфреймов
        if self.mtf["consensus"] == "HIGH":
            if self.mtf["majority"] == "LONG":
                signals.append(self._create_signal("LONG", "MTF_full_consensus",
                    f"Все таймфреймы ({len(TIMEFRAMES)}) в восходящем тренде", 90))
            elif self.mtf["majority"] == "SHORT":
                signals.append(self._create_signal("SHORT", "MTF_full_consensus",
                    f"Все таймфреймы ({len(TIMEFRAMES)}) в нисходящем тренде", 90))
        
        # Сильный тренд на 4ч
        if self.mtf.get("4h", {}).get("trend") == "BULLISH" and self.mtf["4h"].get("strength", 0) > 0.7:
            signals.append(self._create_signal("LONG", "MTF_4h_strong_bull",
                f"Сильный восходящий тренд на 4ч (сила: {self.mtf['4h']['strength']:.2f})", 85))
        elif self.mtf.get("4h", {}).get("trend") == "BEARISH" and self.mtf["4h"].get("strength", 0) > 0.7:
            signals.append(self._create_signal("SHORT", "MTF_4h_strong_bear",
                f"Сильный нисходящий тренд на 4ч (сила: {self.mtf['4h']['strength']:.2f})", 85))
        
        return signals
    
    def _ensemble_signals(self) -> List[Dict]:
        """AI-подобный ансамблевый сигнал на основе всех индикаторов"""
        signals = []
        
        # Собираем веса всех индикаторов
        long_score = 0
        short_score = 0
        total_weight = 0
        
        # Индикаторы и их веса
        indicators = [
            # Трендовые
            ("ema8", 2, lambda x: x > self.last["ema21"]),
            ("ema21", 2, lambda x: x > self.last["ema50"]),
            ("adx14", 2, lambda x: x > 25 and self.last["di_plus"] > self.last["di_minus"]),
            ("sma20", 1, lambda x: self.last["close"] > x),
            
            # Осцилляторы
            ("rsi14", 2, lambda x: x < 35),
            ("rsi14_short", 2, lambda x: x > 65),
            ("stoch_k_14", 2, lambda x: x < 25),
            ("stoch_k_14_short", 2, lambda x: x > 75),
            ("mfi14", 2, lambda x: x < 25),
            ("mfi14_short", 2, lambda x: x > 75),
            ("williams_r", 1, lambda x: x < -80),
            ("williams_r_short", 1, lambda x: x > -20),
            
            # Объемные
            ("volume_ratio", 2, lambda x: x > 1.5 and self.last["close"] > self.last["open"]),
            ("volume_ratio_short", 2, lambda x: x > 1.5 and self.last["close"] < self.last["open"]),
            ("cmf", 2, lambda x: x > 0.1),
            ("cmf_short", 2, lambda x: x < -0.1),
            
            # Дивергенции
            ("rsi_divergence", 3, lambda x: x == -1),
            ("rsi_divergence_short", 3, lambda x: x == 1),
            ("macd_divergence", 3, lambda x: x == -1),
            ("macd_divergence_short", 3, lambda x: x == 1),
            
            # Паттерны
            ("bullish_engulf", 3, lambda x: x),
            ("bearish_engulf", 3, lambda x: x),
            
            # MTF
            ("mtf_bull", 3, lambda x: self.mtf["majority"] == "LONG"),
            ("mtf_bear", 3, lambda x: self.mtf["majority"] == "SHORT"),
        ]
        
        for name, weight, condition in indicators:
            if "short" in name:
                if condition(True):
                    short_score += weight
                    total_weight += weight
            else:
                if condition(True):
                    long_score += weight
                    total_weight += weight
        
        # Применяем конкретные условия
        if self.last["close"] < self.last["bb_lower_20_2"]:
            long_score += 1
        if self.last["close"] > self.last["bb_upper_20_2"]:
            short_score += 1
        
        if self.last["macd"] > self.last["macd_signal"]:
            long_score += 2
        if self.last["macd"] < self.last["macd_signal"]:
            short_score += 2
        
        if self.last["obv"] > self.last["obv_ema13"]:
            long_score += 1
        if self.last["obv"] < self.last["obv_ema13"]:
            short_score += 1
        
        total_score = long_score + short_score
        if total_score > 0:
            long_percent = (long_score / total_score) * 100
            short_percent = (short_score / total_score) * 100
            
            if long_percent - short_percent > 30:
                conf = 70 + min(20, int((long_percent - short_percent) / 2))
                signals.append(self._create_signal("LONG", "Ensemble_AI",
                    f"Ансамблевый сигнал LONG ({long_percent:.0f}% vs {short_percent:.0f}%)", min(100, conf)))
            elif short_percent - long_percent > 30:
                conf = 70 + min(20, int((short_percent - long_percent) / 2))
                signals.append(self._create_signal("SHORT", "Ensemble_AI",
                    f"Ансамблевый сигнал SHORT ({short_percent:.0f}% vs {long_percent:.0f}%)", min(100, conf)))
        
        return signals
    
    def _create_signal(self, direction: str, strategy: str, reason: str, base_conf: int) -> Dict:
        """Создает сигнал с расчетом SL/TP (улучшенный)"""
        
        if direction is None:
            return None
        
        current = self.last["close"]
        atr = self.last["atr14"]
        
        if atr <= 0 or pd.isna(atr):
            atr = current * 0.01
        
        # Адаптивный SL на основе волатильности и ATR
        base_sl_percent = (atr / current) * 100
        volatility_factor = 1.0
        
        # Корректировка на волатильность
        if self.last["hv_10"] > 0.5:  # высокая волатильность
            volatility_factor = 1.3
        elif self.last["hv_10"] < 0.2:  # низкая волатильность
            volatility_factor = 0.8
        
        sl_percent = max(0.6, min(2.5, base_sl_percent * 1.2 * volatility_factor))
        
        # Дополнительная корректировка для сильных сигналов
        if base_conf > 85:
            sl_percent *= 0.9  # чуть уже стоп для сильных сигналов
        
        # Объемная корректировка
        if self.last["volume_ratio"] > 2.0:
            sl_percent *= 1.1
        
        # Расчет уровней
        if direction == "LONG":
            sl = current * (1 - sl_percent / 100)
            tp = current * (1 + (sl_percent * MIN_RR_RATIO) / 100)
        else:
            sl = current * (1 + sl_percent / 100)
            tp = current * (1 - (sl_percent * MIN_RR_RATIO) / 100)
        
        # MTF множитель для уверенности
        mtf_conf_bonus = 0
        if direction == "LONG" and self.mtf["majority"] == "LONG":
            mtf_conf_bonus = 10
        elif direction == "SHORT" and self.mtf["majority"] == "SHORT":
            mtf_conf_bonus = 10
        elif direction == "LONG" and self.mtf["majority"] == "SHORT":
            mtf_conf_bonus = -10
        elif direction == "SHORT" and self.mtf["majority"] == "LONG":
            mtf_conf_bonus = -10
        
        # Паттерн множитель
        pattern_bonus = 0
        if strategy in ["BullishEngulf", "BearishEngulf", "MorningStar", "EveningStar"]:
            pattern_bonus = 5
        
        # Объемный множитель
        volume_bonus = 0
        if self.last["volume_ratio"] > 1.5:
            volume_bonus = 5
        elif self.last["volume_ratio"] > 2.0:
            volume_bonus = 10
        
        final_conf = base_conf + mtf_conf_bonus + pattern_bonus + volume_bonus
        final_conf = max(50, min(100, final_conf))
        
        return {
            "symbol": self.symbol,
            "direction": direction,
            "strategy": strategy,
            "reason": reason,
            "confidence": final_conf,
            "price": round(current, 2),
            "sl": round(sl, 2),
            "tp": round(tp, 2),
            "sl_percent": round(sl_percent, 1),
            "tp_percent": round(sl_percent * MIN_RR_RATIO, 1),
            "rr_ratio": MIN_RR_RATIO,
            "mtf_aligned": (direction == "LONG" and self.mtf["majority"] == "LONG") or 
                          (direction == "SHORT" and self.mtf["majority"] == "SHORT"),
            "mtf_1h": self.mtf.get("1h", {}).get("trend", "NEUTRAL"),
            "mtf_2h": self.mtf.get("2h", {}).get("trend", "NEUTRAL"),
            "mtf_4h": self.mtf.get("4h", {}).get("trend", "NEUTRAL"),
            "volume_ratio": round(self.last["volume_ratio"], 2),
            "rsi": round(self.last["rsi14"], 1),
            "atr_percent": round(self.last["atr_percent"], 2),
            "adx": round(self.last.get("adx14", 0), 1),
            "ensemble_score": final_conf,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }


# ==================== АГРЕГАТОР СИГНАЛОВ ====================

class SignalAggregator:
    """Агрегатор сигналов - собирает все сигналы по активу и формирует итоговый"""
    
    @staticmethod
    def aggregate(symbol: str, all_signals: List[Dict], mtf: Dict, df: pd.DataFrame) -> Dict:
        """Агрегирует все сигналы в один итоговый"""
        
        if not all_signals:
            return None
        
        # Разделяем сигналы по направлениям
        long_signals = [s for s in all_signals if s["direction"] == "LONG"]
        short_signals = [s for s in all_signals if s["direction"] == "SHORT"]
        
        # Считаем взвешенные очки
        long_weighted_score = sum(s["confidence"] for s in long_signals)
        short_weighted_score = sum(s["confidence"] for s in short_signals)
        
        # Количество стратегий
        long_count = len(long_signals)
        short_count = len(short_signals)
        
        # Средняя уверенность
        long_avg_conf = long_weighted_score / long_count if long_count > 0 else 0
        short_avg_conf = short_weighted_score / short_count if short_count > 0 else 0
        
        # Бонус за множественные сигналы (уменьшен для реалистичности)
        long_bonus = min(10, long_count * 2)
        short_bonus = min(10, short_count * 2)
        
        # Итоговая оценка
        long_final_score = long_avg_conf + long_bonus
        short_final_score = short_avg_conf + short_bonus
        
        # Более строгий порог для сигнала (25 вместо 15)
        if long_final_score > short_final_score + 25:
            direction = "LONG"
            confidence = min(90, int(long_final_score * 0.85))
            signals_list = long_signals
            opposing_list = short_signals
        elif short_final_score > long_final_score + 25:
            direction = "SHORT"
            confidence = min(90, int(short_final_score * 0.85))
            signals_list = short_signals
            opposing_list = long_signals
        else:
            return None  # Нет явного перевеса
        
        # Сортируем сигналы по уверенности
        signals_list.sort(key=lambda x: -x["confidence"])
        opposing_list.sort(key=lambda x: -x["confidence"])
        
        # Собираем уникальные стратегии
        strategies = list(set([s["strategy"] for s in signals_list]))
        opposing_strategies = list(set([s["strategy"] for s in opposing_list]))
        
        # Формируем причины ЗА
        reasons_for = []
        for s in signals_list[:5]:
            reasons_for.append(f"  • {s['strategy']}: {s['reason']} (уверенность {s['confidence']}%)")
        
        # Формируем причины ПРОТИВ
        reasons_against = []
        for s in opposing_list[:3]:
            reasons_against.append(f"  • {s['strategy']}: {s['reason']} (уверенность {s['confidence']}%)")
        
        # Берем лучший сигнал для расчета SL/TP и цены
        best_signal = signals_list[0]
        
        # MTF данные
        mtf_bullish_count = sum(1 for tf in ["1h", "2h", "4h"] if mtf.get(tf, {}).get("trend") == "BULLISH")
        mtf_bearish_count = sum(1 for tf in ["1h", "2h", "4h"] if mtf.get(tf, {}).get("trend") == "BEARISH")
        
        # Создаем итоговый сигнал
        final_signal = {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "price": best_signal["price"],
            "sl": best_signal["sl"],
            "tp": best_signal["tp"],
            "sl_percent": best_signal["sl_percent"],
            "tp_percent": best_signal["tp_percent"],
            "rr_ratio": MIN_RR_RATIO,
            "mtf_aligned": (direction == "LONG" and mtf_bullish_count >= 2) or (direction == "SHORT" and mtf_bearish_count >= 2),
            "mtf_1h": mtf.get("1h", {}).get("trend", "NEUTRAL"),
            "mtf_2h": mtf.get("2h", {}).get("trend", "NEUTRAL"),
            "mtf_4h": mtf.get("4h", {}).get("trend", "NEUTRAL"),
            "volume_ratio": best_signal["volume_ratio"],
            "rsi": best_signal["rsi"],
            "atr_percent": best_signal.get("atr_percent", 0),
            "total_signals": len(all_signals),
            "bullish_signals": long_count,
            "bearish_signals": short_count,
            "bullish_score": int(long_final_score),
            "bearish_score": int(short_final_score),
            "main_strategies": strategies[:3],
            "opposing_strategies": opposing_strategies[:3],
            "reasons_for": reasons_for,
            "reasons_against": reasons_against,
            "best_strategy": best_signal["strategy"],
            "best_strategy_reason": best_signal["reason"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return final_signal


# ==================== ГЕНЕРАТОР ГРАФИКОВ ====================

class ChartGenerator:
    """Генератор графиков с индикаторами"""
    
    @staticmethod
    def save_chart(symbol: str, df: pd.DataFrame, signal: Dict, patterns: Dict) -> str:
        """Сохраняет график с индикаторами"""
        
        charts_dir = "charts"
        if not os.path.exists(charts_dir):
            os.makedirs(charts_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{charts_dir}/{symbol}_{signal['strategy']}_{timestamp}.png"
        
        plot_df = df.tail(100).copy()
        plot_df.index = pd.to_datetime(plot_df["timestamp"])
        plot_df = plot_df.rename(columns={
            "open": "Open",
            "high": "High", 
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        })
        
        plot_df["EMA21"] = plot_df["Close"].ewm(span=21, adjust=False).mean()
        plot_df["EMA50"] = plot_df["Close"].ewm(span=50, adjust=False).mean()
        plot_df["BB_upper"] = plot_df["Close"].rolling(20).mean() + (plot_df["Close"].rolling(20).std() * 2)
        plot_df["BB_lower"] = plot_df["Close"].rolling(20).mean() - (plot_df["Close"].rolling(20).std() * 2)
        
        rsi = ChartGenerator._calc_rsi(plot_df["Close"], 14)
        
        apds = [
            mpf.make_addplot(plot_df["Volume"], panel=1, type='bar', color='dodgerblue', alpha=0.5),
            mpf.make_addplot(rsi, panel=2, color='purple'),
            mpf.make_addplot([30]*len(rsi), panel=2, color='gray', linestyle='--'),
            mpf.make_addplot([70]*len(rsi), panel=2, color='gray', linestyle='--'),
            mpf.make_addplot(plot_df["EMA21"], color='orange', panel=0),
            mpf.make_addplot(plot_df["EMA50"], color='blue', panel=0),
            mpf.make_addplot(plot_df["BB_upper"], color='gray', linestyle='--', panel=0),
            mpf.make_addplot(plot_df["BB_lower"], color='gray', linestyle='--', panel=0),
        ]
        
        direction_text = "LONG" if signal["direction"] == "LONG" else "SHORT"
        title = f"{symbol} | {direction_text} | {signal['strategy']} | Confidence: {signal['confidence']}%\n"
        title += f"Entry: {signal['price']} | SL: {signal['sl']} (-{signal['sl_percent']}%) | TP: {signal['tp']} (+{signal['tp_percent']}%) | RR: {signal['rr_ratio']}:1"
        
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', wick='black', edge='black', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--')
        
        mpf.plot(
            plot_df,
            type='candle',
            style=s,
            title=title,
            ylabel='Price',
            volume_panel=1,
            addplot=apds,
            figsize=(16, 10),
            savefig=filename
        )
        
        return filename
    
    @staticmethod
    def _calc_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.ffill().bfill().fillna(50)


# ==================== ГЛАВНЫЙ СКАНЕР ====================

class Scanner:
    """Главный сканер с агрегацией сигналов и отправкой в Telegram"""
    
    def __init__(self):
        self.fetcher = DataFetcher()
        self.daily_trades = 0
        self.daily_loss = 0.0
        self.reset_day = datetime.now().date()
        self.signals_history = []
    
    def send_telegram_message(self, message: str, photo_path: str = None):
        """Отправка сообщения в Telegram (фото и текст отдельно)"""
        try:
            import telebot
            bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)
            
            if photo_path and os.path.exists(photo_path):
                with open(photo_path, 'rb') as photo:
                    if TELEGRAM_THREAD_ID:
                        bot.send_photo(
                            chat_id=TELEGRAM_CHAT_ID,
                            photo=photo,
                            message_thread_id=TELEGRAM_THREAD_ID
                        )
                    else:
                        bot.send_photo(
                            chat_id=TELEGRAM_CHAT_ID,
                            photo=photo
                        )
            
            if TELEGRAM_THREAD_ID:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message,
                    message_thread_id=TELEGRAM_THREAD_ID
                )
            else:
                bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=message
                )
            return True
        except Exception as e:
            print(f"⚠️ Ошибка отправки в Telegram: {e}")
            return False
    
    async def analyze_symbol(self, symbol: str) -> Dict:
        """Полный анализ символа с агрегацией всех сигналов в один"""
        
        df = await self.fetcher.get_klines(symbol, "240", CANDLES_LIMIT)
        
        if df.empty or len(df) < 50:
            return None
        
        df = AdvancedIndicators.add_all_indicators(df)
        
        if df.empty:
            return None
        
        patterns = CandlePatterns.detect_all(df)
        mtf = await MultiTimeframeAnalyzer.analyze(self.fetcher, symbol)
        
        generator = SignalGenerator(df, patterns, mtf, symbol)
        all_raw_signals = generator.generate_all_signals()
        
        if not all_raw_signals:
            return None
        
        final_signal = SignalAggregator.aggregate(symbol, all_raw_signals, mtf, df)
        
        if final_signal and final_signal["confidence"] >= MIN_CONFIDENCE_SCORE:
            return final_signal  # БЕЗ ФИЛЬТРА ДУБЛИКАТОВ
        
        return None
    
    async def run_single_scan(self):
        """Однократное сканирование"""
        
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "="*120)
        print(f"🔥🔥🔥 BYBIT PROFESSIONAL SIGNAL SCANNER v4.0 🔥🔥🔥")
        print(f"📊 Мониторинг: {', '.join(SYMBOLS)}")
        print(f"⏱ Таймфреймы для MTF: 1ч → 2ч → 4ч")
        print(f"🎯 Мин. уверенность: {MIN_CONFIDENCE_SCORE}% | RR: {MIN_RR_RATIO}:1")
        print(f"📈 Стратегий: 35+ | Индикаторов: 25+ | Паттернов: 15+")
        print(f"⏰ Время сканирования: {scan_time}")
        print("="*120 + "\n")
        
        print("📡 Загрузка данных...")
        for tf in TIMEFRAMES:
            await self.fetcher.prefetch_all(SYMBOLS, tf, CANDLES_LIMIT)
        
        print("🔍 Анализ символов...")
        final_signals = []
        
        for symbol in SYMBOLS:
            signal = await self.analyze_symbol(symbol)
            if signal:
                final_signals.append(signal)
                print(f"   ✅ {symbol}: {signal['direction']} | Уверенность: {signal['confidence']}% | Стратегий: {signal['total_signals']} (ЗА: {signal['bullish_signals']}, ПРОТИВ: {signal['bearish_signals']})")
            else:
                print(f"   ⚪ {symbol}: сигналов нет или низкая уверенность")
        
        final_signals.sort(key=lambda x: (-x["confidence"], -x["rr_ratio"]))
        
        if final_signals:
            await self._send_signals_to_telegram(final_signals, scan_time)
        else:
            print(f"\n🔍 Сигналов не найдено за {scan_time}")
            self.send_telegram_message(f"🔍 Сканирование завершено ({scan_time})\n\nСигналов, соответствующих критериям, не найдено.")
        
        print("\n✅ Сканирование завершено!")
    
    async def _send_signals_to_telegram(self, signals: List[Dict], scan_time: str):
        """Отправка агрегированных сигналов в Telegram"""
        
        for sig in signals:
            direction_emoji = "🟢 LONG" if sig["direction"] == "LONG" else "🔴 SHORT"
            star = "⭐️⭐️⭐️" if sig["confidence"] > 90 else "⭐️⭐️" if sig["confidence"] > 80 else "⭐️"
            
            total_score = sig['bullish_score'] + sig['bearish_score']
            bull_percent = (sig['bullish_score'] / total_score * 100) if total_score > 0 else 0
            bear_percent = (sig['bearish_score'] / total_score * 100) if total_score > 0 else 0
            
            message = f"""🎯 ИТОГОВЫЙ СИГНАЛ 🎯
⏰ Время: {scan_time}

{direction_emoji} {star} {sig['symbol']}
📈 Уверенность: {sig['confidence']}%
🎯 Лучшая стратегия: {sig['best_strategy']}

📊 БАЛАНС СИГНАЛОВ:
   • Всего сигналов: {sig['total_signals']}
   • За {sig['direction']}: {sig['bullish_signals'] if sig['direction'] == 'LONG' else sig['bearish_signals']} шт.
   • Против: {sig['bearish_signals'] if sig['direction'] == 'LONG' else sig['bullish_signals']} шт.
   • Соотношение: {bull_percent:.0f}% : {bear_percent:.0f}%

✅ АРГУМЕНТЫ ЗА:
{chr(10).join(sig['reasons_for'][:5])}

{'❌ АРГУМЕНТЫ ПРОТИВ:' if sig['reasons_against'] else ''}
{chr(10).join(sig['reasons_against'][:3]) if sig['reasons_against'] else ''}

💰 ТОРГОВЫЕ УРОВНИ:
   • Вход: {sig['price']}
   • SL: {sig['sl']} (-{sig['sl_percent']}%)
   • TP: {sig['tp']} (+{sig['tp_percent']}%)
   • RR: {sig['rr_ratio']}:1

📊 ТЕКУЩИЕ ИНДИКАТОРЫ:
   • RSI: {sig['rsi']}
   • Объем: x{sig['volume_ratio']}
   • ATR: {sig['atr_percent']}%

🌐 МУЛЬТИ-ТАЙМФРЕЙМ:
   • 1ч: {sig['mtf_1h']}
   • 2ч: {sig['mtf_2h']}
   • 4ч: {sig['mtf_4h']}
   • Согласованность: {'✅ ДА' if sig['mtf_aligned'] else '⚠️ НЕТ'}

✨ КЛЮЧЕВЫЕ СТРАТЕГИИ:
   • {sig['best_strategy']}: {sig['best_strategy_reason']}"""
            
            photo_path = None
            if sig["confidence"] > 75:
                try:
                    df = await self.fetcher.get_klines(sig["symbol"], "240", CANDLES_LIMIT)
                    if not df.empty:
                        df = AdvancedIndicators.add_all_indicators(df)
                        patterns = CandlePatterns.detect_all(df)
                        chart_signal = sig.copy()
                        chart_signal["strategy"] = sig.get("best_strategy", "Unknown")
                        chart_signal["reason"] = sig.get("best_strategy_reason", " ")
                        chart_signal["atr_percent"] = sig.get("atr_percent", 0)
                        photo_path = ChartGenerator.save_chart(sig["symbol"], df, chart_signal, patterns)
                        print(f"   📸 Сохранен график: {photo_path}")
                except Exception as e:
                    print(f"   ⚠️ Ошибка сохранения графика: {e}")
            
            self.send_telegram_message(message, photo_path)
            
            if photo_path and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except:
                    pass
        # ========== СВОДКА В КОНЦЕ ==========
        summary = f"📊 СВОДКА СКАНИРОВАНИЯ\n⏰ {scan_time}\n\nНайдено сигналов: {len(signals)}\n\n"
        for sig in signals:
            summary += f"{'🟢' if sig['direction'] == 'LONG' else '🔴'} {sig['symbol']} | {sig['direction']} | {sig['confidence']}%\n"
    
        self.send_telegram_message(summary, None)


# ==================== ЗАПУСК ====================

async def main():
    scanner = Scanner()
    await scanner.run_single_scan()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Сканер остановлен. Хороших торгов!")