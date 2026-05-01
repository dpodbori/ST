import argparse
import importlib
import inspect
import os

import backtrader as bt

tickers = ['AMZN', 'AAPL', 'DIA', 'NVDA', 'ZIM']
DEFAULT_TICKER = tickers[0]
DEFAULT_INTERVAL = ['2020-01-01', '2025-05-17']
INITIAL_CASH = 100000.0
COMMISSION = 0.001
MARKET_DATA_FOLDER = None

STRATEGY_FOLDER = os.path.join(os.path.dirname(__file__), "strategies")

class StrategyDefinition:
    def __init__(self, name: str, strategy_class, show_parameters):
        self.name = name
        self.strategy_class = strategy_class
        self.show_parameters = show_parameters

def load_strategies():
    strategies = []
    for filename in os.listdir(STRATEGY_FOLDER):
        if filename.endswith(".py") and not filename.startswith("__"):
            module_name = f"strategies.{filename[:-3]}"
            module = importlib.import_module(module_name)
            # Find first class derived from bt.Strategy
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, bt.Strategy) and obj is not bt.Strategy:
                    show_params = getattr(module, "show_parameters", None)
                    strategies.append(StrategyDefinition(name, obj, show_params))
                    break
    return strategies

strategies = load_strategies()

DEFAULT_STRATEGY = 0

def parse_args():
    parser = argparse.ArgumentParser(description="Strategy config CLI")
    parser.add_argument("--ticker", choices=tickers, help="Override default ticker")
    parser.add_argument("--interval", nargs=2, metavar=('START', 'END'), help="Override interval")
    parser.add_argument("--strategy", help="Override default strategy name")
    parser.add_argument("--market_data_folder", help="Override market data folder path")
    args = parser.parse_args()
    return args

args = parse_args()
if args.ticker:
    DEFAULT_TICKER = args.ticker
if args.interval:
    DEFAULT_INTERVAL = args.interval
if args.strategy:
    # Find strategy index by name
    found_index = next((i for i, s in enumerate(strategies) if s.name == args.strategy), None)
    if found_index is not None:
        DEFAULT_STRATEGY = found_index
if args.market_data_folder:
    MARKET_DATA_FOLDER = args.market_data_folder