//+------------------------------------------------------------------+
//|  QuantPlatformExecutor.mq5                                        |
//|  HARDENED EXECUTION & SAFETY LAYER ONLY.                          |
//|                                                                  |
//|  Python is the sole brain: it generates ALL alpha, portfolio,    |
//|  risk, hedging and sizing decisions. This EA NEVER generates a    |
//|  signal, NEVER makes an alpha decision, and NEVER overrides a     |
//|  Python decision. It only:                                        |
//|    - executes the orders Python sends (market/pending/modify/    |
//|      close/flatten),                                             |
//|    - reports fills, account state and symbol state back,          |
//|    - maintains a heartbeat,                                       |
//|    - enforces hard last-resort SAFETY floors (daily-loss stop,    |
//|      max positions, emergency flatten) — safety, not sizing.      |
//|                                                                  |
//|  Transport: atomic key=value files in the COMMON files folder.    |
//|    Python -> commands/<id>.cmd     EA -> responses/<id>.resp      |
//|    EA -> state/{account,positions,ea_heartbeat}                   |
//|    Python -> state/py_heartbeat ,  EMERGENCY_STOP (flag file)     |
//+------------------------------------------------------------------+
#property copyright "Quant Platform"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input string CommSubdir            = "quant_ea";  // under <common>/Files
input int    MagicNumber           = 990001;
input int    PollMillis            = 200;         // command poll cadence
input double MaxDailyLossPct       = 5.0;         // hard safety floor (NOT sizing)
input int    MaxOpenPositions      = 50;          // hard safety cap
input int    PyHeartbeatTimeoutSec = 30;          // Python silence -> stop new risk

CTrade   trade;
string   g_cmd, g_resp, g_state, g_audit;
double   g_day_start_equity = 0.0;
int      g_day = -1;
bool     g_emergency = false;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetTypeFillingBySymbol(_Symbol);
   string base = CommSubdir;
   g_cmd   = base + "\\commands";
   g_resp  = base + "\\responses";
   g_state = base + "\\state";
   g_audit = base + "\\state\\execution_audit.log";
   FolderCreate(g_cmd,   FILE_COMMON);
   FolderCreate(g_resp,  FILE_COMMON);
   FolderCreate(g_state, FILE_COMMON);
   ResetDayAnchor();
   Audit("init", "EA started magic=" + IntegerToString(MagicNumber));
   WriteState();
   EventSetMillisecondTimer(PollMillis);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Audit("deinit", "reason=" + IntegerToString(reason));
}

//+------------------------------------------------------------------+
void OnTimer()
{
   WriteHeartbeat();
   WriteState();                       // account + positions snapshot every tick

   // Broker disconnect recovery: do not execute while disconnected; resume later.
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
   {
      Audit("disconnected", "terminal not connected; deferring commands");
      return;
   }

   CheckSafety();                      // local risk emergency stop (daily loss, kill file)
   ProcessCommands();
}

//+------------------------------------------------------------------+
//| Safety layer (last-resort floors; never sizing/alpha)            |
//+------------------------------------------------------------------+
void ResetDayAnchor()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(t.day != g_day)
   {
      g_day = t.day;
      g_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   }
}

void CheckSafety()
{
   ResetDayAnchor();

   // Explicit emergency flag dropped by Python -> flatten everything.
   if(FileIsExist(CommSubdir + "\\EMERGENCY_STOP", FILE_COMMON))
   {
      if(!g_emergency) Audit("emergency_stop", "EMERGENCY_STOP flag present");
      g_emergency = true;
      FlattenAll("emergency_flag");
   }

   // Hard daily-loss floor.
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_day_start_equity > 0 && eq <= g_day_start_equity * (1.0 - MaxDailyLossPct / 100.0))
   {
      if(!g_emergency) Audit("daily_loss_stop", "equity floor breached eq=" + DoubleToString(eq, 2));
      g_emergency = true;
      FlattenAll("daily_loss_stop");
   }

   // Python heartbeat loss -> stop accepting NEW risk (do not auto-flatten).
   datetime hb = ReadEpoch(g_state + "\\py_heartbeat");
   if(hb > 0 && (TimeCurrent() - hb) > PyHeartbeatTimeoutSec)
   {
      if(!g_emergency) Audit("py_heartbeat_lost", "stopping new risk");
      g_emergency = true;
   }
}

