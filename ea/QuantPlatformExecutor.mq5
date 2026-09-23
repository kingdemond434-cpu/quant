//+------------------------------------------------------------------+
//|  QuantPlatformExecutor.mq5                                        |
//|  HARDENED EXECUTION & SAFETY LAYER ONLY.  v1.10                   |
//|                                                                  |
//|  Python is the sole brain: it generates ALL alpha, portfolio,    |
//|  risk, hedging and sizing decisions. This EA NEVER generates a    |
//|  signal, NEVER makes an alpha decision, and NEVER overrides a     |
//|  Python decision. It only:                                        |
//|    - executes the orders Python sends (market/pending/modify/    |
//|      close/flatten),                                              |
//|    - reports fills, account state and symbol state back,          |
//|    - maintains a heartbeat,                                       |
//|    - enforces hard last-resort SAFETY floors (daily-loss stop,    |
//|      max positions, emergency flatten) — safety, not sizing.      |
//|                                                                  |
//|  Transport: atomic key=value files in the COMMON files folder.    |
//|    Python -> commands/<id>.cmd     EA -> responses/<id>.resp      |
//|    EA -> state/{account,positions,ea_heartbeat}                   |
//|    Python -> state/py_heartbeat ,  EMERGENCY_STOP (flag file)     |
//|                                                                  |
//|  v1.10 hardening:                                                 |
//|    - heartbeat timeout compares GMT to GMT (was server-time mix)  |
//|    - partial fills (DONE_PARTIAL) reported honestly, not rejected |
//|    - persistent processed-id journal (idempotency no longer       |
//|      depends on broker-preserved order comments)                  |
//|    - magic-scoped flatten/positions cap (other strategies and     |
//|      manual trades on a shared account are untouched unless       |
//|      FlattenAccountWide=true)                                     |
//|    - MODIFY (de-risk) always allowed, even while blocked          |
//|    - emergency states auto-recover (kill flag: on flag removal;   |
//|      daily-loss: next day; heartbeat: when heartbeat returns)     |
//|    - volume/price/stop-level validation with explicit errors      |
//|    - atomic-write retry on Windows reader contention; audit log   |
//|      rotation; per-symbol digit formatting; command sentinel      |
//+------------------------------------------------------------------+
#property copyright "Quant Platform"
#property version   "1.10"
#property strict

#include <Trade/Trade.mqh>

input string CommSubdir            = "quant_ea";  // under <common>/Files
input int    MagicNumber           = 990001;
input int    PollMillis            = 200;         // command poll cadence
input double MaxDailyLossPct       = 5.0;         // hard safety floor (NOT sizing)
input int    MaxOpenPositions      = 50;          // hard cap (this EA's magic only)
input int    PyHeartbeatTimeoutSec = 30;          // Python silence -> stop new risk
input int    DeviationPoints       = 50;          // max slippage for market orders
input bool   FlattenAccountWide    = false;       // true = flatten also closes foreign magics

CTrade   trade;
string   g_cmd, g_resp, g_state, g_audit;
double   g_day_start_equity = 0.0;
int      g_day = -1;
// Emergency states are tracked separately so each recovers on its own evidence:
bool     g_kill_flag    = false;  // EMERGENCY_STOP file present (clears when file removed)
bool     g_day_blocked  = false;  // daily-loss floor breached (clears on new day)
bool     g_hb_lost      = false;  // Python heartbeat stale (clears when fresh again)

