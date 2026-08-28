import csv
import datetime
import os
import feedparser
import numpy as np
import pandas as pd
import requests
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import yfinance as yf

# Importation du module d'auto-refresh
try:
    from streamlit_autorefresh import st_autorefresh

    has_autorefresh = True
except ImportError:
    has_autorefresh = False

# Configuration Streamlit Dark Mode & Mobile
st.set_page_config(
    page_title="Cockpit Futures USDT Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .metric-card { background-color: #1E222D; border-radius: 10px; padding: 15px; border-left: 5px solid #2962FF; margin-bottom: 10px; }
    .alert-card-long { background-color: #0D3320; border-radius: 10px; padding: 15px; border-left: 5px solid #00E676; margin-bottom: 10px; }
    .alert-card-short { background-color: #3B141E; border-radius: 10px; padding: 15px; border-left: 5px solid #FF1744; margin-bottom: 10px; }
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
    "AVAX-USD",
    "SUI20947-USD",
    "DOGE-USD",
    "BNB-USD",
]
analyzer = SentimentIntensityAnalyzer()

# Initialisation du Journal CSV
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


# Fonctions de Données avec Cache court pour réactivité
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
        for entry in flux.entries[:5]:
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


@st.cache_data(ttl=15)
def charger_radar_data():
    data = yf.download(
        " ".join(PAIRES_RADAR),
        interval="5m",
        period="2d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
    )
    resultats = []
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)

    for paire in PAIRES_RADAR:
        try:
            df = (
                data[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else data.dropna()
            )
            if len(df) < 25:
                continue

            prix = float(df["Close"].iloc[-1])
            open_p = float(df["Open"].iloc[-1])
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])
            high_s = float(df["High"].iloc[-21:-1].max())
            low_s = float(df["Low"].iloc[-21:-1].min())

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

            sweep_h = (high > high_s) and (prix < high_s)
            sweep_l = (low < low_s) and (prix > low_s)
            fvg_bear = (df["Low"].iloc[-3] > high) and (
                (df["Low"].iloc[-3] - high) > (atr * 0.15)
            )
            fvg_bull = (low > df["High"].iloc[-3]) and (
                (low - df["High"].iloc[-3]) > (atr * 0.15)
            )

            signal = "VEILLE ⚪"
            dist_sl, sl, tp = 0, 0, 0

            if en_killzone:
                if (sweep_h or fvg_bear) and (prix < open_p):
                    signal = "🔴 SHORT"
                    dist_sl = max(high - prix + (0.05 * atr), 0.35 * atr)
                    sl = prix + dist_sl
                    tp = prix - (3.0 * dist_sl)
                elif (sweep_l or fvg_bull) and (prix > open_p):
                    signal = "🟢 LONG"
                    dist_sl = max(prix - low + (0.05 * atr), 0.35 * atr)
                    sl = prix - dist_sl
                    tp = prix + (3.0 * dist_sl)

            resultats.append(
                {
                    "Paire": f"{paire.split('-')[0]}/USDT",
                    "Prix": prix,
                    "Signal": signal,
                    "Stop-Loss": sl if sl > 0 else None,
                    "Take-Profit": tp if tp > 0 else None,
                    "Range 5m": f"[{low_s:.2f} - {high_s:.2f}]",
                }
            )
        except Exception:
            continue
    return resultats, en_killzone


# ==========================================================
# 📱 EN-TÊTE & CONTRÔLE D'ACTUALISATION AUTOMATIQUE
# ==========================================================
col_titre, col_refresh = st.columns([2, 1])

with col_titre:
    st.title("⚡ Cockpit Futures USDT")

with col_refresh:
    activer_auto = st.toggle("🔄 Auto-Refresh Live", value=True)
    if activer_auto:
        sec = st.select_slider(
            "Intervalle (sec)", options=[10, 15, 30, 60], value=15
        )
        if has_autorefresh:
            st_autorefresh(interval=sec * 1000, key="auto_refresh_loop")
        else:
            st.components.v1.html(
                f"<script>setTimeout(function(){{window.parent.location.reload();}}, {sec * 1000});</script>",
                height=0,
            )

heure_actuelle = datetime.datetime.now().strftime("%H:%M:%S")
st.caption(f"🕒 Dernière mise à jour en direct : **{heure_actuelle}**")

# ==========================================================
# 📱 ONGLETS PRINCIPAUX
# ==========================================================
onglet_radar, onglet_marche, onglet_calculateur, onglet_journal = st.tabs(
    [
        "🛰️ Radar Live",
        "🌍 Marché & News",
        "🧮 Calculateur USDT",
        "📊 Journal & Biais",
    ]
)

# 1. RADAR
with onglet_radar:
    radar_data, en_killzone = charger_radar_data()

    if en_killzone:
        st.success("🟢 **SESSION ACTIVE (Killzone Londres / New York)**")
    else:
        st.info("⚪ **HORS SESSION (Marché calme)**")

    alertes = [r for r in radar_data if "VEILLE" not in r["Signal"]]
    if alertes:
        for a in alertes:
            classe = (
                "alert-card-long"
                if "LONG" in a["Signal"]
                else "alert-card-short"
            )
            st.markdown(
                f"""
            <div class="{classe}">
                <h3>🚨 Opportunité : {a['Paire']} ({a['Signal']})</h3>
                <b>Prix Actuel :</b> {a['Prix']:.2f} USDT<br>
                <b>Stop-Loss (One Candle) :</b> {a['Stop-Loss']:.2f} USDT | <b>Take-Profit (1:3) :</b> {a['Take-Profit']:.2f} USDT
            </div>
            """,
                unsafe_allow_html=True,
            )

    df_radar = pd.DataFrame(radar_data)
    st.dataframe(df_radar, hide_index=True)

