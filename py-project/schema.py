SCHEMA = {
"batch_job_master":[("job_id","varchar(64)",0,1,None,""),("job_name","varchar(255)",0,0,None,""),("module_name","varchar(255)",0,0,None,""),("class_name","varchar(45)",0,0,None,""),("cron_minute","varchar(45)",0,0,None,""),("cron_hour","varchar(45)",0,0,None,""),("cron_day_of_week","varchar(45)",0,0,None,""),("enabled_flag","varchar(1)",0,0,None,"")],
"master_stock":[("corp_code","varchar(20)",0,1,None,""),("stock_code","varchar(6)",0,0,None,""),("stock_name","varchar(100)",0,0,None,""),("stock_type","varchar(6)",0,0,None,""),("stock_type_yf","varchar(45)",1,0,None,""),("stock_class","varchar(1)",1,0,None,""),("group_code","varchar(45)",1,0,None,""),("created_date","datetime",1,0,None,""),("market_stop","varchar(1)",1,0,None,""),("nxt_flag","varchar(1)",1,0,"N","")],
"stock_batch_log":[("batch_seq","bigint(20)",0,1,None,""),("batch_code","varchar(100)",0,0,None,""),("batch_cnt","int(11)",1,0,None,""),("status","varchar(45)",1,0,None,""),("start_time","datetime",1,0,None,""),("end_time","datetime",1,0,None,""),("desc","varchar(256)",1,0,None,"")],
"stock_sell_request":[("user_id","int(11)",0,1,None,""),("stock_code","varchar(45)",0,1,None,""),("stock_name","varchar(45)",1,0,None,""),("entry_date","varchar(8)",1,0,None,""),("entry_price","decimal(18,8)",1,0,None,""),("hold_qty","decimal(18,8)",1,0,None,""),("memo","varchar(255)",1,0,None,""),("enabled_flag","varchar(1)",0,0,"Y",""),("created_at","datetime",1,0,"CURRENT_TIMESTAMP",""),("updated_at","datetime",1,0,"CURRENT_TIMESTAMP","on update CURRENT_TIMESTAMP")],
"trade_buy_target_stock":[("ymd","varchar(8)",0,1,None,""),("stock_code","varchar(45)",0,1,None,""),("rank_no","int(11)",1,0,None,""),("stock_name","varchar(45)",1,0,None,""),("open","decimal(18,8)",1,0,None,""),("high","decimal(18,8)",1,0,None,""),("low","decimal(18,8)",1,0,None,""),("close","decimal(18,8)",1,0,None,""),("volume","decimal(18,8)",1,0,None,""),("rate","varchar(45)",1,0,None,""),("action_type","varchar(45)",1,0,None,""),("macd_cross","varchar(45)",1,0,None,""),("obv_cross","varchar(45)",1,0,None,""),("is_vol_limit","varchar(45)",1,0,None,""),("is_under_bb_upper","varchar(45)",1,0,None,""),("is_over_on_mid","varchar(45)",1,0,None,""),("is_vol_surge","varchar(45)",1,0,None,""),("is_bb_mid_breakout","varchar(45)",1,0,None,""),("eps","varchar(45)",1,0,None,""),("pbr","varchar(45)",1,0,None,""),("per","varchar(45)",1,0,None,""),("roe","varchar(45)",1,0,None,""),("peg","varchar(45)",1,0,None,""),("score","decimal(6,2)",1,0,None,"")],
"trade_log":[("trade_id","bigint(20)",0,1,None,"auto_increment"),("user_id","int(11)",0,0,None,""),("coin_symbol","varchar(20)",0,0,None,""),("action_type","varchar(5)",0,0,None,""),("order_time","datetime",1,0,None,""),("exec_time","datetime",1,0,None,""),("price","decimal(18,8)",0,0,"0.00000000",""),("quantity","decimal(18,8)",0,0,"0.00000000",""),("total_amount","decimal(18,8)",0,0,"0.00000000",""),("remain_qty","decimal(18,8)",1,0,None,""),("fee","decimal(18,8)",1,0,None,""),("pnl","decimal(18,8)",1,0,None,""),("krw_balance","decimal(18,8)",1,0,None,""),("note","varchar(255)",1,0,None,""),("created_at","datetime",0,0,"CURRENT_TIMESTAMP","")],
"user_detail":[("user_id","int(11)",0,1,None,""),("salt","varchar(16)",0,0,None,""),("pswd","varchar(255)",0,0,None,""),("err_cnt","int(11)",1,0,"0",""),("created_date","datetime",1,0,None,""),("updated_date","datetime",1,0,None,""),("upbit_access_key","varchar(200)",1,0,None,""),("upbit_secret_key","varchar(200)",1,0,None,""),("reset_flag","varchar(1)",1,0,None,""),("kis_access_key","varchar(200)",1,0,None,""),("kis_secret_key","varchar(200)",1,0,None,""),("tele_bot_id","varchar(200)",1,0,None,""),("tele_chat_id","varchar(200)",1,0,None,""),("kis_id","varchar(45)",1,0,None,""),("kis_account","varchar(45)",1,0,None,""),("kis_app_key","varchar(200)",1,0,None,""),("kis_sec_key","varchar(500)",1,0,None,""),("kis_virtual_id","varchar(50)",1,0,None,""),("kis_virtual_account","varchar(50)",1,0,None,""),("kis_vir_app_key","varchar(200)",1,0,None,""),("kis_vir_sec_key","varchar(500)",1,0,None,"")],
"user_interest_groups":[("division","varchar(45)",0,1,None,""),("group_id","int(11)",0,1,None,""),("user_id","int(11)",0,1,None,""),("group_name","varchar(45)",0,0,None,"")],
"user_interest_stocks":[("group_id","int(11)",0,1,None,""),("stock_code","varchar(45)",0,1,None,""),("status","varchar(45)",0,0,None,""),("added_at","datetime",1,0,None,""),("enabled_flag","varchar(1)",1,0,None,""),("curr_balance","decimal(18,8)",1,0,None,"")],
"user_master":[("user_id","int(11)",0,1,None,""),("user_name","varchar(45)",0,0,None,""),("user_phone","varchar(13)",1,0,None,""),("email","varchar(200)",1,0,None,""),("gender","varchar(2)",1,0,None,""),("age","varchar(45)",1,0,None,"")],
"user_wallet":[("user_id","int(11)",0,1,None,""),("user_balance","decimal(18,8)",0,0,None,""),("stock_amount","decimal(18,8)",0,0,"0.00000000",""),("total_asset","decimal(18,8)",0,0,"0.00000000",""),("updated_at","datetime",1,0,None,"")],
}
_tcd_dec=["open","high","low","close","volume"]
_tcd=[("coin","varchar(10)",0,1,None,""),("datetime","varchar(19)",0,1,None,"")]
_tcd+= [(c,"decimal(18,8)",0,0,None,"") for c in _tcd_dec]
for c in ["ema20","ema60","ema120","bb_mid","bb_lower"]: _tcd.append((c,"decimal(18,8)",1,0,None,""))
_tcd.append(("bb_lower_chk","decimal(1,0)",1,0,None,""))
_tcd.append(("bb_upper","decimal(18,8)",1,0,None,""))
_tcd.append(("bb_upper_chk","decimal(1,0)",1,0,None,""))
for c in ["bb_width","bb_width_avg","macd","macd_s","macd_lower_mean","macd_upper_mean","macd_recent_min","macd_recent_max","fs_k","fs_d","roc","atr","obv","obv_signal"]: _tcd.append((c,"decimal(18,8)",1,0,None,""))
_tcd.append(("obv_cross","varchar(1)",1,0,None,""))
for c in ["obv_recent_min","obv_recent_max","rsi","rsi_signal"]: _tcd.append((c,"decimal(18,8)",1,0,None,""))
_tcd.append(("rsi_cross","varchar(1)",1,0,None,""))
for c in ["score_trend","score_momentum","score_volatility","score_volume","score_total"]: _tcd.append((c,"decimal(18,8)",1,0,None,""))
for c in ["watch_action","active_action","regime"]: _tcd.append((c,"varchar(45)",1,0,None,""))
_tcd.append(("bb_mid_breakout","decimal(18,8)",1,0,None,""))
for c in ["macd_g_cross_n","macd_d_cross_n","obv_g_cross_n","obv_d_cross_n"]: _tcd.append((c,"varchar(1)",1,0,None,""))
_tcd.append(("vol_surge_n","decimal(18,8)",1,0,None,""))
_tcd.append(("recent_high","decimal(18,8)",1,0,None,""))
SCHEMA["trade_candle_data"]=_tcd
_uo=[("user_id","int(11)",0,1,None,"")]
for c in ["upbit_push_flag","stock_sell_mail_flag","stock_buy_target_mail_flag","stock_sell_tele_flag"]: _uo.append((c,"varchar(1)",1,0,None,""))
for c in ["buy_confirm","buy_entry","sell_entry","sell_exit"]: _uo.append((c,"int(11)",1,0,None,""))
_uo.append(("user_balance","decimal(18,8)",1,0,None,""))
for c in ["ratio_trend","ratio_momentum","ratio_volatility","ratio_volume"]: _uo.append((c,"decimal(2,2)",1,0,None,""))
_uo.append(("time_frame","varchar(45)",1,0,None,""))
_uo.append(("macd_recent_day","int(2)",1,0,None,""))
_uo.append(("bb_over_recent_day","int(2)",1,0,None,""))
_uo.append(("vol_limit","int(11)",1,0,None,""))
_uo.append(("vol_surge","decimal(4,2)",1,0,None,""))
for c,t in [("s1_stop_loss_pct","decimal(6,4)"),("s1_take_profit_pct","decimal(6,4)"),("s1_max_hold_bars","int(4)"),("s1_rsi_overbought","int(4)"),("s1_rsi_ideal_low","int(4)"),("s1_rsi_ideal_high","int(4)"),("s1_vol_ma_window","int(4)"),("s1_vol_ma_mult","decimal(6,2)"),("s1_regime_window","int(4)"),("s1_regime_threshold","decimal(6,4)"),("s1_strict_need_macd_up","tinyint(1)"),("s1_loose_need_vol_surge","tinyint(1)"),("s1_surge_relax_mult","decimal(6,2)"),("s1_downtrend_surge_bypass","tinyint(1)"),("s1_surge_bypass_mult","decimal(6,2)"),("s1_use_trailing","tinyint(1)"),("s1_trail_basis","varchar(5)"),("s1_trail_activate_pct","decimal(6,4)"),("s1_k_trail_atr","decimal(6,2)"),("s1_trail_floor_pct","decimal(6,4)"),("s1_time_stop_extend","tinyint(1)"),("s1_time_stop_band","decimal(6,4)"),("s1_time_stop_grace","int(4)"),("s1_max_hold_bars_hard","int(4)"),("s1_obv_dead_min_bars","int(4)")]: _uo.append((c,t,1,0,None,""))
SCHEMA["user_options"]=_uo
if __name__=="__main__":
    for t,c in SCHEMA.items(): print(f"{t:26} {len(c)}")
