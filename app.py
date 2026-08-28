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
    page_title="Cockpit Trader Multi-Styles",
    page_icon="🎛️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #080A0E; color: #FAFAFA; }
    .metric-card { background-color: #12161F; border-radius: 8px; padding: 12px; border-left: 4px solid #2962FF; margin-bottom: 8px; }
    .profile-card { background-color: #161B26; border-radius: 8px; padding: 10px; border: 1px solid #2A3245; margin-bottom: 10px; }
    
    /* Cartes Panoramiques */
    .mini-card-conservateur { background-color: #0E1626; border-radius: 8px; padding: 10px; border-top: 4px solid #2979FF; margin-bottom: 8px; min-height: 120px; }
    .mini-card-intraday { background-color: #161124; border-radius: 8px; padding: 10px; border-top: 4px solid #9C27B0; margin-bottom: 8px; min-height: 120px; }
    .mini-card-scalping { background-color: #1C1608; border-radius: 8px; padding: 10px; border-top: 4px solid #FF9100; margin-bottom: 8px; min-height: 120px; }
    .mini-card-ultrascalp { background-color: #21090D; border-radius: 8px; padding: 10px; border-top: 4px solid #FF1744; margin-bottom: 8px; min-height: 120px; }
    
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

# Mémoire Indépendante par Profil
if "memoire_par_profil" not in st.session_state:
    st.session_state.memoire_par_profil = {
        "Conservateur": {},
        "Intraday": {},
        "Scalping": {},
        "Ultra-Scalp": {},
    }


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


# Moteur d'Analyse pour un Profil Spécifique
@st.cache_data(ttl=10)
def analyser_marche_profil_reel(profil_court):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)

    if profil_court == "Conservateur":
        intervalle = "15m"
        periode = "5d"
        lookback = 30
        mult_sl, mult_tp1, mult_tp2 = 0.50, 2.0, 4.0
    elif profil_court == "Intraday":
        intervalle = "5m"
        periode = "2d"
        lookback = 20
        mult_sl, mult_tp1, mult_tp2 = 0.40, 2.0, 3.5
    elif profil_court == "Scalping":
        intervalle = "5m"
        periode = "2d"
        lookback = 10
        mult_sl, mult_tp1, mult_tp2 = 0.30, 1.8, 3.5
    else:  # Ultra-Scalp
        intervalle = "1m"
        periode = "1d"
        lookback = 8
        mult_sl, mult_tp1, mult_tp2 = 0.25, 1.8, 3.8

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
            g = d.where(d > 0, 0).rolling(7 if profil_court == "Ultra-Scalp" else 14).mean()
            l = (
                (-d.where(d < 0, 0))
                .rolling(7 if profil_court == "Ultra-Scalp" else 14)
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

            if profil_court == "Conservateur":
                if prix < ema_50 and sweep_h and rsi >= 65 and (prix < open_p):
                    signal, motif = (
                        "🔴 SHORT",
                        "SMC Majeur 15m",
                    )
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
                    signal, motif = (
                        "🟢 LONG",
                        "SMC Majeur 15m",
                    )
                    opt_p = low_s
                    dist_sl = max(opt_p - low + (0.05 * atr), mult_sl * atr)
                    sl = opt_p - dist_sl
                    tp1 = opt_p + (mult_tp1 * dist_sl)
                    tp2 = opt_p + (mult_tp2 * dist_sl)

            elif profil_court == "Intraday":
                if en_killzone:
                    if (sweep_h or fvg_bear) and (prix < open_p) and rsi >= 60:
                        signal, motif = (
                            "🔴 SHORT",
                            "Killzone 5m",
                        )
                        opt_p = high_s if sweep_h else prix
                        dist_sl = max(
                            high - opt_p + (0.05 * atr), mult_sl * atr
                        )
                        sl = opt_p + dist_sl
                        tp1 = opt_p - (mult_tp1 * dist_sl)
                        tp2 = opt_p - (mult_tp2 * dist_sl)
                    elif (
                        (sweep_l or fvg_bull)
                        and (prix > open_p)
                        and rsi <= 40
                    ):
                        signal, motif = (
                            "🟢 LONG",
                            "Killzone 5m",
                        )
                        opt_p = low_s if sweep_l else prix
                        dist_sl = max(
                            opt_p - low + (0.05 * atr), mult_sl * atr
                        )
                        sl = opt_p - dist_sl
                        tp1 = opt_p + (mult_tp1 * dist_sl)
                        tp2 = opt_p + (mult_tp2 * dist_sl)

            elif profil_court == "Scalping":
                if (sweep_h or fvg_bear or (ema_9 < ema_21 and rsi >= 62)) and (
                    prix < open_p
                ):
                    signal, motif = (
                        "🔴 SHORT",
                        "Scalp 5m Momentum",
                    )
                    opt_p = prix
                    dist_sl = max(high - prix + (0.04 * atr), mult_sl * atr)
                    sl = prix + dist_sl
                    tp1 = prix - (mult_tp1 * dist_sl)
                    tp2 = prix - (mult_tp2 * dist_sl)
                elif (
                    sweep_l or fvg_bull or (ema_9 > ema_21 and rsi <= 38)
                ) and (prix > open_p):
                    signal, motif = (
                        "🟢 LONG",
                        "Scalp 5m Momentum",
                    )
                    opt_p = prix
                    dist_sl = max(prix - low + (0.04 * atr), mult_sl * atr)
                    sl = prix - dist_sl
                    tp1 = prix + (mult_tp1 * dist_sl)
                    tp2 = prix + (mult_tp2 * dist_sl)

            else:  # Ultra-Scalp
                if (sweep_h or fvg_bear or rsi >= 58) and (
                    prix < open_p or ema_9 < ema_21
                ):
                    signal, motif = "🔴 SHORT", "Micro 1m"
                    opt_p = prix
                    dist_sl = max(high - prix + (0.03 * atr), mult_sl * atr)
                    sl = prix + dist_sl
                    tp1 = prix - (mult_tp1 * dist_sl)
                    tp2 = prix - (mult_tp2 * dist_sl)
                elif (sweep_l or fvg_bull or rsi <= 42) and (
                    prix > open_p or ema_9 > ema_21
                ):
                    signal, motif = "🟢 LONG", "Micro 1m"
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
# 🎛️ LE CURSEUR MAÎTRE DE RISQUE
# ==========================================================
st.title("🎛️ Cockpit Futures Multi-Styles")

profil = st.select_slider(
    "👉 Sélectionnez votre profil actif principal :",
    options=[
        "🛡️ Conservateur (15m x20)",
        "⚖️ Intraday (5m x50)",
        "⚡ Scalping (5m x100)",
        "🔥 Ultra-Scalp (1m x150)",
    ],
    value="⚡ Scalping (5m x100)",
)

# Configuration du profil sélectionné
if "Conservateur" in profil:
    profil_cle = "Conservateur"
    levier_suggere = 20
    duree_memoire = 600
    unite_temps = "15m"
elif "Intraday" in profil:
    profil_cle = "Intraday"
    levier_suggere = 50
    duree_memoire = 300
    unite_temps = "5m"
elif "Scalping" in profil:
    profil_cle = "Scalping"
    levier_suggere = 100
    duree_memoire = 180
    unite_temps = "5m"
else:
    profil_cle = "Ultra-Scalp"
    levier_suggere = 150
    duree_memoire = 120
    unite_temps = "1m"

# Contrôles Auto-Refresh
col_ref, col_time = st.columns([1, 1])
with col_ref:
    activer_auto = st.toggle("🔄 Auto-Refresh Live", value=True)
    if activer_auto:
        sec = 5 if profil_cle == "Ultra-Scalp" else 10
        if has_autorefresh:
            st_autorefresh(interval=sec * 1000, key="loop_master_panoramique")
with col_time:
    maintenant_ts = time.time()
    st.caption(
        f"🕒 Heure : **{datetime.datetime.now().strftime('%H:%M:%S')}** | Profil Actif : **{profil_cle} ({unite_temps} x{levier_suggere})**"
    )

# ==========================================================
# 🧠 SYNCHRONISATION MULTI-PROFILS EN ARRIÈRE-PLAN
# ==========================================================
durees_profils = {
    "Conservateur": 600,
    "Intraday": 300,
    "Scalping": 180,
    "Ultra-Scalp": 120,
}

# Scan et mise à jour de la mémoire pour les 4 styles
for p_nom in ["Conservateur", "Intraday", "Scalping", "Ultra-Scalp"]:
    donnees_p = analyser_marche_profil_reel(p_nom)
    for d in donnees_p:
        paire = d["Paire"]
        if d["Signal_Detecte"] is not None:
            st.session_state.memoire_par_profil[p_nom][paire] = {
                "signal": d["Signal_Detecte"],
                "motif": d["Motif"],
                "prix_entree": d["Opt_Price"],
                "sl": d["SL"],
                "tp1": d["TP1"],
                "tp2": d["TP2"],
                "timestamp": maintenant_ts,
            }

    # Nettoyage des expirations par profil
    exp = durees_profils[p_nom]
    a_suppr = [
        p
        for p, info in st.session_state.memoire_par_profil[p_nom].items()
        if maintenant_ts - info["timestamp"] > exp
    ]
    for p in a_suppr:
        del st.session_state.memoire_par_profil[p_nom][p]

# ==========================================================
# 👀 VUE PANORAMIQUE : LES SIGNAUX SUR LES 4 STYLES
# ==========================================================
st.markdown("### 👀 Vue Panoramique (Opportunités sur les 4 Styles) :")

col_c, col_i, col_s, col_u = st.columns(4)

with col_c:
    st.markdown(
        """<div class="mini-card-conservateur">
    <b>🛡️ Conservateur (15m x20)</b><hr style="margin:5px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_c = st.session_state.memoire_par_profil["Conservateur"]
    if sigs_c:
        for paire, info in sigs_c.items():
            st.markdown(
                f"**{info['signal']}** `{paire}`<br>🎯 Limit : {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille (En attente)</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_i:
    st.markdown(
        """<div class="mini-card-intraday">
    <b>⚖️ Intraday (5m x50)</b><hr style="margin:5px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_i = st.session_state.memoire_par_profil["Intraday"]
    if sigs_i:
        for paire, info in sigs_i.items():
            st.markdown(
                f"**{info['signal']}** `{paire}`<br>🎯 Limit : {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille (En attente)</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_s:
    st.markdown(
        """<div class="mini-card-scalping">
    <b>⚡ Scalping (5m x100)</b><hr style="margin:5px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_s = st.session_state.memoire_par_profil["Scalping"]
    if sigs_s:
        for paire, info in sigs_s.items():
            st.markdown(
                f"**{info['signal']}** `{paire}`<br>🎯 Limit : {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille (En attente)</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_u:
    st.markdown(
        """<div class="mini-card-ultrascalp">
    <b>🔥 Ultra-Scalp (1m x150)</b><hr style="margin:5px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_u = st.session_state.memoire_par_profil["Ultra-Scalp"]
    if sigs_u:
        for paire, info in sigs_u.items():
            st.markdown(
                f"**{info['signal']}** `{paire}`<br>🎯 Limit : {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille (En attente)</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# ==========================================================
# 📱 ONGLETS DÉTAILLÉS (DU PROFIL SÉLECTIONNÉ)
# ==========================================================
tab_radar, tab_calc, tab_marche, tab_journal = st.tabs(
    [
        f"⚡ Radar Détaillé ({profil_cle})",
        f"🧮 Calculateur (x{levier_suggere})",
        "🌍 Baromètre IA",
        "📊 Journal Trades",
    ]
)

# 1. RADAR DÉTAILLÉ DU PROFIL ACTIF
with tab_radar:
    memoire_active = st.session_state.memoire_par_profil[profil_cle]
    if memoire_active:
        st.subheader(f"🎯 Opportunités en cours ({profil_cle}) :")
        for paire, info in list(memoire_active.items()):
            temps_restant = int(
                durees_profils[profil_cle]
                - (maintenant_ts - info["timestamp"])
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
                🚀 <span class="tp-runner">TP2 RUNNER (Gros Coup) : {formater_prix(info['tp2'])} USDT</span><br>
                <small>💡 <i>Trade en cours ? Laissez le Stop-Loss et Take-Profit agir sur MEXC sans couper prématurément.</i></small>
            </div>
            """,
                unsafe_allow_html=True,
            )
        st.markdown("---")

    donnees_affichees = analyser_marche_profil_reel(profil_cle)
    lignes_tableau = []
    for d in donnees_affichees:
        paire = d["Paire"]
        statut = (
            memoire_active[paire]["signal"]
            if paire in memoire_active
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

# 2. CALCULATEUR
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
            p_entree + (1.8 * distance)
            if is_long
            else p_entree - (1.8 * distance)
        )
        tp2 = (
            p_entree + (3.5 * distance)
            if is_long
            else p_entree - (3.5 * distance)
        )
        gain_tp1 = (1.8 * distance / p_entree) * notionnel
        gain_tp2 = (3.5 * distance / p_entree) * notionnel

        securite_validee = (p_sl > p_liq) if is_long else (p_sl < p_liq)

        st.markdown("---")
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>📋 Ordre MEXC Recommandé (x{levier_choisi}) :</h3>
            <b>💵 Marge Engagée :</b> <span style="font-size:22px; color:#00E676;"><b>{marge_fixe:.2f} USDT</b></span><br>
            <b>🚀 Notionnel Contrôlé :</b> <b>{notionnel:,.2f} USDT</b> ({quantite:.4f} {paire.split('/')[0]})<br>
            <b>🛑 Perte au Stop-Loss :</b> <span style="color:#FF5252;"><b>-{perte_sl:.2f} USDT</b> ({pct_dist:.2%})</span><br>
            <b>🎯 TP1 (Sécurisation 50%) :</b> <span style="color:#00E676;"><b>+{gain_tp1:.2f} USDT</b></span> ({formater_prix(tp1)} USDT)<br>
            <b>🚀 TP2 RUNNER (Gros Coup) :</b> <span style="color:#00E676;"><b>+{gain_tp2:.2f} USDT</b></span> ({formater_prix(tp2)} USDT)<br>
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