// Processed-command-id journal: bounded ring of recent ids, reloaded on init so
// restart idempotency never depends on the broker preserving order comments.
#define JOURNAL_CAP 2048
string   g_seen_ids[JOURNAL_CAP];
int      g_seen_count = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(DeviationPoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   string base = CommSubdir;
   g_cmd   = base + "\\commands";
   g_resp  = base + "\\responses";
   g_state = base + "\\state";
   g_audit = base + "\\state\\execution_audit.log";
   FolderCreate(g_cmd,   FILE_COMMON);
   FolderCreate(g_resp,  FILE_COMMON);
   FolderCreate(g_state, FILE_COMMON);
   LoadJournal();
   ResetDayAnchor();
   Audit("init", "EA started v1.10 magic=" + IntegerToString(MagicNumber));
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
   WriteState();                       // account + positions snapshot each poll

   // Broker disconnect recovery: do not execute while disconnected; resume later.
   if(!TerminalInfoInteger(TERMINAL_CONNECTED))
   {
      Audit("disconnected", "terminal not connected; deferring commands");
      return;
   }

   CheckSafety();                      // local risk emergency floors
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
      g_day_blocked = false;            // daily floor is day-scoped by definition
   }
}

void CheckSafety()
{
   ResetDayAnchor();

   // Explicit emergency flag dropped by Python -> flatten everything (ours).
   bool flag = FileIsExist(CommSubdir + "\\EMERGENCY_STOP", FILE_COMMON);
   if(flag && !g_kill_flag) Audit("emergency_stop", "EMERGENCY_STOP flag present");
   g_kill_flag = flag;                  // clears when Python removes the flag

   // Hard daily-loss floor (day-scoped; recovers at the next day anchor).
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(!g_day_blocked && g_day_start_equity > 0
      && eq <= g_day_start_equity * (1.0 - MaxDailyLossPct / 100.0))
   {
      Audit("daily_loss_stop", "equity floor breached eq=" + DoubleToString(eq, 2));
      g_day_blocked = true;
   }
   if(g_day_blocked) FlattenAll("daily_loss_stop");

   // Python heartbeat loss -> stop accepting NEW risk (no auto-flatten).
   // GMT vs GMT: the heartbeat file holds TimeGMT(); TimeCurrent() is broker
   // server time (UTC+2/+3) and must never be compared against it.
   datetime hb = ReadEpoch(g_state + "\\py_heartbeat");
   bool stale = (hb > 0 && (TimeGMT() - hb) > PyHeartbeatTimeoutSec);
   if(stale && !g_hb_lost) Audit("py_heartbeat_lost", "stopping new risk");
   if(!stale && g_hb_lost) Audit("py_heartbeat_ok", "heartbeat fresh; resuming");
   g_hb_lost = stale;

   if(g_kill_flag) FlattenAll("emergency_flag");
}

bool BlockedForNewRisk()
{
   return(g_kill_flag || g_day_blocked || g_hb_lost);
}

int CountOurPositions()
{
   int n = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && PositionGetInteger(POSITION_MAGIC) == MagicNumber) n++;
   }
   return(n);
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
   // Command sentinel: a partial/corrupt file must never reach the trade layer.
   string type = GetField(content, "type");
   if(cid == "" || type == "" || GetField(content, "id") != cid)
   {
      WriteResponse(resp_path, cid, "error", 0, 0, 0, "malformed command file");
      Audit("malformed", cid);
      return;
   }
   string symbol = GetField(content, "symbol");
   string side   = GetField(content, "side");
   double volume = StringToDouble(GetField(content, "volume"));
   double price  = StringToDouble(GetField(content, "price"));
   double sl     = StringToDouble(GetField(content, "sl"));
   double tp     = StringToDouble(GetField(content, "tp"));
   long   ticket = (long)StringToInteger(GetField(content, "ticket"));

   // Fail-safe idempotency across restarts: journal first (broker-independent),
   // then open-position comment as a secondary net for pre-journal positions.
   if(JournalHas(cid) || PositionExistsForId(cid))
   {
      WriteResponse(resp_path, cid, "duplicate", 0, 0, 0, "command already executed");
      return;
   }

   // Safety: block NEW risk while blocked; MODIFY and de-risk/close always pass
   // (blocking stop-tightening during an emergency would block de-risking).
   bool new_risk = (type == "MARKET" || type == "PENDING");
   if(new_risk && BlockedForNewRisk())
   {
      WriteResponse(resp_path, cid, "blocked", 0, 0, 0, "safety stop active");
      Audit("blocked", cid + " " + type);
      return;
   }
   if(new_risk && CountOurPositions() >= MaxOpenPositions)
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

