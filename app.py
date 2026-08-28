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
    page_title="Cockpit Trader Multi-Profils",
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


# Moteur Multi-Timeframes & Multi-Profils
@st.cache_data(ttl=10)
def analyser_marche_profil(profil_nom):
    # Définition dynamique des paramètres selon le curseur
    if "Conservateur" in profil_nom:
        intervalle = "15m"
        periode = "5d"
        lookback = 20
        rsi_h, rsi_b = 68, 32
        fvg_mult = 0.20
        mult_sl = 0.50
        mult_tp = 3.0
    elif "Équilibré" in profil_nom:
        intervalle = "5m"
        periode = "2d"
        lookback = 15
        rsi_h, rsi_b = 64, 36
        fvg_mult = 0.15
        mult_sl = 0.40
        mult_tp = 2.5
    elif "Agressif" in profil_nom:
        intervalle = "5m"
        periode = "2d"
        lookback = 10
        rsi_h, rsi_b = 60, 40
        fvg_mult = 0.12
        mult_sl = 0.30
        mult_tp = 2.5
    else:  # Ultra-Scalper
        intervalle = "1m"
        periode = "1d"
        lookback = 8
        rsi_h, rsi_b = 58, 42
        fvg_mult = 0.08
        mult_sl = 0.25
        mult_tp = 2.0

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
            if len(df) < 20:
                continue

            prix = float(df["Close"].iloc[-1])
            open_p = float(df["Open"].iloc[-1])
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])

            high_s = float(df["High"].iloc[-lookback:-1].max())
            low_s = float(df["Low"].iloc[-lookback:-1].min())

            df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
            df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
            ema_9 = float(df["EMA_9"].iloc[-1])
            ema_21 = float(df["EMA_21"].iloc[-1])

            d = df["Close"].diff()
            g = d.where(d > 0, 0).rolling(7).mean()
            l = (-d.where(d < 0, 0)).rolling(7).mean()
            rsi = float((100 - (100 / (1 + (g / l)))).iloc[-1])

            hl = df["High"] - df["Low"]
            hc = (df["High"] - df["Close"].shift()).abs()
            lc = (df["Low"] - df["Close"].shift()).abs()
            atr = float(
                pd.concat([hl, hc, lc], axis=1)
                .max(axis=1)
                .rolling(10)
                .mean()
                .iloc[-1]
            )

            # Sweeps récents
            sweep_h = any(
                df["High"].iloc[-i] > high_s and df["Close"].iloc[-i] < high_s
                for i in range(1, 4)
            )
            sweep_l = any(
                df["Low"].iloc[-i] < low_s and df["Close"].iloc[-i] > low_s
                for i in range(1, 4)
            )

            # FVG
            fvg_bear = (df["Low"].iloc[-3] > high) and (
                (df["Low"].iloc[-3] - high) > (atr * fvg_mult)
            )
            fvg_bull = (low > df["High"].iloc[-3]) and (
                (low - df["High"].iloc[-3]) > (atr * fvg_mult)
            )

            signal = None
            opt_p, sl, tp = None, None, None
            motif = ""

            # Signaux SHORT
            if (sweep_h or fvg_bear) and (prix < open_p or rsi >= rsi_h):
                signal = "🔴 SHORT"
                motif = "SMC (Sweep / FVG)"
                opt_p = high_s if sweep_h else prix
                dist_sl = max(high - opt_p + (0.04 * atr), mult_sl * atr)
                sl = opt_p + dist_sl
                tp = opt_p - (mult_tp * dist_sl)
            elif ema_9 < ema_21 and rsi >= rsi_h and df["Close"].iloc[-2] > prix:
                signal = "🔴 SHORT"
                motif = "Momentum Rejet"
                opt_p = prix
                dist_sl = max(high - prix + (0.04 * atr), mult_sl * atr)
                sl = prix + dist_sl
                tp = prix - (mult_tp * dist_sl)

            # Signaux LONG
            elif (sweep_l or fvg_bull) and (prix > open_p or rsi <= rsi_b):
                signal = "🟢 LONG"
                motif = "SMC (Sweep / FVG)"
                opt_p = low_s if sweep_l else prix
                dist_sl = max(opt_p - low + (0.04 * atr), mult_sl * atr)
                sl = opt_p - dist_sl
                tp = opt_p + (mult_tp * dist_sl)
            elif ema_9 > ema_21 and rsi <= rsi_b and df["Close"].iloc[-2] < prix:
                signal = "🟢 LONG"
                motif = "Momentum Rebond"
                opt_p = prix
                dist_sl = max(prix - low + (0.04 * atr), mult_sl * atr)
                sl = prix - dist_sl
                tp = prix + (mult_tp * dist_sl)

            nom_paire = f"{paire.split('-')[0]}/USDT"
            resultats.append(
                {
                    "Paire": nom_paire,
                    "Prix": prix,
                    "Signal_Detecte": signal,
                    "Motif": motif,
                    "Opt_Price": opt_p,
                    "SL": sl,
                    "TP": tp,
                    "RSI": f"{rsi:.1f}",
                    "Intervalle": intervalle,
                }
            )
        except Exception:
            continue
    return resultats


# ==========================================================
# 🎛️ LE CURSEUR MAÎTRE DE RISQUE (EN HAUT DE L'ÉCRAN)
# ==========================================================
st.title("🎛️ Cockpit Trader Multi-Profils")

