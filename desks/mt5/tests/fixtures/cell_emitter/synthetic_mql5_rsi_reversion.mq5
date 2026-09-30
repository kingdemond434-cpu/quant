// SYNTHETIC FIXTURE -- written for desks/mt5/tests/test_cell_emitter.py, not recorded from any site.
#property copyright "fixture"
input int    RsiPeriod  = 7;
input double Oversold   = 25;
input double Overbought = 75;
int OnInit() { return(INIT_SUCCEEDED); }
void OnTick()
  {
   double rsi = iRSI(_Symbol, PERIOD_H1, RsiPeriod, PRICE_CLOSE);
   if(rsi < Oversold)
      trade.PositionOpen(_Symbol, ORDER_TYPE_BUY, 0.1, Ask, 0, 0);
   if(rsi > Overbought)
      trade.PositionOpen(_Symbol, ORDER_TYPE_SELL, 0.1, Bid, 0, 0);
  }