//+------------------------------------------------------------------+
//| Symbol validation: volume normalization, margin, stop levels     |
//+------------------------------------------------------------------+
bool ValidateOrder(string symbol, double vol_in, double price, double sl, double tp,
                   long order_type, double &vol_out, string &err)
{
   if(!SymbolSelect(symbol, true)) { err = "unknown symbol " + symbol; return(false); }
   double vmin  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
   double vmax  = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   if(vstep <= 0) vstep = 0.01;
   vol_out = MathRound(vol_in / vstep) * vstep;
   if(vol_out < vmin) { err = "volume below min " + DoubleToString(vmin, 2); return(false); }
   if(vol_out > vmax) vol_out = vmax;
   // Margin check (fail-closed: cannot verify -> reject).
   double margin = 0.0;
   if(!OrderCalcMargin(order_type, symbol, vol_out, price, margin))
      { err = "margin calc failed"; return(false); }
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      { err = "insufficient free margin"; return(false); }
   return(true);
}

bool ValidateStops(string symbol, bool is_buy, double sl, double tp, string &err)
{
   if(sl == 0 && tp == 0) return(true);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   long   stops = SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double min_dist = stops * point;
   MqlTick tick; if(!SymbolInfoTick(symbol, tick)) { err = "no tick"; return(false); }
   if(sl != 0)
   {
      double d = is_buy ? (sl - tick.bid) : (tick.ask - sl);
      if(d < min_dist) { err = "sl inside stops level"; return(false); }
   }
   if(tp != 0)
   {
      double d = is_buy ? (tp - tick.ask) : (tick.bid - tp);
      if(d < min_dist) { err = "tp inside stops level"; return(false); }
   }
   return(true);
}

//+------------------------------------------------------------------+
void DoMarket(string cid, string symbol, string side, double volume, double sl, double tp, string resp_path)
{
   double vol = 0.0; string err = "";
   long   otype = (side == "buy") ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick)) { WriteResponse(resp_path, cid, "error", 0, 0, 0, "no tick"); return; }
   double ref_price = (side == "buy") ? tick.ask : tick.bid;
   if(!ValidateOrder(symbol, volume, ref_price, sl, tp, otype, vol, err)
      || !ValidateStops(symbol, side == "buy", sl, tp, err))
   {
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, err);
      Audit("rejected", cid + " " + err);
      return;
   }
   trade.SetTypeFillingBySymbol(symbol);
   bool ok = (side == "buy") ? trade.Buy(vol, symbol, 0.0, sl, tp, cid)
                             : trade.Sell(vol, symbol, 0.0, sl, tp, cid);
   uint rc = trade.ResultRetcode();
   // DONE_PARTIAL is a real (partial) fill, not a rejection — report it honestly
   // so Python's book matches the broker's book.
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL))
   {
      bool partial = (rc == TRADE_RETCODE_DONE_PARTIAL);
      WriteResponse(resp_path, cid, "filled", (long)trade.ResultOrder(),
                    trade.ResultPrice(), trade.ResultVolume(),
                    partial ? "partial fill" : "market filled", DigitsOf(symbol));
      Audit("filled", cid + " " + side + " " + symbol + " "
           + DoubleToString(trade.ResultVolume(), 2) + (partial ? " PARTIAL" : ""));
      JournalAdd(cid);
   }
   else
   {
      // Ambiguous retcodes (timeout, connection loss) may still have reached the
      // broker: the response says rejected, but the id is journaled only on real
      // fills — Python reconciles positions.state (which carries command ids in
      // comments + journal) against its own book.
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, trade.ResultRetcodeDescription());
      Audit("rejected", cid + " " + trade.ResultRetcodeDescription());
   }
}