profil = st.select_slider(
    "👉 Réglez votre style de trading :",
    options=[
        "🛡️ Conservateur (Swing x5)",
        "⚖️ Équilibré (Intraday x20)",
        "⚡ Agressif (Scalp 5m x50)",
        "🔥 Ultra-Scalper (1m x150)",
    ],
    value="⚡ Agressif (Scalp 5m x50)",
)

# Configuration dynamique selon le curseur
if "Conservateur" in profil:
    levier_suggere = 5
    duree_memoire = 600  # 10 minutes
    unite_temps = "15m"
    desc = "🛡️ **Mode Conservateur :** Graphiques 15m. Signaux rares et ultra-filtrés. Stop large, zéro stress."
elif "Équilibré" in profil:
    levier_suggere = 20
    duree_memoire = 300  # 5 minutes
    unite_temps = "5m"
    desc = "⚖️ **Mode Équilibré :** Graphiques 5m/15m. Trades de session (Killzones). Bon ratio gains/sécurité."
elif "Agressif" in profil:
    levier_suggere = 50
    duree_memoire = 180  # 3 minutes
    unite_temps = "5m"
    desc = "⚡ **Mode Agressif :** Scalping 5m dynamique. Opportunités régulières, Stop serré (One Candle Rule)."
else:
    levier_suggere = 150
    duree_memoire = 120  # 2 minutes
    unite_temps = "1m"
    desc = "🔥 **Mode Ultra-Scalper :** Flux 1 minute direct. Micro-scalping à haute fréquence, sorties rapides."

st.markdown(f'<div class="profile-card">{desc}</div>', unsafe_allow_html=True)

# Contrôles Auto-Refresh
col_ref, col_time = st.columns([1, 1])
with col_ref:
    activer_auto = st.toggle("🔄 Auto-Refresh Live", value=True)
    if activer_auto:
        sec = 5 if "Ultra" in profil else 10
        if has_autorefresh:
            st_autorefresh(interval=sec * 1000, key="loop_master")
with col_time:
    maintenant_ts = time.time()
    st.caption(
        f"🕒 Heure : **{datetime.datetime.now().strftime('%H:%M:%S')}** | Unité : **{unite_temps}** | Levier suggéré : **x{levier_suggere}**"
    )

# ==========================================================
# 🧠 MÉMOIRE PERSISTANTE DES SIGNAUX
# ==========================================================
donnees_marche = analyser_marche_profil(profil)

for d in donnees_marche:
    paire = d["Paire"]
    if d["Signal_Detecte"] is not None:
        st.session_state.memoire_signaux[paire] = {
            "signal": d["Signal_Detecte"],
            "motif": d["Motif"],
            "prix_entree": d["Opt_Price"],
            "sl": d["SL"],
            "tp": d["TP"],
            "timestamp": maintenant_ts,
            "profil": profil,
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

# 1. RADAR DYNAMIQUE
with tab_radar:
    if st.session_state.memoire_signaux:
        st.subheader(f"🎯 Opportunités Validées ({profil}) :")
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
                🎯 <span class="opt-price">ORDRE LIMIT CONSEILLÉ : {formater_prix(info['prix_entree'])} USDT</span><br>
                🛑 <b>Stop-Loss (One Candle) :</b> {formater_prix(info['sl'])} USDT<br>
                💰 <b>Take-Profit Cible :</b> {formater_prix(info['tp'])} USDT<br>
                <small>💡 <i>Trade en cours ? Laissez le Stop-Loss et Take-Profit agir sur MEXC sans couper manuellement.</i></small>
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

# 2. CALCULATEUR SYNCHRONISÉ AVEC LE PROFIL
with tab_calc:
    st.subheader(f"🧮 Calculateur de Risque (Calibré pour {profil})")

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
            p_entree + (2.0 * distance)
            if is_long
            else p_entree - (2.0 * distance)
        )
        tp2 = (
            p_entree + (2.5 * distance)
            if is_long
            else p_entree - (2.5 * distance)
        )
        gain_tp1 = (2.0 * distance / p_entree) * notionnel
        gain_tp2 = (2.5 * distance / p_entree) * notionnel

        securite_validee = (p_sl > p_liq) if is_long else (p_sl < p_liq)

        st.markdown("---")
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>📋 Ordre MEXC Recommandé (x{levier_choisi}) :</h3>
            <b>💵 Marge Engagée :</b> <span style="font-size:22px; color:#00E676;"><b>{marge_fixe:.2f} USDT</b></span><br>
            <b>🚀 Notionnel Contrôlé :</b> <b>{notionnel:,.2f} USDT</b> ({quantite:.4f} {paire.split('/')[0]})<br>
            <b>🛑 Perte au Stop-Loss :</b> <span style="color:#FF5252;"><b>-{perte_sl:.2f} USDT</b> ({pct_dist:.2%})</span><br>
            <b>🎯 Gain au TP 1:2 :</b> <span style="color:#00E676;"><b>+{gain_tp1:.2f} USDT</b></span> ({formater_prix(tp1)} USDT)<br>
            <b>🎯 Gain au TP 1:2.5 :</b> <span style="color:#00E676;"><b>+{gain_tp2:.2f} USDT</b></span> ({formater_prix(tp2)} USDT)<br>
            <b>💀 PRIX DE LIQUIDATION :</b> <b>{formater_prix(p_liq)} USDT</b> (Distance : {formater_prix(distance_liq_dollars)} USDT)
        </div>
        """,
            unsafe_allow_html=True,
        )

        if securite_validee and (pct_dist < dist_liq_pct * 0.7):
            st.success("✅ SÉCURITÉ VALIDÉE : Stop-Loss placé avant la liquidation.")
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