# 2. MARCHÉ
with onglet_marche:
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

    st.subheader("📰 Dernières dépêches analysées par l'IA")
    for tag, titre in news:
        st.markdown(f"**{tag}** — {titre}")

# 3. CALCULATEUR
with onglet_calculateur:
    st.subheader("🧮 Calculateur de Risque MEXC (Futures USDT)")

    c1, c2 = st.columns(2)
    paire_choisie = c1.selectbox(
        "Contrat Futures",
        ["SOL/USDT", "BTC/USDT", "ETH/USDT", "XRP/USDT", "AVAX/USDT"],
    )
    sens_choisi = c2.radio("Sens", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
    is_long = "LONG" in sens_choisi

    col_p1, col_p2 = st.columns(2)
    p_entree = col_p1.number_input(
        "Prix d'Entrée (USDT)", value=106.0, step=0.1, format="%.2f"
    )
    p_sl = col_p2.number_input(
        "Prix Stop-Loss (USDT)",
        value=105.2 if is_long else 106.8,
        step=0.1,
        format="%.2f",
    )

    col_r1, col_r2 = st.columns(2)
    risque_max = col_r1.number_input(
        "Risque accepté (USDT)", value=20.0, step=5.0
    )
    levier_choisi = col_r2.slider("Levier", min_value=1, max_value=100, value=55)

    if (is_long and p_sl < p_entree) or ((not is_long) and p_sl > p_entree):
        distance = abs(p_entree - p_sl)
        pct_distance = distance / p_entree
        notionnel = risque_max / pct_distance
        marge_usdt = notionnel / levier_choisi
        quantite_crypto = notionnel / p_entree

        dist_liq_pct = 1.0 / levier_choisi * 0.92
        p_liq = (
            p_entree * (1 - dist_liq_pct)
            if is_long
            else p_entree * (1 + dist_liq_pct)
        )
        securite_ok = (p_sl > p_liq) if is_long else (p_sl < p_liq)

        st.markdown("---")
        st.markdown(
            f"""
        <div class="metric-card">
            <h3>📋 Paramètres d'Ordre MEXC Futures :</h3>
            <b>💵 Marge à entrer sur MEXC :</b> <span style="font-size:22px; color:#00E676;"><b>{marge_usdt:.2f} USDT</b></span><br>
            <b>🪙 Quantité du contrat :</b> {quantite_crypto:.4f} {paire_choisie.split('/')[0]} (Position totale : {notionnel:.2f} USDT)<br>
            <b>🛑 Stop-Loss OBLIGATOIRE :</b> {p_sl:.2f} USDT (Perte : <b>-{risque_max:.2f} USDT</b>)<br>
            <b>🎯 Take-Profit 1:2 :</b> {p_entree + 2*distance if is_long else p_entree - 2*distance:.2f} USDT (+{risque_max*2:.2f} USDT)<br>
            <b>🎯 Take-Profit 1:3 :</b> {p_entree + 3*distance if is_long else p_entree - 3*distance:.2f} USDT (+{risque_max*3:.2f} USDT)<br>
            <b>💀 Prix de Liquidation :</b> {p_liq:.2f} USDT
        </div>
        """,
            unsafe_allow_html=True,
        )

        if securite_ok:
            st.success(
                "✅ Sécurité Validée : Stop-Loss bien placé AVANT la liquidation."
            )
        else:
            st.error(
                "🚨 DANGER : Levier trop fort ! La liquidation arrive AVANT le Stop-Loss !"
            )

        if st.button("💾 Sauvegarder dans mon Journal"):
            with open(
                FICHIER_JOURNAL, mode="a", newline="", encoding="utf-8"
            ) as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                        paire_choisie,
                        "LONG" if is_long else "SHORT",
                        f"{p_entree:.2f}",
                        f"{p_sl:.2f}",
                        f"{p_entree + 3*distance if is_long else p_entree - 3*distance:.2f}",
                        f"{marge_usdt:.2f}",
                        f"x{levier_choisi}",
                        "EN_COURS",
                        "0.00",
                    ]
                )
            st.success("Trade archivé avec succès dans votre journal USDT !")
    else:
        st.warning("⚠️ Vérifiez vos prix : le Stop-Loss est mal positionné.")

# 4. JOURNAL
with onglet_journal:
    st.subheader("📊 Historique des Trades USDT & Détection des Biais")
    if os.path.exists(FICHIER_JOURNAL):
        try:
            df_j = pd.read_csv(
                FICHIER_JOURNAL, encoding="utf-8", encoding_errors="ignore"
            )
        except Exception:
            df_j = pd.read_csv(FICHIER_JOURNAL, encoding="latin1")
        st.dataframe(df_j, hide_index=True)