//+------------------------------------------------------------------+
//| Command processing (idempotent, fail-safe acknowledgement)       |
//+------------------------------------------------------------------+
void ProcessCommands()
{
   string file;
   long   handle = FileFindFirst(g_cmd + "\\*.cmd", file, FILE_COMMON);
   if(handle == INVALID_HANDLE) return;
   do
   {
      string cid = StringSubstr(file, 0, StringLen(file) - 4); // strip ".cmd"
      string resp_path = g_resp + "\\" + cid + ".resp";
      if(FileIsExist(resp_path, FILE_COMMON))                  // already answered -> idempotent
      {
         FileDelete(g_cmd + "\\" + file, FILE_COMMON);
         continue;
      }
      string content = ReadFile(g_cmd + "\\" + file);
      ExecuteCommand(cid, content, resp_path);
      FileDelete(g_cmd + "\\" + file, FILE_COMMON);            // consume after responding
   }
   while(FileFindNext(handle, file));
   FileFindClose(handle);
}

void ExecuteCommand(string cid, string content, string resp_path)
{
   string type   = GetField(content, "type");
   string symbol = GetField(content, "symbol");
   string side   = GetField(content, "side");
   double volume = StringToDouble(GetField(content, "volume"));
   double price  = StringToDouble(GetField(content, "price"));
   double sl     = StringToDouble(GetField(content, "sl"));
   double tp     = StringToDouble(GetField(content, "tp"));
   long   ticket = (long)StringToInteger(GetField(content, "ticket"));

   // Fail-safe idempotency across restarts: if a position already carries this id, treat as filled.
   if(PositionExistsForId(cid))
   {
      WriteResponse(resp_path, cid, "duplicate", 0, 0, 0, "position already open for id");
      return;
   }

   // Safety: block NEW risk while in emergency; always allow CLOSE / FLATTEN / PING.
   bool new_risk = (type == "MARKET" || type == "PENDING" || type == "MODIFY");
   if(g_emergency && new_risk)
   {
      WriteResponse(resp_path, cid, "blocked", 0, 0, 0, "emergency stop active");
      Audit("blocked", cid + " " + type);
      return;
   }
   if(new_risk && PositionsTotal() >= MaxOpenPositions && type != "MODIFY")
   {
      WriteResponse(resp_path, cid, "blocked", 0, 0, 0, "max open positions");
      return;
   }

   if(type == "PING")            { WriteResponse(resp_path, cid, "ack", 0, 0, 0, "pong"); return; }
   if(type == "FLATTEN_ALL")     { FlattenAll(cid); WriteResponse(resp_path, cid, "flat", 0, 0, 0, "flattened"); return; }
   if(type == "MARKET")          { DoMarket(cid, symbol, side, volume, sl, tp, resp_path); return; }
   if(type == "PENDING")         { DoPending(cid, symbol, side, GetField(content,"order_type"), volume, price, sl, tp, resp_path); return; }
   if(type == "MODIFY")          { DoModify(cid, ticket, sl, tp, resp_path); return; }
   if(type == "CLOSE")           { DoClose(cid, ticket, resp_path); return; }

   WriteResponse(resp_path, cid, "error", 0, 0, 0, "unknown type " + type);
}

void DoMarket(string cid, string symbol, string side, double volume, double sl, double tp, string resp_path)
{
   trade.SetTypeFillingBySymbol(symbol);
   bool ok = (side == "buy") ? trade.Buy(volume, symbol, 0.0, sl, tp, cid)
                             : trade.Sell(volume, symbol, 0.0, sl, tp, cid);
   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      WriteResponse(resp_path, cid, "filled", (long)trade.ResultOrder(),
                    trade.ResultPrice(), trade.ResultVolume(), "market filled");
      Audit("filled", cid + " " + side + " " + symbol + " " + DoubleToString(volume,2));
   }
   else
   {
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, trade.ResultRetcodeDescription());
      Audit("rejected", cid + " " + trade.ResultRetcodeDescription());
   }
}

