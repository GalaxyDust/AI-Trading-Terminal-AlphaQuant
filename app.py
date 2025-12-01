import streamlit as st
import numpy as np
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from GoogleNews import GoogleNews
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import streamlit.components.v1 as components
import time

# --- CONFIGURATION ---
st.set_page_config(
    page_title="AlphaQuant Prime", 
    page_icon="💎", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CSS PREMIUM ---
st.markdown("""
<style>
    .stApp { background-color: #0b0e11; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .glass-card {
        background: #15191e; border: 1px solid #2a2e39; border-radius: 8px; padding: 20px; margin-bottom: 15px;
    }
    .signal-badge {
        font-size: 28px; font-weight: 800; text-align: center; padding: 15px; border-radius: 8px; letter-spacing: 2px;
    }
    .sig-buy { background: rgba(0, 255, 127, 0.15); color: #00ff7f; border: 1px solid #00ff7f; }
    .sig-sell { background: rgba(255, 0, 60, 0.15); color: #ff003c; border: 1px solid #ff003c; }
    .sig-wait { background: rgba(255, 215, 0, 0.15); color: #ffd700; border: 1px solid #ffd700; }
    .price-level { font-family: 'Courier New', monospace; font-size: 16px; }
    .label-lvl { font-size: 12px; color: #888; text-transform: uppercase; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# --- ANALYTICS ENGINE (ROBUST VERSION) ---
@st.cache_data(ttl=300)
def run_analysis(symbol, keyword):
    # 1. NEWS SENTIMENT
    try:
        googlenews = GoogleNews(lang='en', region='US', period='1d')
        googlenews.search(keyword)
        results = googlenews.result()
        analyzer = SentimentIntensityAnalyzer()
        
        score_total = 0
        headlines = []
        # Ambil max 3 berita valid
        for item in results[:3]: 
            if len(item['title']) > 10:
                s = analyzer.polarity_scores(item['title'])['compound']
                score_total += s
                headlines.append(item['title'])
        
        sent_score = score_total / len(headlines) if headlines else 0
    except:
        sent_score = 0
        headlines = ["Real-time news data unavailable."]

    # 2. TECHNICAL DATA (FIX ERROR DISINI)
    # Kita ambil 2 tahun (2y) agar EMA 200 bisa dihitung valid
    df = yf.download(symbol, period='2y', interval='1d', progress=False)
    
    # Fix MultiIndex Column (Masalah Yfinance Baru)
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    
    # Cek apakah data cukup
    if len(df) < 205:
        return 50, 0, 0, 0, ["Insufficient Data for Tech Analysis"], 0

    # Indicators
    df['EMA_200'] = ta.ema(df['Close'], length=200)
    df['RSI'] = ta.rsi(df['Close'], length=14)
    df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
    
    # 3. SCORING LOGIC
    # Ambil data terakhir yang valid (drop NaN)
    df_clean = df.dropna()
    if df_clean.empty:
         return 50, 0, 0, 0, ["Data Error"], 0

    price = df_clean['Close'].iloc[-1]
    ema = df_clean['EMA_200'].iloc[-1]
    rsi = df_clean['RSI'].iloc[-1]
    atr = df_clean['ATR'].iloc[-1]
    
    score = 50 # Base Score
    
    # Technical Weight
    if price > ema: score += 20
    else: score -= 20
    
    if rsi < 30: score += 15
    elif rsi > 70: score -= 15
    
    # Fundamental Weight (Max +/- 20 poin)
    score += (sent_score * 20) 
    
    return score, price, atr, sent_score, headlines, ema

# --- ASSET CONFIG ---
ASSETS = {
    "BITCOIN (BTC)": {"sym": "BTC-USD", "kw": "Bitcoin Crypto Market", "tv": "BINANCE:BTCUSDT"},
    "GOLD (XAU/USD)": {"sym": "GC=F", "kw": "Gold Price Economy", "tv": "OANDA:XAUUSD"},
    "ETHEREUM (ETH)": {"sym": "ETH-USD", "kw": "Ethereum Crypto", "tv": "BINANCE:ETHUSDT"},
    "GBP/USD": {"sym": "GBPUSD=X", "kw": "GBP USD Forex", "tv": "FX:GBPUSD"},
    "EUR/USD": {"sym": "EURUSD=X", "kw": "EUR USD Forex", "tv": "FX:EURUSD"},
    "NASDAQ 100": {"sym": "NQ=F", "kw": "Nasdaq Stock Market", "tv": "NDX"},
}

# --- UI LAYOUT ---

# 1. TOP SELECTOR (Auto-Update Logic)
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    selected_label = st.selectbox(
        "Select Asset:", 
        list(ASSETS.keys()),
        index=0, # Default BTC
        label_visibility="collapsed"
    )

current = ASSETS[selected_label]

# --- EXECUTE ANALYSIS (AUTO RUN) ---
# Kode ini jalan otomatis setiap kali dropdown berubah
with st.spinner(f"⚡ Analyzing {selected_label} Institution Data..."):
    score, price, atr, sentiment, news, ema = run_analysis(current['sym'], current['kw'])

    # Logic Keputusan
    action = "WAIT / NEUTRAL"
    css = "sig-wait"
    direction = 0
    
    if score >= 65:
        action = "LONG / BUY"
        css = "sig-buy"
        direction = 1
    elif score <= 35:
        action = "SHORT / SELL"
        css = "sig-sell"
        direction = -1

    # Hitung Level
    if direction != 0 and price > 0:
        sl = price - (atr * 1.5 * direction)
        tp1 = price + (atr * 1.5 * direction)
        tp2 = price + (atr * 2.5 * direction)
        tp3 = price + (atr * 4.0 * direction)
        
        # Probabilitas
        prob = min(abs(score - 50) * 2 + 20, 95)
    else:
        sl = tp1 = tp2 = tp3 = 0
        prob = 0

# --- DASHBOARD VISUALIZATION ---

# CHART SECTION
st.markdown(f"### 📊 {selected_label} Live Chart")
components.html(
    f"""
    <div class="tradingview-widget-container">
      <div id="tradingview_chart"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {{
        "width": "100%",
        "height": 500,
        "symbol": "{current['tv']}",
        "interval": "D",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_top_toolbar": false,
        "container_id": "tradingview_chart"
      }}
      );
      </script>
    </div>
    """,
    height=500
)

# AI PANEL SECTION
col_res, col_data = st.columns([1, 1.5])

with col_res:
    st.markdown("### 🤖 AI Verdict")
    st.markdown(f"<div class='glass-card'>", unsafe_allow_html=True)
    
    # SIGNAL BADGE
    st.markdown(f"<div class='signal-badge {css}'>{action}</div>", unsafe_allow_html=True)
    st.write("")
    
    # SCORE BAR
    st.write(f"**Confidence Score:** {score:.1f}/100")
    st.progress(int(score))
    
    if direction != 0:
        st.markdown("---")
        st.markdown(f"""
        <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
            <div><span class='label-lvl'>ENTRY ZONE</span><br><b class='price-level' style='color:#00AAFF'>${price:,.2f}</b></div>
            <div style='text-align:right'><span class='label-lvl'>STOP LOSS</span><br><b class='price-level' style='color:#FF4444'>${sl:,.2f}</b></div>
        </div>
        """, unsafe_allow_html=True)
        
        # TP LEVELS
        st.markdown(f"<div style='margin-bottom:5px'><span class='label-lvl'>TP 1 (Conservative)</span> <span style='float:right; color:#00ff7f'>${tp1:,.2f}</span></div>", unsafe_allow_html=True)
        st.progress(int(prob))
        
        st.markdown(f"<div style='margin-bottom:5px; margin-top:10px'><span class='label-lvl'>TP 2 (Standard)</span> <span style='float:right; color:#00ff7f'>${tp2:,.2f}</span></div>", unsafe_allow_html=True)
        st.progress(int(prob * 0.85))
        
        st.markdown(f"<div style='margin-bottom:5px; margin-top:10px'><span class='label-lvl'>TP 3 (Moonbag)</span> <span style='float:right; color:#00ff7f'>${tp3:,.2f}</span></div>", unsafe_allow_html=True)
        st.progress(int(prob * 0.6))
        
    st.markdown("</div>", unsafe_allow_html=True)

with col_data:
    st.markdown("### 🧠 Logic & Data")
    
    # NEWS PANEL
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.caption("FUNDAMENTAL SENTIMENT")
    if sentiment > 0.05:
        st.markdown("<h4 style='color:#00ff7f'>BULLISH NEWS CYCLE</h4>", unsafe_allow_html=True)
    elif sentiment < -0.05:
        st.markdown("<h4 style='color:#ff003c'>BEARISH NEWS CYCLE</h4>", unsafe_allow_html=True)
    else:
        st.markdown("<h4 style='color:#ffd700'>NEUTRAL / MIXED</h4>", unsafe_allow_html=True)
        
    for h in news:
        st.markdown(f"<li style='font-size:13px; color:#aaa'>{h}</li>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # TECHNICAL PANEL
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.caption("TECHNICAL STRUCTURE")
    
    trend_txt = "✅ UPTREND (Above EMA 200)" if price > ema else "🔻 DOWNTREND (Below EMA 200)"
    
    st.markdown(f"<b>{trend_txt}</b>", unsafe_allow_html=True)
    st.markdown(f"<b>Volatility (ATR): ${atr:,.2f}</b>", unsafe_allow_html=True)
    
    if direction == 0:
        st.info("⚠️ AI Reason: No clear confluence > 80% found. Capital preservation mode.")
    else:
        st.success("✅ AI Reason: Strong alignment between News Sentiment and Technical Trend.")
        
    st.markdown("</div>", unsafe_allow_html=True)