void DoPending(string cid, string symbol, string side, string ot, double volume,
               double price, double sl, double tp, string resp_path)
{
   double vol = 0.0; string err = "";
   long otype = -1;
   if(side == "buy"  && ot == "limit") otype = ORDER_TYPE_BUY_LIMIT;
   if(side == "buy"  && ot == "stop")  otype = ORDER_TYPE_BUY_STOP;
   if(side == "sell" && ot == "limit") otype = ORDER_TYPE_SELL_LIMIT;
   if(side == "sell" && ot == "stop")  otype = ORDER_TYPE_SELL_STOP;
   if(otype == -1) { WriteResponse(resp_path, cid, "error", 0, 0, 0, "bad side/order_type"); return; }
   if(price <= 0)  { WriteResponse(resp_path, cid, "error", 0, 0, 0, "missing price"); return; }
   if(!ValidateOrder(symbol, volume, price, sl, tp, otype, vol, err)
      || !ValidateStops(symbol, side == "buy", sl, tp, err))
   {
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, err);
      return;
   }
   bool ok = false;
   if(otype == ORDER_TYPE_BUY_LIMIT)   ok = trade.BuyLimit(vol, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(otype == ORDER_TYPE_BUY_STOP)    ok = trade.BuyStop (vol, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(otype == ORDER_TYPE_SELL_LIMIT)  ok = trade.SellLimit(vol, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(otype == ORDER_TYPE_SELL_STOP)   ok = trade.SellStop (vol, price, symbol, sl, tp, ORDER_TIME_GTC, 0, cid);
   if(ok && trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      WriteResponse(resp_path, cid, "pending", (long)trade.ResultOrder(), price, vol, "pending placed", DigitsOf(symbol));
      JournalAdd(cid);
   }
   else
      WriteResponse(resp_path, cid, "rejected", 0, 0, 0, trade.ResultRetcodeDescription());
}

void DoModify(string cid, long ticket, double sl, double tp, string resp_path)
{
   // Always allowed: modifying stops is de-risking and must never be blocked.
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
   // Magic-scoped by default: a shared account's manual trades and other
   // strategies survive our emergency floors unless FlattenAccountWide=true.
   bool closed_any = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!FlattenAccountWide && PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
      if(trade.PositionClose(tk)) closed_any = true;
   }
   for(int j = OrdersTotal() - 1; j >= 0; j--)
   {
      ulong tk = OrderGetTicket(j);
      if(tk == 0) continue;
      if(!FlattenAccountWide && OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
      if(trade.OrderDelete(tk)) closed_any = true;
   }
   // Only audit when there was something to do — a latched condition otherwise
   // spams the log on every 200ms tick.
   if(closed_any) Audit("flatten_all", reason);
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
//| Processed-id journal (restart-safe idempotency)                  |
//+------------------------------------------------------------------+
void LoadJournal()
{
   int h = FileOpen(g_state + "\\processed_ids.log",
                    FILE_READ | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   while(!FileIsEnding(h) && g_seen_count < JOURNAL_CAP)
   {
      string s = FileReadString(h);
      StringTrimLeft(s); StringTrimRight(s);
      if(s != "") { g_seen_ids[g_seen_count % JOURNAL_CAP] = s; g_seen_count++; }
   }
   FileClose(h);
}

void JournalAdd(string cid)
{
   int slot = g_seen_count % JOURNAL_CAP;
   g_seen_ids[slot] = cid;
   g_seen_count++;
   int h = FileOpen(g_state + "\\processed_ids.log",
                    FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, cid + "\n");
   FileClose(h);
}

bool JournalHas(string cid)
{
   int n = (g_seen_count < JOURNAL_CAP) ? g_seen_count : JOURNAL_CAP;
   for(int i = 0; i < n; i++)
      if(g_seen_ids[i] == cid) return true;
   return false;
}

//+------------------------------------------------------------------+
//| State / heartbeat / audit reporting                              |
//+------------------------------------------------------------------+
int DigitsOf(string symbol)
{
   int d = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   return(d > 0 ? d : _Digits);
}

void WriteState()
{
   string acct = "login=" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "\n"
               + "balance=" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + "\n"
               + "equity=" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + "\n"
               + "margin_free=" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + "\n"
               + "currency=" + AccountInfoString(ACCOUNT_CURRENCY) + "\n"
               + "trade_mode=" + IntegerToString((int)AccountInfoInteger(ACCOUNT_TRADE_MODE)) + "\n"
               + "kill_flag=" + (g_kill_flag ? "1" : "0") + "\n"
               + "day_blocked=" + (g_day_blocked ? "1" : "0") + "\n"
               + "hb_lost=" + (g_hb_lost ? "1" : "0") + "\n"
               + "emergency=" + (BlockedForNewRisk() ? "1" : "0") + "\n"
               + "ts=" + TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n";
   WriteFileAtomic(g_state + "\\account.state", acct);

   // SYMBOL|qty|avg|magic — per-symbol digits (chart _Digits is wrong for
   // multi-symbol books); Python filters by its own magic.
   string pos = "";
   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      string sym = PositionGetString(POSITION_SYMBOL);
      double q = PositionGetDouble(POSITION_VOLUME);
      if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL) q = -q;
      pos += sym + "|" + DoubleToString(q, 2) + "|"
           + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), DigitsOf(sym)) + "|"
           + IntegerToString((int)PositionGetInteger(POSITION_MAGIC)) + "\n";
   }
   WriteFileAtomic(g_state + "\\positions.state", pos);
}

