import React, { useState } from 'react';
import Box from '@material-ui/core/Box';
import Controls from './Controls';
import SplitPane from '../SplitPane';
import TradingResult from '../TradingResult';
import { fetchJson } from '../../fetch';

export default function Dashboard() {
  const [tradingResult, setTradingResult] = useState(null);

  async function backtest(args) {
    const result = await fetchJson(
      'POST',
      `/backtest/${args.strategy}/${args.stopLoss}/${args.takeProfit}`,
      args,
    );

    setTradingResult({
      args: {
        exchange: args.exchange,
        interval: args.interval,
        start: args.start,
        end: args.end,
        trainingSymbols: args.symbols,
        validationSymbols: [],
      },
      config: {
        trader: args.traderParams,
        strategy: {
          type: args.strategy,
          ...args.strategyParams,
        },
        stopLoss: {
          type: args.stopLoss,
          ...args.stopLossParams,
        },
        takeProfit: {
          type: args.takeProfit,
          ...args.takeProfitParams,
        },
      },
      symbolStats: result.symbolStats,
      title: args.strategy,
    });
  }

  return (
    <SplitPane
      left={
        <Box p={1}>
          <Controls onBacktest={backtest} />
        </Box>
      }
      right={tradingResult && <TradingResult value={tradingResult} />}
    />
  );
}