void DoPending(string cid, string symbol, string side, string ot, double volume,
               double price, double sl, double tp, string resp_path)
{
   bool ok = false;
   if(side == "buy"  && ot == "limit") ok = trade.BuyLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(side == "buy"  && ot == "stop")  ok = trade.BuyStop (volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(side == "sell" && ot == "limit") ok = trade.SellLimit(volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(side == "sell" && ot == "stop")  ok = trade.SellStop (volume, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
      WriteResponse(resp_path, cid, "pending", (long)trade.ResultOrder(), price, volume, "pending placed");
   else
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, trade.ResultRetcodeDescription());
}

void DoModify(string cid, long ticket, double sl, double tp, string resp_path)
{
   bool ok = trade.PositionModify(ticket, sl, tp);
   if(!ok) ok = trade.OrderModify(ticket, 0, sl, tp, ORDER_TIME_GTC, 0);
   WriteResponse(resp_path, cid, ok ? "modified" : "error", ticket, 0, 0,
                 ok ? "sl/tp updated" : trade.ResultRetcodeDescription());
}

void DoClose(string cid, long ticket, string resp_path)
{
   bool ok = false;
   if(PositionSelectByTicket(ticket)) ok = trade.PositionClose(ticket);
   else                               ok = trade.OrderDelete(ticket);
   WriteResponse(resp_path, cid, ok ? "closed" : "error", ticket, 0, 0,
                 ok ? "closed" : trade.ResultRetcodeDescription());
}

void FlattenAll(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk != 0) trade.PositionClose(tk);
   }
   for(int j = OrdersTotal() - 1; j >= 0; j--)
   {
      ulong tk = OrderGetTicket(j);
      if(tk != 0) trade.OrderDelete(tk);
   }
   Audit("flatten_all", reason);
}

bool PositionExistsForId(string cid)
{
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && PositionGetString(POSITION_COMMENT) == cid) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| State / heartbeat / audit reporting                              |
//+------------------------------------------------------------------+
void WriteState()
{
   string acct = "login=" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "\n"
               + "balance=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n"
               + "equity=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n"
               + "margin_free=" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + "\n"
               + "currency=" + AccountInfoString(ACCOUNT_CURRENCY) + "\n"
               + "trade_mode=" + IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE)) + "\n"
               + "emergency=" + (g_emergency ? "1" : "0") + "\n"
               + "ts=" + TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n";
   WriteFileAtomic(g_state + "\\account.state", acct);

   string pos = "";
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      double q = PositionGetDouble(POSITION_VOLUME);
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL) q = -q;
      pos += PositionGetString(POSITION_SYMBOL) + "|" + DoubleToString(q, 2) + "|"
           + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), _Digits) + "\n";
   }
   WriteFileAtomic(g_state + "\\positions.state", pos);
}

void WriteHeartbeat()
{
   WriteFileAtomic(g_state + "\\ea_heartbeat",
                   TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n");
}

void WriteResponse(string path, string cid, string status, long ticket,
                   double fill_price, double fill_volume, string message)
{
   string r = "id=" + cid + "\n"
            + "status=" + status + "\n"
            + "ticket=" + IntegerToString(ticket) + "\n"
            + "fill_price=" + DoubleToString(fill_price, _Digits) + "\n"
            + "fill_volume=" + DoubleToString(fill_volume, 2) + "\n"
            + "message=" + message + "\n"
            + "ts=" + TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n";
   WriteFileAtomic(path, r);          // atomic: Python never reads a partial response
}

void Audit(string event, string detail)
{
   int h = FileOpen(g_audit, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\t" + event
                      + "\t" + detail + "\n");
   FileClose(h);
}

//+------------------------------------------------------------------+
//| File / parse helpers                                             |
//+------------------------------------------------------------------+
void WriteFileAtomic(string path, string content)
{
   string tmp = path + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileWriteString(h, content);
   FileClose(h);
   FileMove(tmp, FILE_COMMON, path, FILE_COMMON | FILE_REWRITE);
}

string ReadFile(string path)
{
   int h = FileOpen(path, FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return("");
   string out = "";
   while(!FileIsEnding(h)) out += FileReadString(h) + "\n";
   FileClose(h);
   return(out);
}

datetime ReadEpoch(string path)
{
   string s = ReadFile(path);
   StringTrimLeft(s); StringTrimRight(s);
   if(s == "") return(0);
   return(StringToTime(s));   // EA writes/reads "YYYY.MM.DD HH:MM:SS" GMT
}

string GetField(string content, string key)
{
   string lines[];
   int n = StringSplit(content, '\n', lines);
   for(int i = 0; i < n; i++)
   {
      int eq = StringFind(lines[i], "=");
      if(eq < 0) continue;
      string k = StringSubstr(lines[i], 0, eq);
      StringTrimLeft(k); StringTrimRight(k);
      if(k == key)
      {
         string v = StringSubstr(lines[i], eq + 1);
         StringTrimLeft(v); StringTrimRight(v);
         return(v);
      }
   }
   return("");
}
//+------------------------------------------------------------------+