void WriteHeartbeat()
{
   WriteFileAtomic(g_state + "\\ea_heartbeat",
                   TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n");
}

void WriteResponse(string path, string cid, string status, long ticket,
                   double fill_price, double fill_volume, string message, int digits = 0)
{
   int dg = (digits > 0) ? digits : _Digits;
   string r = "id=" + cid + "\n"
            + "status=" + status + "\n"
            + "ticket=" + IntegerToString(ticket) + "\n"
            + "fill_price=" + DoubleToString(fill_price, dg) + "\n"
            + "fill_volume=" + DoubleToString(fill_volume, 2) + "\n"
            + "message=" + message + "\n"
            + "ts=" + TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\n";
   WriteFileAtomic(path, r);          // atomic: Python never reads a partial response
}

void Audit(string event, string detail)
{
   // Rotate at ~4MB so a long-running terminal never writes an unbounded log.
   int h = FileOpen(g_audit, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return;
   if(FileSize(h) > 4 * 1024 * 1024)
   {
      FileClose(h);
      FileMove(g_audit, FILE_COMMON, g_audit + ".old", FILE_COMMON | FILE_REWRITE);
      h = FileOpen(g_audit, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
      if(h == INVALID_HANDLE) return;
   }
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, TimeToString(TimeGMT(), TIME_DATE | TIME_SECONDS) + "\t" + event
                      + "\t" + detail + "\n");
   FileClose(h);
}

//+------------------------------------------------------------------+
//| File / parse helpers                                             |
//+------------------------------------------------------------------+
bool WriteFileAtomic(string path, string content)
{
   string tmp = path + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_COMMON);
   if(h == INVALID_HANDLE) return(false);
   FileWriteString(h, content);
   FileClose(h);
   // Windows: a concurrent reader can hold the target open — retry briefly
   // rather than silently leaving stale content (the old failure mode).
   for(int attempt = 0; attempt < 5; attempt++)
   {
      if(FileMove(tmp, FILE_COMMON, path, FILE_COMMON | FILE_REWRITE)) return(true);
      Sleep(50);
   }
   Audit("write_stale", path);   // surfaced; reader will see previous content
   return(false);
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
   return(StringToTime(s));   // "YYYY.MM.DD HH:MM:SS" GMT on both sides
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
