import csv
import datetime
import json
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
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
    .stApp { background-color: #080A0E; color: #FAFAFA; }
    .metric-card { background-color: #12161F; border-radius: 8px; padding: 12px; border-left: 4px solid #2962FF; margin-bottom: 8px; }
    .xp-card { background-color: #1A1528; border-radius: 8px; padding: 14px; border: 1px solid #9C27B0; margin-bottom: 12px; }
    .cooldown-badge { background-color: #332005; color: #FFB300; padding: 3px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; border: 1px solid #FFB300; }
    .user-badge { background-color: #0D2818; color: #00E676; padding: 5px 12px; border-radius: 6px; font-weight: bold; border: 1px solid #00E676; }
    
    .mini-card-conservateur { background-color: #0E1626; border-radius: 8px; padding: 10px; border-top: 4px solid #2979FF; margin-bottom: 8px; min-height: 110px; }
    .mini-card-intraday { background-color: #161124; border-radius: 8px; padding: 10px; border-top: 4px solid #9C27B0; margin-bottom: 8px; min-height: 110px; }
    .mini-card-scalping { background-color: #1C1608; border-radius: 8px; padding: 10px; border-top: 4px solid #FF9100; margin-bottom: 8px; min-height: 110px; }
    .mini-card-ultrascalp { background-color: #21090D; border-radius: 8px; padding: 10px; border-top: 4px solid #FF1744; margin-bottom: 8px; min-height: 110px; }
    
    .pos-card { background-color: #151A24; border-radius: 8px; padding: 12px; border: 1px solid #00E676; margin-bottom: 8px; }
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
FICHIER_COMPTES = "comptes_traders.json"
FICHIER_IA = "experience_ia_collective.json"

PAIRES_RADAR = [
    "SOL-USD",
    "BTC-USD",
    "ETH-USD",
    "XRP-USD",
    "ZEC-USD",
    "PIPPIN-USD",
    "BNB-USD",
]
LISTE_PROFILS = ["Conservateur", "Intraday", "Scalping 1m", "Ultra-Scalp"]
analyzer = SentimentIntensityAnalyzer()


# ==========================================================
# 👥 GESTION DES COMPTES UTILISATEURS MULTIPLES
# ==========================================================
def charger_tous_les_comptes():
    if os.path.exists(FICHIER_COMPTES):
        try:
            with open(FICHIER_COMPTES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "Thomas": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "positions": {},
            "historique": [],
        }
    }


def sauvegarder_tous_les_comptes(comptes):
    with open(FICHIER_COMPTES, "w", encoding="utf-8") as f:
        json.dump(comptes, f, indent=4, ensure_ascii=False)


# ==========================================================
# 🧠 CERVEAU COLLECTIF UNIQUE DE L'IA
# ==========================================================
def charger_experience_ia_collective():
    if os.path.exists(FICHIER_IA):
        try:
            with open(FICHIER_IA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "xp_total": 0,
        "niveau": "Novice Quant 🥚",
        "scores_paires": {p.split("-")[0]: 1.0 for p in PAIRES_RADAR},
        "cooldowns": {"SMC": 0, "Momentum": 0, "Tendance": 0},
        "pertes_consecutives": {"SMC": 0, "Momentum": 0, "Tendance": 0},
        "lecons_apprises": [
            "Initialisation du cerveau collectif. En attente des premiers trades du groupe."
        ],
    }


def sauvegarder_experience_ia_collective(ia_data):
    with open(FICHIER_IA, "w", encoding="utf-8") as f:
        json.dump(ia_data, f, indent=4, ensure_ascii=False)


def mettre_a_jour_ia_collective(nom_trader, paire_brute, motif_famille, win, pnl):
    ia = charger_experience_ia_collective()
    paire = paire_brute.split("/")[0]

    ia["xp_total"] += 15 if win else 5
    xp = ia["xp_total"]

    if xp < 150:
        ia["niveau"] = "Novice Quant 🥚"
    elif xp < 500:
        ia["niveau"] = "Collectif Initié 🥉"
    elif xp < 1200:
        ia["niveau"] = "Hedge Fund IA Confirmé 🥈"
    else:
        ia["niveau"] = "Maître Quant Suprême 🥇"

    score_p = ia["scores_paires"].get(paire, 1.0)

    if win:
        ia["scores_paires"][paire] = round(min(score_p + 0.05, 1.5), 2)
        ia["pertes_consecutives"][motif_famille] = 0
        lecon = f"✅ [{nom_trader} - {datetime.datetime.now().strftime('%H:%M')}] Victoire sur {paire} ({motif_famille}) : +{pnl:.2f} USDT."
    else:
        ia["scores_paires"][paire] = round(max(score_p - 0.08, 0.5), 2)
        ia["pertes_consecutives"][motif_famille] = (
            ia["pertes_consecutives"].get(motif_famille, 0) + 1
        )
        if ia["pertes_consecutives"][motif_famille] >= 2:
            ia["cooldowns"][motif_famille] = time.time() + 720
            lecon = f"🛡️ [Alerte Collectif] 2 pertes consécutives sur {motif_famille} : Cooldown 12 min activé pour tout le monde !"
        else:
            lecon = f"❌ [{nom_trader} - {datetime.datetime.now().strftime('%H:%M')}] Perte sur {paire} ({motif_famille}) : {pnl:.2f} USDT."

    ia["lecons_apprises"].insert(0, lecon)
    ia["lecons_apprises"] = ia["lecons_apprises"][:8]
    sauvegarder_experience_ia_collective(ia)


# Mémoire d'affichage
if "memoire_par_profil" not in st.session_state:
    st.session_state.memoire_par_profil = {p: {} for p in LISTE_PROFILS}


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


# Moteur de Marché
@st.cache_data(ttl=10)
def analyser_marche_harmonise(profil_court):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)
    ia_data = charger_experience_ia_collective()
    ts_actuel = time.time()

    if profil_court == "Conservateur":
        intervalle, periode, lookback = "15m", "5d", 20
        mult_sl, mult_tp1, mult_tp2 = 0.40, 1.8, 3.5
    elif profil_court == "Intraday":
        intervalle, periode, lookback = "5m", "2d", 15
        mult_sl, mult_tp1, mult_tp2 = 0.35, 1.8, 3.2
    elif profil_court == "Scalping 1m":
        intervalle, periode, lookback = "1m", "1d", 10
        mult_sl, mult_tp1, mult_tp2 = 0.30, 1.8, 3.5
    else:  # Ultra-Scalp
        intervalle, periode, lookback = "1m", "1d", 8
        mult_sl, mult_tp1, mult_tp2 = 0.25, 1.8, 3.8

    try:
        data = yf.download(
            " ".join(PAIRES_RADAR),
            interval=intervalle,
            period=periode,
            group_by="ticker",
            auto_adjust=True,
            progress=False,
        )
    except Exception:
        return []

    resultats = []

    for paire in PAIRES_RADAR:
        nom_court = paire.split("-")[0]
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

            df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
            ema_50 = float(df["EMA_50"].iloc[-1])
            df["EMA_9"] = df["Close"].ewm(span=9, adjust=False).mean()
            df["EMA_21"] = df["Close"].ewm(span=21, adjust=False).mean()
            ema_9 = float(df["EMA_9"].iloc[-1])
            ema_21 = float(df["EMA_21"].iloc[-1])

            d = df["Close"].diff()
            g = d.where(d > 0, 0).rolling(7 if "1m" in intervalle else 14).mean()
            l = (
                (-d.where(d < 0, 0))
                .rolling(7 if "1m" in intervalle else 14)
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

            high_s = float(df["High"].iloc[-lookback:-1].max())
            low_s = float(df["Low"].iloc[-lookback:-1].min())
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

            signal, opt_p, sl, tp1, tp2, motif, motif_famille = (
                None,
                None,
                None,
                None,
                None,
                "",
                "SMC",
            )

            if profil_court == "Conservateur":
                motif_famille = "Tendance"
                if prix < ema_50 and rsi >= 58 and prix < open_p:
                    signal, motif = (
                        "🔴 SHORT",
                        "Tendance 15m (Sous EMA 50)",
                    )
                elif prix > ema_50 and rsi <= 42 and prix > open_p:
                    signal, motif = (
                        "🟢 LONG",
                        "Tendance 15m (Sur EMA 50)",
                    )

            elif profil_court == "Intraday":
                motif_famille = "SMC"
                if en_killzone:
                    if (sweep_h or (prix < ema_9)) and rsi >= 60:
                        signal, motif = "🔴 SHORT", "Killzone 5m"
                    elif (sweep_l or (prix > ema_9)) and rsi <= 40:
                        signal, motif = "🟢 LONG", "Killzone 5m"

            elif profil_court == "Scalping 1m":
                motif_famille = "Momentum"
                if atr >= 0.08:
                    if (ema_9 < ema_21) and (fvg_bear or rsi >= 60) and (prix < open_p):
                        signal, motif = "🔴 SHORT", "Momentum 1m x100"
                    elif (
                        (ema_9 > ema_21)
                        and (fvg_bull or rsi <= 40)
                        and (prix > open_p)
                    ):
                        signal, motif = "🟢 LONG", "Momentum 1m x100"

            else:  # Ultra-Scalp
                motif_famille = "SMC"
                if atr >= 0.08:
                    if (sweep_h or fvg_bear) and (prix < open_p or rsi >= 58):
                        signal, motif = (
                            "🔴 SHORT",
                            "Ultra-SMC 1m (x150)",
                        )
                    elif (sweep_l or fvg_bull) and (prix > open_p or rsi <= 42):
                        signal, motif = (
                            "🟢 LONG",
                            "Ultra-SMC 1m (x150)",
                        )

            en_cooldown = ts_actuel < ia_data.get("cooldowns", {}).get(
                motif_famille, 0
            )
            if signal and en_cooldown:
                signal = None

            if signal == "🔴 SHORT":
                opt_p = high_s if sweep_h else prix
                dist_sl = max(high - opt_p + (0.04 * atr), mult_sl * atr)
                sl = opt_p + dist_sl
                tp1 = opt_p - (mult_tp1 * dist_sl)
                tp2 = opt_p - (mult_tp2 * dist_sl)
            elif signal == "🟢 LONG":
                opt_p = low_s if sweep_l else prix
                dist_sl = max(opt_p - low + (0.04 * atr), mult_sl * atr)
                sl = opt_p - dist_sl
                tp1 = opt_p + (mult_tp1 * dist_sl)
                tp2 = opt_p + (mult_tp2 * dist_sl)

            nom_paire = f"{nom_court}/USDT"
            resultats.append(
                {
                    "Paire": nom_paire,
                    "Prix": prix,
                    "High": high,
                    "Low": low,
                    "Signal_Detecte": signal,
                    "Motif": motif,
                    "Motif_Famille": motif_famille,
                    "Opt_Price": opt_p,
                    "SL": sl,
                    "TP1": tp1,
                    "TP2": tp2,
                    "RSI": f"{rsi:.1f}",
                    "Intervalle": intervalle,
                    "En_Cooldown": en_cooldown,
                }
            )
        except Exception:
            continue
    return resultats


# ==========================================================
# 👤 GESTIONNAIRE DE PROFILS TRADERS VÉRITABLEMENT VERROUILLÉ
# ==========================================================
comptes_tous = charger_tous_les_comptes()
liste_noms = list(comptes_tous.keys()) + ["➕ Nouveau Profil Trader"]

if (
    "active_trader" not in st.session_state
    or st.session_state.active_user not in list(comptes_tous.keys())
):
    st.session_state.active_user = (
        "Thomas" if "Thomas" in comptes_tous else list(comptes_tous.keys())[0]
    )


def change_user_cb():
    val = st.session_state.temp_user_select
    if val != "➕ Nouveau Profil Trader":
        st.session_state.active_user = val


keys_dispos = list(comptes_tous.keys())
idx_safe = (
    keys_dispos.index(st.session_state.active_user)
    if st.session_state.active_user in keys_dispos
    else 0
)

st.sidebar.markdown("### 👤 Espace Utilisateur")
choix_utilisateur = st.sidebar.selectbox(
    "Connecté en tant que :",
    liste_noms,
    index=idx_safe if idx_safe < len(liste_noms) - 1 else 0,
    key="temp_user_select",
    on_change=change_user_cb,
)

if choix_utilisateur == "➕ Nouveau Profil Trader":
    nouveau_pseudo = st.sidebar.text_input("Votre Prénom / Pseudo :").strip()
    if st.sidebar.button("Créer mon compte virtuel"):
        if nouveau_pseudo and nouveau_pseudo not in comptes_tous:
            comptes_tous[nouveau_pseudo] = {
                "solde": 1000.0,
                "capital_initial": 1000.0,
                "auto_actif": False,
                "positions": {},
                "historique": [],
            }
            sauvegarder_tous_les_comptes(comptes_tous)
            st.session_state.active_user = nouveau_pseudo
            st.sidebar.success(f"Compte créé pour {nouveau_pseudo} !")
            st.rerun()
    trader_courant = st.session_state.active_user
else:
    trader_courant = (
        st.session_state.active_user
        if st.session_state.active_user in comptes_tous
        else choix_utilisateur
    )

compte_actif = comptes_tous.get(
    trader_courant,
    {
        "solde": 1000.0,
        "capital_initial": 1000.0,
        "auto_actif": False,
        "positions": {},
        "historique": [],
    },
)

# ==========================================================
# 🎛️ LE CURSEUR MAÎTRE
# =================================