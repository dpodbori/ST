import backtrader as bt
import config
from trade_list_analyzer import TradeListAnalyzer


def run_strategy(strategy: config.StrategyDefinition, data, model_params):
    # Create a Cerebro engine
    cerebro = bt.Cerebro()

    data_feed = bt.feeds.PandasData(dataname=data)
    cerebro.adddata(data_feed)

    # Add the improved MACD strategy
    cerebro.addstrategy(strategy.strategy_class, **model_params)

    # Set the initial cash amount and commission
    cerebro.broker.setcash(config.INITIAL_CASH)
    cerebro.broker.setcommission(commission=config.COMMISSION)
    cerebro.addobserver(bt.observers.Broker)
    cerebro.addobserver(bt.observers.Trades)
    cerebro.addobserver(bt.observers.DrawDown)
    cerebro.addobserver(bt.observers.BuySell)
    
    # analyzers
    cerebro.addanalyzer(bt.analyzers.SharpeRatio,   _name='sharpe',    timeframe=bt.TimeFrame.Days, compression=1, factor=252, annualize=True)
    cerebro.addanalyzer(bt.analyzers.AnnualReturn,  _name='annual_return')
    cerebro.addanalyzer(bt.analyzers.Returns,       _name='returns',   timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown,      _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    cerebro.addanalyzer(bt.analyzers.SQN,           _name='sqn')
    cerebro.addanalyzer(bt.analyzers.Calmar,        _name='calmar')
    cerebro.addanalyzer(TradeListAnalyzer,          _name='trade_list')

    # Print starting account value
    print('<START> Brokerage account: $%.2f' % cerebro.broker.getvalue())
    # Run the strategy
    results = cerebro.run()

    # Print ending account value
    print('<FINISH> Brokerage account: $%.2f' % cerebro.broker.getvalue())
    # Plot the results
    figs = cerebro.plot()
    fig = figs[0][0]
    return [results[0], cerebro.broker.getvalue(), fig]
