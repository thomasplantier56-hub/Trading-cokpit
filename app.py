import csv
import datetime
import os
import time
import feedparser
import numpy as np
import pandas as pd
import requests
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf

# Auto-Refresh
try:
    from streamlit_autorefresh import st_autorefresh

    has_autorefresh = True
except ImportError:
    has_autorefresh = False

# Configuration Streamlit Mobile & Dark Mode
st.set_page_config(
    page_title="Cockpit Futures USDT Pro",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #080A0E; color: #FAFAFA; }
    .metric-card { background-color: #12161F; border-radius: 8px; padding: 12px; border-left: 4px solid #2962FF; margin-bottom: 8px; }
    .profile-card { background-color: #161B26; border-radius: 8px; padding: 12px; border: 1px solid #2A3245; margin-bottom: 12px; }
    .alert-card-long { background-color: #082618; border-radius: 8px; padding: 14px; border-left: 5px solid #00E676; margin-bottom: 10px; }
    .alert-card-short { background-color: #2D0C13; border-radius: 8px; padding: 14px; border-left: 5px solid #FF1744; margin-bottom: 10px; }
    .opt-price { color: #FFD700; font-size: 18px; font-weight: bold; }
    .tp-runner { color: #00E676; font-size: 16px; font-weight: bold; }
    .timer-badge { background-color: #1F2430; color: #00E676; padding: 3px 8px; border-radius: 5px; font-size: 13px; font-weight: bold; }
    .danger-liq { background-color: #4A0000; border-radius: 8px; padding: 10px; border: 1px solid #FF1744; color: #FFF; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)

FICHIER_JOURNAL = "journal_trading.csv"
PAIRES_RADAR = [
    "SOL-USD",
    "BTC-USD",
    "ETH-USD",
    "XRP-USD",
    "ZEC-USD",
    "PIPPIN-USD",
    "BNB-USD",
]
analyzer = SentimentIntensityAnalyzer()

if "memoire_signaux" not in st.session_state:
    st.session_state.memoire_signaux = {}
if "profil_precedent" not in st.session_state:
    st.session_state.profil_precedent = None


def formater_prix(p):
    if p is None:
        return "N/A"
    if p < 0.1:
        return f"{p:.5f}"
    elif p < 1.0:
        return f"{p:.4f}"
    elif p < 10.0:
        return f"{p:.3f}"
    else:
        return f"{p:.2f}"


if not os.path.exists(FICHIER_JOURNAL):
    with open(FICHIER_JOURNAL, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Date",
                "Paire",
                "Sens",
                "Prix Entree",
                "Stop Loss",
                "Take Profit",
                "Marge (USDT)",
                "Levier",
                "Resultat",
                "PnL (USDT)",
            ]
        )


@st.cache_data(ttl=30)
def charger_fear_and_greed():
    try:
        res = requests.get(
            "https://api.alternative.me/fng/?limit=1", timeout=3
        ).json()
        return int(res["data"][0]["value"]), res["data"][0][
            "value_classification"
        ]
    except Exception:
        return 50, "Neutre"


@st.cache_data(ttl=60)
def charger_news_ia():
    try:
        flux = feedparser.parse(
            "https://news.google.com/rss/search?q=crypto+bitcoin+solana+when:2d&hl=en-US&gl=US&ceid=US:en"
        )
        articles, scores = [], []
        for entry in flux.entries[:4]:
            titre = entry.title
            compound = analyzer.polarity_scores(titre)["compound"]
            scores.append(compound)
            tag = (
                "🟢 HAUSSIER"
                if compound >= 0.15
                else ("🔴 BAISSIER" if compound <= -0.15 else "⚪ NEUTRE")
            )
            articles.append((tag, titre))
        score_ia = int(np.clip(5.5 + (np.mean(scores) * 4.5), 1, 10))
        return score_ia, articles
    except Exception:
        return 5, []


# Moteur avec TP Échelonné (TP1 Sécurité + TP2 Runner Ambitieux)
@st.cache_data(ttl=10)
def analyser_marche_profil_reel(profil_nom):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)

    if "Conservateur" in profil_nom:
        intervalle = "15m"
        periode = "5d"
        lookback = 30
        mult_sl = 0.50
        mult_tp1 = 2.0
        mult_tp2 = 4.0  # R/R 1:4
    elif "Intraday" in profil_nom:
        intervalle = "5m"
        periode = "2d"
        lookback = 20
        mult_sl = 0.40
        mult_tp1 = 2.0
        mult_tp2 = 3.5
    elif "Scalping" in profil_nom:
        intervalle = "5m"
        periode = "2d"
        lookback = 10
        mult_sl = 0.30
        mult_tp1 = 1.8
        mult_tp2 = 3.5
    else:  # Ultra-Scalp
        intervalle = "1m"
        periode = "1d"
        lookback = 8
        mult_sl = 0.25
        mult_tp1 = 1.8
        mult_tp2 = 3.8  # Objectif Runner ambitieux sur 1m !

    data = yf.download(
        " ".join(PAIRES_RADAR),
        interval=intervalle,
        period=periode,
        group_by="ticker",
        auto_adjust=True,
        progress=False,
    )
    resultats = []

    for paire in PAIRES_RADAR:
        try:
            df = (
                data[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else data.dropna()
            )
            if len(df) < 30:
                continue

            prix = float(df["Close"].iloc[-1])
            open_p = float(df["Open"].iloc[-1])
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])

            high_s = float(df["High"].iloc[-lookback:-1].max())
            low_s = float(df["Low"].iloc[-lookback:-1].min())

            df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
            ema_50 = float(df["EMA_50"].iloc[-1])

            df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
            df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
            ema_9 = float(df["EMA_9"].iloc[-1])
            ema_21 = float(df["EMA_21"].iloc[-1])

            d = df["Close"].diff()
            g = d.where(d > 0, 0).rolling(7 if "Ultra" in profil_nom else 14).mean()
            l = (
                (-d.where(d < 0, 0))
                .rolling(7 if "Ultra" in profil_nom else 14)
                .mean()
            )
            rsi = float((100 - (100 / (1 + (g / l)))).iloc[-1])

            hl = df["High"] - df["Low"]
            hc = (df["High"] - df["Close"].shift()).abs()
            lc = (df["Low"] - df["Close"].shift()).abs()
            atr = float(
                pd.concat([hl, hc, lc], axis=1)
                .max(axis=1)
                .rolling(14)
                .mean()
                .iloc[-1]
            )

            sweep_h = any(
                df["High"].iloc[-i] > high_s and df["Close"].iloc[-i] < high_s
                for i in range(1, 3)
            )
            sweep_l = any(
                df["Low"].iloc[-i] < low_s and df["Close"].iloc[-i] > low_s
                for i in range(1, 3)
            )

            fvg_bear = (df["Low"].iloc[-3] > high) and (
                (df["Low"].iloc[-3] - high) > (atr * 0.15)
            )
            fvg_bull = (low > df["High"].iloc[-3]) and (
                (low - df["High"].iloc[-3]) > (atr * 0.15)
            )

            signal = None
            opt_p, sl, tp1, tp2 = None, None, None, None
            motif = ""

            # 🛡️ 1. CONSERVATEUR (15m x20)
            if "Conservateur" in profil_nom:
                if prix < ema_50 and sweep_h and rsi >= 65 and (prix < open_p):
                    signal = "🔴 SHORT"
                    motif = "SMC Majeur 15m"
                    opt_p = high_s
                    dist_sl = max(high - opt_p + (0.05 * atr), mult_sl * atr)
                    sl = opt_p + dist_sl
                    tp1 = opt_p - (mult_tp1 * dist_sl)
                    tp2 = opt_p - (mult_tp2 * dist_sl)
                elif (
                    prix > ema_50
                    and sweep_l
                    and rsi <= 35
                    and (prix > open_p)
                ):
                    signal = "🟢 LONG"
                    motif = "SMC Majeur 15m"
                    opt_p = low_s
                    dist_sl = max(opt_p - low + (0.05 * atr), mult_sl * atr)
                    sl = opt_p - dist_sl
                    tp1 = opt_p + (mult_tp1 * dist_sl)
                    tp2 = opt_p + (mult_tp2 * dist_sl)

            # ⚖️ 2. INTRADAY (5m x50)
            elif "Intraday" in profil_nom:
                if en_killzone:
                    if (sweep_h or fvg_bear) and (prix < open_p) and rsi >= 60:
                        signal = "🔴 SHORT"
                        motif = "Killzone Session"
                        opt_p = high_s if sweep_h else prix
                        dist_sl = max(high - opt_p + (0.05 * atr), mult_sl * atr)
                        sl = opt_p + dist_sl
                        tp1 = opt_p - (mult_tp1 * dist_sl)
                        tp2 = opt_p - (mult_tp2 * dist_sl)
                    elif (
                        (sweep_l or fvg_bull)
                        and (prix > open_p)
                        and rsi <= 40
                    ):
                        signal = "🟢 LONG"
                        motif = "Killzone Session"
                        opt_p = low_s if sweep_l else prix
                        dist_sl = max(opt_p - low + (0.05 * atr), mult_sl * atr)
                        sl = opt_p - dist_sl
                        tp1 = opt_p + (mult_tp1 * dist_sl)
                        tp2 = opt_p + (mult_tp2 * dist_sl)

            # ⚡ 3. SCALPING (5m x100)
            elif "Scalping" in profil_nom:
                if (sweep_h or fvg_bear or (ema_9 < ema_21 and rsi >= 62)) and (
                    prix < open_p
                ):
                    signal = "🔴 SHORT"
                    motif = "Scalp 5m Momentum"
                    opt_p = prix
                    dist_sl = max(high - prix + (0.04 * atr), mult_sl * atr)
                    sl = prix + dist_sl
                    tp1 = prix - (mult_tp1 * dist_sl)
                    tp2 = prix - (mult_tp2 * dist_sl)
                elif (
                    sweep_l or fvg_bull or (ema_9 > ema_21 and rsi <= 38)
                ) and (prix > open_p):
                    signal = "🟢 LONG"
                    motif = "Scalp 5m Momentum"
                    opt_p = prix
                    dist_sl = max(prix - low + (0.04 * atr), mult_sl * atr)
                    sl = prix - dist_sl
                    tp1 = prix + (mult_tp1 * dist_sl)
                    tp2 = prix + (mult_tp2 * dist_sl)

            # 🔥 4. ULTRA-SCALP (1m x150)
            else:
                if (sweep_h or fvg_bear or rsi >= 58) and (
                    prix < open_p or ema_9 < ema_21
                ):
                    signal = "🔴 SHORT"
                    motif = "Micro-Scalp 1m"
                    opt_p = prix
                    dist_sl = max(high - prix + (0.03 * atr), mult_sl * atr)
                    sl = prix + dist_sl
                    tp1 = prix - (mult_tp1 * dist_sl)
                    tp2 = prix - (
                        mult_tp2 * dist_sl
                    )  # Objectif Runner 1:3.8 !
                elif (sweep_l or fvg_bull or rsi <= 42) and (
                    prix > open_p or ema_9 > ema_21
                ):
                    signal = "🟢 LONG"
                    motif = "Micro-Scalp 1m"
                    opt_p = prix
                    dist_sl = max(prix - low + (0.03 * atr), mult_sl * atr)
                    sl = prix - dist_sl
                    tp1 = prix + (mult_tp1 * dist_sl)
                    tp2 = prix + (mult_tp2 * dist_sl)

            nom_paire = f"{paire.split('-')[0]}/USDT"
            resultats.append(
                {
                    "Paire": nom_paire,
                    "Prix": prix,
                    "Signal_Detecte": signal,
                    "Motif": motif,
                    "Opt_Price": opt_p,
                    "SL": sl,
                    "TP1": tp1,
                    "TP2": tp2,
                    "RSI": f"{rsi:.1f}",
                    "Intervalle": intervalle,
                }
            )
        except Exception:
            continue
    return resultats


# ==========================================================
# 🎛️ LE CURSEUR MAÎTRE
# ==========================================================
st.title("🎛️ Cockpit Futures USDT Pro")

profil = st.select_slider(
    "👉 Réglez votre style de trading :",
    options=[
        "🛡️ Conservateur (15m x20)",
        "⚖️ Intraday (5m x50)",
        "⚡ Scalping (5m x100)",
        "🔥 Ultra-Scalp (1m x150)",
    ],
    value="⚡ Scalping (5m x100)",
)

if st.session_state.profil_precedent != profil:
    st.session_state.memoire_signaux = {}
    st.session_state.profil_precedent = profil
    st.cache_data.clear()

if "Conservateur" in profil:
    levier_suggere = 20
    duree_memoire = 600
    unite_temps = "15m"
    desc = "🛡️ **Conservateur (x20) :** Structure 15m. TP1 pour sécuriser + TP2 Runner 1:4."
elif "Intraday" in profil:
    levier_suggere = 50
    duree_memoire = 300
    unite_temps = "5m"
    desc = "⚖️ **Intraday (x50) :** Killzones Londres/NY. TP1 rapide + TP2 Runner 1:3.5."
elif "Scalping" in profil:
    levier_suggere = 100
    duree_memoire = 180
    unite_temps = "5m"
    desc = "⚡ **Scalping (x100) :** Scalping 5m dynamique. Sorties échelonnées pour maximiser le gain."
else:
    levier_suggere = 150
    duree_memoire = 120
    unite_temps = "1m"
    desc = "🔥 **Ultra-Scalp (x150) :** Flux 1m direct. TP1 (Breakeven immédiat) + TP2 Runner pour capter les vraies impulsions (+50 à +120 USDT)."

st.markdown(f'<div class="profile-card">{desc}</div>', unsafe_allow_html=True)

# Contrôles Auto-Refresh
col_ref, col_time = st.columns([1, 1])
with col_ref:
    activer_auto = st.toggle("🔄 Auto-Refresh Live", value=True)
    if activer_auto:
        sec = 5 if "Ultra" in profil else 10
        if has_autorefresh:
            st_autorefresh(interval=sec * 1000, key="loop_master_v3")
with col_time:
    maintenant_ts = time.time()
    st.caption(
        f"🕒 Heure : **{datetime.datetime.now().strftime('%H:%M:%S')}** | Unité : **{unite_temps}** | Levier : **x{levier_suggere}**"
    )

# ==========================================================
# 🧠 MÉMOIRE PROPRE DES SIGNAUX
# ==========================================================
donnees_marche = analyser_marche_profil_reel(profil)

for d in donnees_marche:
    paire = d["Paire"]
    if d["Signal_Detecte"] is not None:
        st.session_state.memoire_signaux[paire] = {
            "signal": d["Signal_Detecte"],
            "motif": d["Motif"],
            "prix_entree": d["Opt_Price"],
            "sl": d["SL"],
            "tp1": d["TP1"],
            "tp2": d["TP2"],
            "timestamp": maintenant_ts,
        }

signaux_a_supprimer = [
    p
    for p, info in st.session_state.memoire_signaux.items()
    if maintenant_ts - info["timestamp"] > duree_memoire
]
for p in signaux_a_supprimer:
    del st.session_state.memoire_signaux[p]

# ==========================================================
# 📱 ONGLETS
# ==========================================================
tab_radar, tab_calc, tab_marche, tab_journal = st.tabs(
    [
        "⚡ Signaux Actifs & Radar",
        f"🧮 Calculateur (x{levier_suggere})",
        "🌍 Baromètre IA",
        "📊 Journal Trades",
    ]
)

# 1. RADAR AVEC TP1 & TP2 RUNNER
with tab_radar:
    if st.session_state.memoire_signaux:
        st.subheader(f"🎯 Opportunités Validées ({unite_temps}) :")
        for paire, info in list(st.session_state.memoire_signaux.items()):
            temps_restant = int(
                duree_memoire - (maintenant_ts - info["timestamp"])
            )
            minutes_rest = max(0, temps_restant // 60)
            secondes_rest = max(0, temps_restant % 60)

            classe = (
                "alert-card-long"
                if "LONG" in info["signal"]
                else "alert-card-short"
            )
            st.markdown(
                f"""
            <div class="{classe}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h3>⚡ {paire} : {info['signal']} ({info['motif']})</h3>
                    <span class="timer-badge">⏱️ Valide : {minutes_rest}m {secondes_rest:02d}s</span>
                </div>
                🎯 <span class="opt-price">ENTRÉE OPTIMALE (Ordre Limit) : {formater_prix(info['prix_entree'])} USDT</span><br>
                🛑 <b>Stop-Loss Obligatoire :</b> {formater_prix(info['sl'])} USDT<br>
                💰 <b>TP1 (Sécuriser 50% + Breakeven) :</b> {formater_prix(info['tp1'])} USDT<br>
                🚀 <span class="tp-runner">TP2 RUNNER (Gros Coup 1:3.8) : {formater_prix(info['tp2'])} USDT</span><br>
                <small>💡 <i>Méthode Pro : Clôturez 50% au TP1 et remontez votre Stop à Breakeven pour laisser courir le TP2 sans risque !</i></small>
            </div>
            """,
                unsafe_allow_html=True,
            )
        st.markdown("---")

    lignes_tableau = []
    for d in donnees_marche:
        paire = d["Paire"]
        statut = (
            st.session_state.memoire_signaux[paire]["signal"]
            if paire in st.session_state.memoire_signaux
            else "VEILLE ⚪"
        )
        lignes_tableau.append(
            {
                "Paire": paire,
                "Prix Actuel": formater_prix(d["Prix"]),
                "Statut": statut,
                "RSI": d["RSI"],
                "Unité": d["Intervalle"],
            }
        )

    st.subheader(f"📊 Surveillance des 7 Paires en direct ({unite_temps})")
    st.dataframe(pd.DataFrame(lignes_tableau), hide_index=True)

# 2. CALCULATEUR AVEC TP ÉCHELONNÉ
with tab_calc:
    st.subheader(
        f"🧮 Calculateur de Payouts (Levier x{levier_suggere} | 100 USDT)"
    )

    col_p, col_s = st.columns(2)
    liste_options = [f"{p.split('-')[0]}/USDT" for p in PAIRES_RADAR]
    paire = col_p.selectbox("Contrat Futures", liste_options)
    sens = col_s.radio("Sens", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
    is_long = "LONG" in sens

    col_e, col_sl = st.columns(2)
    p_entree = col_e.number_input(
        "🎯 Prix d'Entrée (USDT)", value=106.20, step=0.01, format="%.5f"
    )
    p_sl = col_sl.number_input(
        "🛑 Stop-Loss (USDT)", value=105.90, step=0.01, format="%.5f"
    )

    col_m, col_lev = st.columns(2)
    marge_fixe = col_m.number_input(
        "Marge engagée (USDT)", value=100.0, step=10.0
    )
    levier_choisi = col_lev.slider(
        "Levier", min_value=1, max_value=200, value=levier_suggere
    )

    if (is_long and p_sl < p_entree) or ((not is_long) and p_sl > p_entree):
        distance = abs(p_entree - p_sl)
        pct_dist = distance / p_entree

        notionnel = marge_fixe * levier_choisi
        quantite = notionnel / p_entree
        perte_sl = pct_dist * notionnel

        dist_liq_pct = (1.0 / levier_choisi) * 0.90
        p_liq = (
            p_entree * (1 - dist_liq_pct)
            if is_long
            else p_entree * (1 + dist_liq_pct)
        )
        distance_liq_dollars = abs(p_liq - p_entree)

        tp1 = (
            p_entree + (1.8 * distance)
            if is_long
            else p_entree - (1.8 * distance)
        )
        tp2 = (
            p_entree + (3.8 * distance)
            if is_long
            else p_entree - (3.8 * distance)
        )
        gain_tp1 = (1.8 * distance / p_entree) * notionnel
        gain_tp2 = (3.8 * distance / p_entree) * notionnel

        securite_validee = (p_sl > p_liq) if is_long else (p_sl < p_liq)

        st.markdown("---")
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>📋 Vos Payouts Estimés sur MEXC (x{levier_choisi}) :</h3>
            <b>💵 Marge Engagée :</b> <b>{marge_fixe:.2f} USDT</b> (Position totale : {notionnel:,.2f} USDT)<br>
            <b>🛑 Perte si Stop touché :</b> <span style="color:#FF5252;"><b>-{perte_sl:.2f} USDT</b> ({pct_dist:.2%})</span><br>
            <b>🎯 TP1 (Sécurisation 50%) :</b> <span style="color:#00E676;"><b>+{gain_tp1:.2f} USDT</b></span> ({formater_prix(tp1)} USDT)<br>
            <b>🚀 TP2 RUNNER (Gros Coup 1:3.8) :</b> <span style="font-size:20px; color:#00E676;"><b>+{gain_tp2:.2f} USDT</b></span> ({formater_prix(tp2)} USDT)<br>
            <b>💀 PRIX DE LIQUIDATION :</b> <b>{formater_prix(p_liq)} USDT</b> (Marge de sécurité : {formater_prix(distance_liq_dollars)} USDT)
        </div>
        """,
            unsafe_allow_html=True,
        )

        if securite_validee and (pct_dist < dist_liq_pct * 0.7):
            st.success("✅ SÉCURITÉ VALIDÉE : Stop-Loss bien placé.")
        else:
            st.markdown(
                f"""
            <div class="danger-liq">
                🚨 ATTENTION DANGER LIQUIDATION !<br>
                Votre Stop-Loss est trop éloigné ({pct_dist:.2%}) par rapport à la liquidation ({dist_liq_pct:.2%}).<br>
                Rapprochez votre Stop ou diminuez le levier !
            </div>
            """,
                unsafe_allow_html=True,
            )

        if st.button("💾 Sauvegarder dans mon Journal"):
            with open(
                FICHIER_JOURNAL, mode="a", newline="", encoding="utf-8"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        paire,
                        "LONG" if is_long else "SHORT",
                        f"{p_entree}",
                        f"{p_sl}",
                        f"{tp2}",
                        f"{marge_fixe:.2f}",
                        f"x{levier_choisi}",
                        "EN_COURS",
                        "0.00",
                    ]
                )
            st.success("Trade archivé avec succès !")

# 3. MARCHÉ & NEWS IA
with tab_marche:
    fg_score, fg_sentiment = charger_fear_and_greed()
    score_ia, news = charger_news_ia()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
        <div class="metric-card">
            <h4>📊 Fear & Greed Index</h4>
            <h2>{fg_score} / 100</h2>
            <b>Sentiment :</b> {fg_sentiment}
        </div>
        """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
        <div class="metric-card">
            <h4>🧠 Sentiment IA des News</h4>
            <h2>{score_ia} / 10</h2>
            <b>Tendance :</b> {"RISK-ON 🐂" if score_ia >= 6 else ("RISK-OFF 🐻" if score_ia <= 4 else "NEUTRE ⚪")}
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.subheader("📰 Dernières dépêches mondiales")
    for tag, titre in news:
        st.markdown(f"**{tag}** — {titre}")

# 4. JOURNAL DE TRADES
with tab_journal:
    st.subheader("📊 Historique des Trades USDT")
    if os.path.exists(FICHIER_JOURNAL):
        try:
            df_j = pd.read_csv(
                FICHIER_JOURNAL, encoding="utf-8", encoding_errors="ignore"
            )
        except Exception:
            df_j = pd.read_csv(FICHIER_JOURNAL, encoding="latin1")
        st.dataframe(df_j, hide_index=True)