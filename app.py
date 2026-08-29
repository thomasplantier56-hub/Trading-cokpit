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

# Gestion du fuseau horaire France (Europe/Paris)
try:
    import zoneinfo

    TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
except Exception:
    TZ_PARIS = datetime.timezone(datetime.timedelta(hours=2))


def obtenir_date_heure_paris(format_str="%H:%M:%S"):
    return datetime.datetime.now(TZ_PARIS).strftime(format_str)


# Auto-Refresh
try:
    from streamlit_autorefresh import st_autorefresh

    has_autorefresh = True
except ImportError:
    has_autorefresh = False

# Configuration Mobile First & Dark Mode
st.set_page_config(
    page_title="Cockpit Trader Pro Live",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS NOIR PUR OLED
st.markdown(
    """
<style>
    .stApp { background-color: #000000; color: #E6EDF3; }
    .metric-card { background-color: #0D1117; border-radius: 8px; padding: 10px; border-left: 3px solid #2962FF; margin-bottom: 6px; }
    .xp-card { background-color: #120E1E; border-radius: 8px; padding: 10px; border: 1px solid #9C27B0; margin-bottom: 8px; }
    .user-badge { background-color: #061A0E; color: #00E676; padding: 4px 8px; border-radius: 5px; font-weight: bold; border: 1px solid #00E676; font-size: 13px; }
    
    .gold-card { background-color: #171203; border-radius: 8px; padding: 14px; border: 2px solid #FFD700; margin-bottom: 12px; }
    .gold-card-empty { background-color: #0D1117; border-radius: 6px; padding: 8px 12px; border: 1px dashed #30363D; margin-bottom: 10px; font-size: 13px; color: #8B949E; }
    .gold-title { color: #FFD700; font-size: 17px; font-weight: bold; }
    
    .news-box { background-color: #0D1117; border-radius: 6px; padding: 8px 12px; border: 1px solid #21262D; margin-bottom: 10px; font-size: 12px; }
    .tag-bull { color: #00E676; font-weight: bold; background: rgba(0,230,118,0.15); padding: 2px 6px; border-radius: 3px; }
    .tag-bear { color: #FF1744; font-weight: bold; background: rgba(255,23,68,0.15); padding: 2px 6px; border-radius: 3px; }
    .tag-neu { color: #8B949E; font-weight: bold; background: rgba(139,148,158,0.15); padding: 2px 6px; border-radius: 3px; }

    .mini-card-conservateur { background-color: #050B14; border-radius: 6px; padding: 8px; border-top: 3px solid #2979FF; margin-bottom: 6px; }
    .mini-card-intraday { background-color: #0D0814; border-radius: 6px; padding: 8px; border-top: 3px solid #9C27B0; margin-bottom: 6px; }
    .mini-card-scalping { background-color: #140F04; border-radius: 6px; padding: 8px; border-top: 3px solid #FF9100; margin-bottom: 6px; }
    .mini-card-ultrascalp { background-color: #140508; border-radius: 6px; padding: 8px; border-top: 3px solid #FF1744; margin-bottom: 6px; }
    
    .pos-card { background-color: #0D1117; border-radius: 6px; padding: 10px; border: 1px solid #00E676; margin-bottom: 6px; }
    .alert-card-long { background-color: #04140B; border-radius: 6px; padding: 10px; border-left: 4px solid #00E676; margin-bottom: 8px; }
    .alert-card-short { background-color: #170508; border-radius: 6px; padding: 10px; border-left: 4px solid #FF1744; margin-bottom: 8px; }
    .opt-price { color: #FFD700; font-size: 16px; font-weight: bold; }
    .tp-runner { color: #00E676; font-size: 16px; font-weight: bold; }
    .timer-badge { background-color: #161B22; color: #00E676; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
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
# ⚡ TRIPLE FLUX DE PRIX DIRECT (SANS CACHE & SANS LATENCE)
# ==========================================================
def obtenir_prix_live_mexc_garanti():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    prix_dict = {}

    # 1. MEXC Futures Public Ticker API
    try:
        url = "https://contract.mexc.com/api/v1/contract/ticker"
        res = requests.get(url, headers=headers, timeout=1.8).json()
        if res.get("success", False) or "data" in res:
            for item in res.get("data", []):
                sym = item.get("symbol", "").replace("_", "/")
                if item.get("lastPrice"):
                    prix_dict[sym] = float(item.get("lastPrice"))
    except Exception:
        pass

    # 2. Binance Futures Ticker (Relais de secours)
    if not prix_dict or "SOL/USDT" not in prix_dict:
        try:
            url_binance = "https://fapi.binance.com/fapi/v1/ticker/price"
            res2 = requests.get(
                url_binance, headers=headers, timeout=1.8
            ).json()
            for it in res2:
                s_name = it.get("symbol", "")
                for base in ["SOL", "BTC", "ETH", "XRP", "ZEC", "BNB"]:
                    if s_name == f"{base}USDT":
                        prix_dict[f"{base}/USDT"] = float(it.get("price", 0))
        except Exception:
            pass

    return prix_dict


# ==========================================================
# 👥 GESTION ATOMIQUE DES COMPTES TRADERS
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
        },
        "Alex": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "positions": {},
            "historique": [],
        },
    }


def sauvegarder_tous_les_comptes(comptes):
    with open(FICHIER_COMPTES, "w", encoding="utf-8") as f:
        json.dump(comptes, f, indent=4, ensure_ascii=False)


def mettre_a_jour_un_compte(nom_trader, modificateur_fn):
    comptes = charger_tous_les_comptes()
    if nom_trader not in comptes:
        comptes[nom_trader] = {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "positions": {},
            "historique": [],
        }
    modificateur_fn(comptes[nom_trader])
    sauvegarder_tous_les_comptes(comptes)


# ==========================================================
# 🧠 CERVEAU COLLECTIF DE L'IA
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
            "Cerveau collectif prêt. Flux live sans latence actif."
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
        ia["niveau"] = "Quant Confirmé 🥈"
    else:
        ia["niveau"] = "Maître Quant Suprême 🥇"

    score_p = ia["scores_paires"].get(paire, 1.0)
    heure_str = obtenir_date_heure_paris("%H:%M")

    if win:
        ia["scores_paires"][paire] = round(min(score_p + 0.05, 1.5), 2)
        ia["pertes_consecutives"][motif_famille] = 0
        lecon = f"✅ [{nom_trader} - {heure_str}] Gain {paire} ({motif_famille}) : +{pnl:.2f} USDT."
    else:
        ia["scores_paires"][paire] = round(max(score_p - 0.08, 0.5), 2)
        ia["pertes_consecutives"][motif_famille] = (
            ia["pertes_consecutives"].get(motif_famille, 0) + 1
        )
        if ia["pertes_consecutives"][motif_famille] >= 2:
            ia["cooldowns"][motif_famille] = time.time() + 720
            lecon = f"🛡️ [{heure_str}] Cooldown 12 min activé sur {motif_famille} !"
        else:
            lecon = f"❌ [{nom_trader} - {heure_str}] Perte {paire} : {pnl:.2f} USDT."

    ia["lecons_apprises"].insert(0, lecon)
    ia["lecons_apprises"] = ia["lecons_apprises"][:6]
    sauvegarder_experience_ia_collective(ia)


def formater_prix(p):
    if p is None:
        return "N/A"
    try:
        p = float(p)
    except Exception:
        return str(p)
    if p < 0.1:
        return f"{p:.5f}"
    elif p < 1.0:
        return f"{p:.4f}"
    elif p < 10.0:
        return f"{p:.3f}"
    else:
        return f"{p:.2f}"


@st.cache_data(ttl=120)
def charger_news_statiques():
    try:
        flux = feedparser.parse(
            "https://news.google.com/rss/search?q=crypto+bitcoin+solana+when:2d&hl=en-US&gl=US&ceid=US:en"
        )
        items = []
        for entry in flux.entries[:3]:
            titre = entry.title
            compound = analyzer.polarity_scores(titre)["compound"]
            if compound >= 0.15:
                tag = '<span class="tag-bull">BULLISH</span>'
            elif compound <= -0.15:
                tag = '<span class="tag-bear">BEARISH</span>'
            else:
                tag = '<span class="tag-neu">NEUTRE</span>'
            items.append(f"{tag} {titre[:55]}...")
        return items
    except Exception:
        return ["<span class='tag-neu'>MARCHE</span> Synchronisation flux..."]


@st.cache_data(ttl=60)
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


# Cache court de 5 secondes pour la structure
@st.cache_data(ttl=5)
def charger_donnees_marche_globales():
    donnees = {}
    for intervalle, periode in [("15m", "5d"), ("5m", "2d"), ("1m", "1d")]:
        try:
            df = yf.download(
                " ".join(PAIRES_RADAR),
                interval=intervalle,
                period=periode,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
            )
            donnees[intervalle] = df
        except Exception:
            donnees[intervalle] = None
    return donnees


# ==========================================================
# 👑 DÉTECTEUR DU SETUP A+ DU JOUR
# ==========================================================
def detecter_setup_a_plus_du_jour(donnees_globales):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)
    df_15m = donnees_globales.get("15m")

    if df_15m is None:
        return None

    setups_valides = []

    for paire in PAIRES_RADAR:
        nom_court = paire.split("-")[0]
        try:
            df = (
                df_15m[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else df_15m.dropna()
            )
            if len(df) < 35:
                continue

            prix = float(df["Close"].iloc[-1])
            open_p = float(df["Open"].iloc[-1])
            high = float(df["High"].iloc[-1])
            low = float(df["Low"].iloc[-1])

            df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
            ema_50 = float(df["EMA_50"].iloc[-1])

            high_s = float(df["High"].iloc[-17:-1].max())
            low_s = float(df["Low"].iloc[-17:-1].min())

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
                df["High"].iloc[-k] > high_s and df["Close"].iloc[-k] < high_s
                for k in range(1, 3)
            )
            sweep_l = any(
                df["Low"].iloc[-k] < low_s and df["Close"].iloc[-k] > low_s
                for k in range(1, 3)
            )

            fvg_bear = (df["Low"].iloc[-3] > high) and (
                (df["Low"].iloc[-3] - high) > (atr * 0.15)
            )
            fvg_bull = (low > df["High"].iloc[-3]) and (
                (low - df["High"].iloc[-3]) > (atr * 0.15)
            )

            if (
                en_killzone
                and prix < ema_50
                and (sweep_h or fvg_bear)
                and prix < open_p
            ):
                entree_opt = high_s
                dist = max(high - entree_opt + (0.05 * atr), 0.35 * atr)
                sl = entree_opt + dist
                tp = entree_opt - (4.2 * dist)

                if (
                    prix > tp
                    and prix < sl
                    and abs(prix - entree_opt) / entree_opt < 0.015
                ):
                    setups_valides.append(
                        {
                            "paire": f"{nom_court}/USDT",
                            "sens": "SHORT 🔴",
                            "entree": entree_opt,
                            "sl": sl,
                            "tp": tp,
                            "levier": 50,
                            "marge_suggeree": 50.0,
                            "gain_vise": round(
                                (4.2 * dist / entree_opt) * (50.0 * 50), 2
                            ),
                            "perte_max": round(
                                (dist / entree_opt) * (50.0 * 50), 2
                            ),
                            "motif": "Sweep 15m + FVG Majeur en Killzone",
                        }
                    )

            elif (
                en_killzone
                and prix > ema_50
                and (sweep_l or fvg_bull)
                and prix > open_p
            ):
                entree_opt = low_s
                dist = max(entree_opt - low + (0.05 * atr), 0.35 * atr)
                sl = entree_opt - dist
                tp = entree_opt + (4.2 * dist)

                if (
                    prix < tp
                    and prix > sl
                    and abs(prix - entree_opt) / entree_opt < 0.015
                ):
                    setups_valides.append(
                        {
                            "paire": f"{nom_court}/USDT",
                            "sens": "LONG 🟢",
                            "entree": entree_opt,
                            "sl": sl,
                            "tp": tp,
                            "levier": 50,
                            "marge_suggeree": 50.0,
                            "gain_vise": round(
                                (4.2 * dist / entree_opt) * (50.0 * 50), 2
                            ),
                            "perte_max": round(
                                (dist / entree_opt) * (50.0 * 50), 2
                            ),
                            "motif": "Sweep 15m + FVG Majeur en Killzone",
                        }
                    )
        except Exception:
            continue

    return setups_valides[0] if setups_valides else None


def analyser_profil(profil_court, donnees_globales):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)
    ia_data = charger_experience_ia_collective()
    ts_actuel = time.time()

    if profil_court == "Conservateur":
        intervalle, lookback = "15m", 20
        mult_sl, mult_tp1, mult_tp2 = 0.40, 1.8, 3.5
    elif profil_court == "Intraday":
        intervalle, lookback = "5m", 15
        mult_sl, mult_tp1, mult_tp2 = 0.35, 1.8, 3.2
    elif profil_court == "Scalping 1m":
        intervalle, lookback = "1m", 10
        mult_sl, mult_tp1, mult_tp2 = 0.30, 1.8, 3.5
    else:
        intervalle, lookback = "1m", 8
        mult_sl, mult_tp1, mult_tp2 = 0.25, 1.8, 3.8

    data = donnees_globales.get(intervalle)
    if data is None:
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
                        "Tendance 15m",
                    )
                elif prix > ema_50 and rsi <= 42 and prix > open_p:
                    signal, motif = (
                        "🟢 LONG",
                        "Tendance 15m",
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
                        signal, motif = "🔴 SHORT", "Momentum 1m"
                    elif (
                        (ema_9 > ema_21)
                        and (fvg_bull or rsi <= 40)
                        and (prix > open_p)
                    ):
                        signal, motif = "🟢 LONG", "Momentum 1m"

            else:  # Ultra-Scalp
                motif_famille = "SMC"
                if atr >= 0.08:
                    if (sweep_h or fvg_bear) and (prix < open_p or rsi >= 58):
                        signal, motif = "🔴 SHORT", "Ultra-SMC 1m"
                    elif (sweep_l or fvg_bull) and (prix > open_p or rsi <= 42):
                        signal, motif = "🟢 LONG", "Ultra-SMC 1m"

            en_cooldown = ts_actuel < ia_data.get("cooldowns", {}).get(
                motif_famille, 0
            )
            if signal and en_cooldown:
                signal = None

            if signal == "🔴 SHORT":
                opt_p = high_s if sweep_h else prix
                dist = max(high - opt_p + (0.04 * atr), mult_sl * atr)
                sl = opt_p + dist
                tp1 = opt_p - (mult_tp1 * dist)
                tp2 = opt_p - (mult_tp2 * dist)
            elif signal == "🟢 LONG":
                opt_p = low_s if sweep_l else prix
                dist = max(opt_p - low + (0.04 * atr), mult_sl * atr)
                sl = opt_p - dist
                tp1 = opt_p + (mult_tp1 * dist)
                tp2 = opt_p + (mult_tp2 * dist)

            nom_paire = f"{nom_court}/USDT"
            resultats.append(
                {
                    "Paire": nom_paire,
                    "Prix": prix,
                    "High": high,
                    "Low": low,
                    "Range_Str": f"[{formater_prix(low_s)} - {formater_prix(high_s)}]",
                    "Signal_Detecte": signal,
                    "Motif": motif,
                    "Motif_Famille": motif_famille,
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
# 👤 GESTION DU PROFIL UTILISATEUR
# ==========================================================
comptes_actuels = charger_tous_les_comptes()
liste_noms = list(comptes_actuels.keys())

if "trader_session" not in st.session_state:
    st.session_state.trader_session = (
        "Thomas" if "Thomas" in liste_noms else liste_noms[0]
    )

st.sidebar.markdown("### 👤 Espace Utilisateur")
idx_nom = (
    liste_noms.index(st.session_state.trader_session)
    if st.session_state.trader_session in liste_noms
    else 0
)
choix_trader = st.sidebar.selectbox(
    "Connecté en tant que :", liste_noms, index=idx_nom, key="select_trader_box"
)
st.session_state.trader_session = choix_trader
trader_courant = st.session_state.trader_session

with st.sidebar.expander("➕ Créer un profil"):
    nouveau_nom = st.text_input("Prénom / Pseudo :").strip()
    if st.button("Valider"):
        if nouveau_nom:
            comptes_frais = charger_tous_les_comptes()
            if nouveau_nom not in comptes_frais:
                comptes_frais[nouveau_nom] = {
                    "solde": 1000.0,
                    "capital_initial": 1000.0,
                    "auto_actif": False,
                    "positions": {},
                    "historique": [],
                }
                sauvegarder_tous_les_comptes(comptes_frais)
            st.session_state.trader_session = nouveau_nom
            st.rerun()

compte_actif = comptes_actuels.get(
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
# 🔋 EN-TÊTE & AUTO-REFRESH 10S
# ==========================================================
col_h1, col_h2 = st.columns([2, 1])
with col_h1:
    st.markdown(
        f"### ⚡ Cockpit Pro <span class='user-badge'>👤 {trader_courant}</span>",
        unsafe_allow_html=True,
    )
with col_h2:
    mode_refresh = st.selectbox(
        "🔄 Actualisation",
        ["10s (Direct MEXC)", "30s (Éco)", "60s (Ultra-Éco)", "Désactivée"],
        index=0,
    )
    intervalle_sec = (
        10
        if "10s" in mode_refresh
        else (30 if "30s" in mode_refresh else (60 if "60s" in mode_refresh else 0))
    )

    if intervalle_sec > 0 and has_autorefresh:
        st_autorefresh(
            interval=intervalle_sec * 1000, key="loop_final_pure_live_feed"
        )

# Bouton manuel
if st.button("🔄 Rafraîchir les cours en direct", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

news_list = charger_news_statiques()
fg_score, fg_sentiment = charger_fear_and_greed()
st.markdown(
    f"""
<div class="news-box">
    <b>📊 F&G: {fg_score}/100 ({fg_sentiment})</b> | {' | '.join(news_list)}
</div>
""",
    unsafe_allow_html=True,
)

# Chargement données & Prix live directs
donnees_globales = charger_donnees_marche_globales()
prix_mexc_direct = (
    obtenir_prix_live_mexc_garanti()
)  # 🌟 SANS CACHE, AU TICK PRÈS !

# ==========================================================
# 👑 SECTION DU SETUP A+ DU JOUR
# ==========================================================
setup_a_plus = detecter_setup_a_plus_du_jour(donnees_globales)

if setup_a_plus:
    st.markdown(
        f"""
    <div class="gold-card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="gold-title">👑 SETUP A+ DU JOUR : {setup_a_plus['paire']} ({setup_a_plus['sens']})</span>
            <span style="color:#00E676; font-weight:bold; font-size:15px;">Gain Visé : +{setup_a_plus['gain_vise']} USDT (1:4.2)</span>
        </div>
        <hr style="border-color:#FFD700; margin:6px 0;">
        🎯 <b>Entrée Optimale (Limit) :</b> <span class="opt-price">{formater_prix(setup_a_plus['entree'])} USDT</span> | 🛑 <b>Stop-Loss :</b> {formater_prix(setup_a_plus['sl'])} USDT<br>
        🚀 <b>Take-Profit Royal (Ratio 1:4.2) :</b> <span style="color:#00E676; font-weight:bold;">{formater_prix(setup_a_plus['tp'])} USDT</span><br>
        💼 <b>Marge Conseillée :</b> {setup_a_plus['marge_suggeree']} USDT (Levier x{setup_a_plus['levier']}) | 🛑 Risque : -{setup_a_plus['perte_max']} USDT<br>
        <small style="color:#AAA;">💡 <i>{setup_a_plus['motif']} — Entrée encore disponible !</i></small>
    </div>
    """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
    <div class="gold-card-empty">
        👑 <b>SETUP A+ DU JOUR :</b> ⚪ En attente. Le Setup A+ précédent est terminé. L'IA surveille le prochain alignement 5 étoiles !
    </div>
    """,
        unsafe_allow_html=True,
    )

# Curseur actif
profil = st.select_slider(
    "Profil actif :",
    options=[
        "🛡️ Conservateur (15m x20)",
        "⚖️ Intraday (5m x50)",
        "⚡ Scalping (1m x100)",
        "🔥 Ultra-Scalp (1m x150)",
    ],
    value="🔥 Ultra-Scalp (1m x150)",
)

if "Conservateur" in profil:
    profil_cle, levier_suggere, duree_memoire, unite_temps = (
        "Conservateur",
        20,
        600,
        "15m",
    )
elif "Intraday" in profil:
    profil_cle, levier_suggere, duree_memoire, unite_temps = (
        "Intraday",
        50,
        300,
        "5m",
    )
elif "Scalping" in profil:
    profil_cle, levier_suggere, duree_memoire, unite_temps = (
        "Scalping 1m",
        100,
        180,
        "1m",
    )
else:
    profil_cle, levier_suggere, duree_memoire, unite_temps = (
        "Ultra-Scalp",
        150,
        120,
        "1m",
    )

maintenant_ts = time.time()

# ==========================================================
# 🧠 SYNCHRONISATION MULTI-PROFILS
# ==========================================================
durees_profils = {
    "Conservateur": 600,
    "Intraday": 300,
    "Scalping 1m": 180,
    "Ultra-Scalp": 120,
}
leviers_profils = {
    "Conservateur": 20,
    "Intraday": 50,
    "Scalping 1m": 100,
    "Ultra-Scalp": 150,
}

donnees_tous_profils = {}

if "memoire_par_profil" not in st.session_state:
    st.session_state.memoire_par_profil = {p: {} for p in LISTE_PROFILS}

for p_nom in LISTE_PROFILS:
    if p_nom not in st.session_state.memoire_par_profil:
        st.session_state.memoire_par_profil[p_nom] = {}

    donnees_p = analyser_profil(p_nom, donnees_globales)
    donnees_tous_profils[p_nom] = donnees_p

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

    exp = durees_profils.get(p_nom, 120)
    mem_p = st.session_state.memoire_par_profil[p_nom]
    a_suppr = [
        p for p, info in mem_p.items() if maintenant_ts - info["timestamp"] > exp
    ]
    for p in a_suppr:
        del mem_p[p]

# ==========================================================
# 🤖 AUTO-TRADING POUR LE COMPTE ACTIF
# ==========================================================
if compte_actif.get("auto_actif", False):

    def executer_moteur(compte):
        heure_fr_trade = obtenir_date_heure_paris("%H:%M:%S")
        for p_nom in LISTE_PROFILS:
            levier_strat = leviers_profils[p_nom]
            for d in donnees_tous_profils.get(p_nom, []):
                paire = d["Paire"]
                cle_pos = f"{p_nom}_{paire}"
                high = d["High"]
                low = d["Low"]
                motif_fam = d["Motif_Famille"]

                if cle_pos in compte["positions"]:
                    pos = compte["positions"][cle_pos]
                    sens = pos.get("sens", "LONG")
                    p_entree = float(pos.get("entree", d["Prix"]))
                    sl = float(pos.get("sl", 0))
                    tp1 = float(pos.get("tp1", 0))
                    tp2 = float(pos.get("tp2", 0))
                    marge_p = float(pos.get("marge", 100.0))
                    levier_p = float(pos.get("levier", levier_strat))
                    notionnel = marge_p * levier_p

                    if "SHORT" in sens:
                        if not pos.get("tp1_hit", False) and low <= tp1:
                            pos["tp1_hit"] = True
                            pnl_50 = (
                                (p_entree - tp1) / p_entree
                            ) * (notionnel * 0.5)
                            compte["solde"] += pnl_50
                            pos["sl"] = p_entree
                        elif pos.get("tp1_hit", False) and low <= tp2:
                            pnl_runner = (
                                (p_entree - tp2) / p_entree
                            ) * (notionnel * 0.5)
                            pnl_tot = (
                                (p_entree - tp1) / p_entree
                            ) * (notionnel * 0.5) + pnl_runner
                            compte["solde"] += pnl_runner
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, True, pnl_tot
                            )
                            compte["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl_tot, 2),
                                    "win": True,
                                    "date": heure_fr_trade,
                                },
                            )
                            del compte["positions"][cle_pos]
                        elif high >= sl:
                            if pos.get("tp1_hit", False):
                                pnl_tot = (
                                    (p_entree - tp1) / p_entree
                                ) * (notionnel * 0.5)
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire,
                                    motif_fam,
                                    True,
                                    pnl_tot,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire,
                                        "sens": sens,
                                        "pnl": round(pnl_tot, 2),
                                        "win": True,
                                        "date": heure_fr_trade,
                                    },
                                )
                            else:
                                pnl = (
                                    (p_entree - sl) / p_entree
                                ) * notionnel
                                compte["solde"] += pnl
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire,
                                    motif_fam,
                                    False,
                                    pnl,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire,
                                        "sens": sens,
                                        "pnl": round(pnl, 2),
                                        "win": False,
                                        "date": heure_fr_trade,
                                    },
                                )
                            del compte["positions"][cle_pos]

                    elif "LONG" in sens:
                        if not pos.get("tp1_hit", False) and high >= tp1:
                            pos["tp1_hit"] = True
                            pnl_50 = (
                                (tp1 - p_entree) / p_entree
                            ) * (notionnel * 0.5)
                            compte["solde"] += pnl_50
                            pos["sl"] = p_entree
                        elif pos.get("tp1_hit", False) and high >= tp2:
                            pnl_runner = (
                                (tp2 - p_entree) / p_entree
                            ) * (notionnel * 0.5)
                            pnl_tot = (
                                (tp1 - p_entree) / p_entree
                            ) * (notionnel * 0.5) + pnl_runner
                            compte["solde"] += pnl_runner
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, True, pnl_tot
                            )
                            compte["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl_tot, 2),
                                    "win": True,
                                    "date": heure_fr_trade,
                                },
                            )
                            del compte["positions"][cle_pos]
                        elif low <= sl:
                            if pos.get("tp1_hit", False):
                                pnl_tot = (
                                    (tp1 - p_entree) / p_entree
                                ) * (notionnel * 0.5)
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire,
                                    motif_fam,
                                    True,
                                    pnl_tot,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire,
                                        "sens": sens,
                                        "pnl": round(pnl_tot, 2),
                                        "win": True,
                                        "date": heure_fr_trade,
                                    },
                                )
                            else:
                                pnl = ((sl - p_entree) / p_entree) * notionnel
                                compte["solde"] += pnl
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire,
                                    motif_fam,
                                    False,
                                    pnl,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire,
                                        "sens": sens,
                                        "pnl": round(pnl, 2),
                                        "win": False,
                                        "date": heure_fr_trade,
                                    },
                                )
                            del compte["positions"][cle_pos]

                elif len(compte["positions"]) < 4 and d["Signal_Detecte"]:
                    compte["positions"][cle_pos] = {
                        "strategie": p_nom,
                        "sens": d["Signal_Detecte"],
                        "motif": d["Motif"],
                        "entree": d["Opt_Price"],
                        "sl": d["SL"],
                        "tp1": d["TP1"],
                        "tp2": d["TP2"],
                        "marge": 100.0,
                        "levier": levier_strat,
                        "tp1_hit": False,
                        "date_open": heure_fr_trade,
                    }

    mettre_a_jour_un_compte(trader_courant, executer_moteur)
    compte_actif = charger_tous_les_comptes().get(trader_courant, compte_actif)

# ==========================================================
# 👀 VUE PANORAMIQUE DES 4 STYLES
# ==========================================================
col_c, col_i, col_s, col_u = st.columns(4)
with col_c:
    st.markdown(
        """<div class="mini-card-conservateur"><b>🛡️ Conservateur (15m x20)</b><br>""",
        unsafe_allow_html=True,
    )
    sigs_c = st.session_state.memoire_par_profil.get("Conservateur", {})
    if sigs_c:
        for p, info in sigs_c.items():
            st.markdown(
                f"**{info['signal']}** `{p}` 🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#6E7681;'>⚪ En veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_i:
    st.markdown(
        """<div class="mini-card-intraday"><b>⚖️ Intraday (5m x50)</b><br>""",
        unsafe_allow_html=True,
    )
    sigs_i = st.session_state.memoire_par_profil.get("Intraday", {})
    if sigs_i:
        for p, info in sigs_i.items():
            st.markdown(
                f"**{info['signal']}** `{p}` 🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#6E7681;'>⚪ En veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_s:
    st.markdown(
        """<div class="mini-card-scalping"><b>⚡ Scalp (1m x100)</b><br>""",
        unsafe_allow_html=True,
    )
    sigs_s = st.session_state.memoire_par_profil.get("Scalping 1m", {})
    if sigs_s:
        for p, info in sigs_s.items():
            st.markdown(
                f"**{info['signal']}** `{p}` 🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#6E7681;'>⚪ En veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_u:
    st.markdown(
        """<div class="mini-card-ultrascalp"><b>🔥 Ultra (1m x150)</b><br>""",
        unsafe_allow_html=True,
    )
    sigs_u = st.session_state.memoire_par_profil.get("Ultra-Scalp", {})
    if sigs_u:
        for p, info in sigs_u.items():
            st.markdown(
                f"**{info['signal']}** `{p}` 🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#6E7681;'>⚪ En veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# 📱 ONGLETS PRINCIPAUX
# ==========================================================
tab_auto, tab_radar, tab_ia, tab_classement, tab_calc = st.tabs(
    [
        f"🤖 Auto ({trader_courant})",
        f"⚡ Radar ({profil_cle})",
        "🧠 Cerveau IA",
        "🏆 Classement",
        "🧮 Calculateur",
    ]
)

# 1. MON AUTO-TRADER
with tab_auto:
    col_t1, col_t2 = st.columns([2, 1])
    pnl_auto = compte_actif["solde"] - compte_actif["capital_initial"]

    with col_t1:
        st.markdown(
            f"💰 **Solde :** `{compte_actif['solde']:.2f} USDT` | **PnL :** <span style='color:{'#00E676' if pnl_auto >= 0 else '#FF5252'}; font-weight:bold;'>{pnl_auto:+.2f} USDT</span>",
            unsafe_allow_html=True,
        )

    with col_t2:
        nouvel_etat = st.toggle(
            "⚡ ACTIVER L'AUTO",
            value=compte_actif.get("auto_actif", False),
            key="toggle_auto_live_final_mexc",
        )
        if nouvel_etat != compte_actif.get("auto_actif", False):

            def toggle_etat(c):
                c["auto_actif"] = nouvel_etat

            mettre_a_jour_un_compte(trader_courant, toggle_etat)
            st.rerun()

    if compte_actif["positions"]:
        st.markdown("#### 🚀 Positions Ouvertes :")
        for cle, pos in list(compte_actif["positions"].items()):
            strat_nom = pos.get("strategie", "Auto")
            paire_nom = cle.split("_")[1] if "_" in cle else cle
            sens_nom = pos.get("sens", "LONG")
            levier_nom = pos.get("levier", 50)
            entree_val = formater_prix(pos.get("entree", 0))
            sl_val = formater_prix(pos.get("sl", 0))
            tp1_val = formater_prix(pos.get("tp1", 0))
            tp2_val = formater_prix(pos.get("tp2", 0))
            tp1_statut = (
                "✅ Breakeven" if pos.get("tp1_hit", False) else "⏳ Attente"
            )

            st.markdown(
                f"""
            <div class="pos-card">
                <b>[{strat_nom}] {paire_nom} ({sens_nom} x{levier_nom})</b><br>
                🎯 <b>Entrée :</b> {entree_val} | 🛑 <b>SL :</b> {sl_val}<br>
                💰 <b>TP1 :</b> {tp1_val} [{tp1_statut}] | 🚀 <b>TP2 :</b> {tp2_val}
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("👀 Aucune position ouverte.")

    if compte_actif["historique"]:
        st.markdown("#### 📜 Derniers Trades Clôturés :")
        st.dataframe(
            pd.DataFrame(compte_actif["historique"][:5]), hide_index=True
        )

    if st.button("🔄 Reset solde à 1000 USDT"):

        def reset_c(c):
            c["solde"] = 1000.0
            c["capital_initial"] = 1000.0
            c["auto_actif"] = False
            c["positions"] = {}
            c["historique"] = []

        mettre_a_jour_un_compte(trader_courant, reset_c)
        st.rerun()

# 2. RADAR AVEC PRIX DIRECTS DU FLUX MEXC
with tab_radar:
    memoire_active = st.session_state.memoire_par_profil.get(profil_cle, {})
    if memoire_active:
        for p, info in list(memoire_active.items()):
            temps_restant = int(
                durees_profils.get(profil_cle, 120)
                - (maintenant_ts - info["timestamp"])
            )
            classe = (
                "alert-card-long"
                if "LONG" in info["signal"]
                else "alert-card-short"
            )
            st.markdown(
                f"""
            <div class="{classe}">
                <b>⚡ {p} : {info['signal']} ({info['motif']})</b> <span class="timer-badge">⏱️ {max(0, temps_restant)}s</span><br>
                🎯 <span class="opt-price">Limit : {formater_prix(info['prix_entree'])} USDT</span><br>
                🛑 SL : {formater_prix(info['sl'])} | 💰 TP1 : {formater_prix(info['tp1'])} | 🚀 TP2 : {formater_prix(info['tp2'])}
            </div>
            """,
                unsafe_allow_html=True,
            )

    donnees_affichees = donnees_tous_profils.get(profil_cle, [])
    lignes_tableau = []
    for d in donnees_affichees:
        paire = d["Paire"]
        statut = (
            memoire_active[paire]["signal"]
            if paire in memoire_active
            else "VEILLE ⚪"
        )
        # Affichage du vrai prix MEXC en direct
        prix_reel_mexc = prix_mexc_direct.get(paire, d["Prix"])

        lignes_tableau.append(
            {
                "Paire": paire,
                "Prix Actuel": formater_prix(prix_reel_mexc),
                "Statut": statut,
                "Range Structure": d["Range_Str"],
                "RSI": d["RSI"],
            }
        )
    st.dataframe(pd.DataFrame(lignes_tableau), hide_index=True)

# 3. CERVEAU COLLECTIF IA
with tab_ia:
    ia_stats = charger_experience_ia_collective()
    st.markdown(
        f"""
    <div class="xp-card">
        <b>🏆 Niveau : <span style="color:#00E676;">{ia_stats['niveau']}</span></b> (⭐ {ia_stats['xp_total']} XP Partagés)<br>
        <small>Chaque trade améliore les filtres de tout le groupe.</small>
    </div>
    """,
        unsafe_allow_html=True,
    )
    for lecon in ia_stats["lecons_apprises"][:4]:
        st.caption(f"• {lecon}")

# 4. CLASSEMENT
with tab_classement:
    liste_classement = []
    comptes_live = charger_tous_les_comptes()
    for nom, c in comptes_live.items():
        pnl = c["solde"] - c["capital_initial"]
        trades_nb = len(c.get("historique", []))
        wins = sum(1 for t in c.get("historique", []) if t.get("win", False))
        wr = (wins / trades_nb * 100) if trades_nb > 0 else 0.0
        liste_classement.append(
            {
                "Trader": f"👤 {nom}",
                "Solde": f"{c['solde']:.1f} $",
                "PnL": f"{pnl:+.1f} $",
                "WR": f"{wr:.0f}%",
                "Trades": trades_nb,
            }
        )
    st.dataframe(
        pd.DataFrame(liste_classement).sort_values(
            by="PnL", ascending=False
        ),
        hide_index=True,
    )

# 5. CALCULATEUR
with tab_calc:
    c1, c2 = st.columns(2)
    paire_sel = c1.selectbox(
        "Paire", [f"{p.split('-')[0]}/USDT" for p in PAIRES_RADAR]
    )
    sens_sel = c2.radio("Sens", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
    is_long = "LONG" in sens_sel

    col_e, col_sl = st.columns(2)
    p_entree = col_e.number_input(
        "Entrée ($)", value=106.20, step=0.01, format="%.5f"
    )
    p_sl = col_sl.number_input(
        "SL ($)", value=105.90, step=0.01, format="%.5f"
    )

    marge_fixe = st.number_input("Marge (USDT)", value=10.0, step=5.0)

    if (is_long and p_sl < p_entree) or ((not is_long) and p_sl > p_entree):
        distance = abs(p_entree - p_sl)
        pct_dist = distance / p_entree
        notionnel = marge_fixe * levier_suggere
        perte_sl = pct_dist * notionnel

        dist_liq_pct = (1.0 / levier_suggere) * 0.90
        p_liq = (
            p_entree * (1 - dist_liq_pct)
            if is_long
            else p_entree * (1 + dist_liq_pct)
        )
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

        st.markdown(
            f"""
        <div class="metric-card">
            <b>Marge :</b> {marge_fixe:.1f} USDT (x{levier_suggere}) | <b>SL :</b> <span style="color:#FF5252;">-{perte_sl:.2f}$ ({pct_dist:.2%})</span><br>
            🎯 <b>TP1 :</b> {formater_prix(tp1)} | 🚀 <b>TP2 Runner :</b> {formater_prix(tp2)}<br>
            💀 <b>Liquidation :</b> {formater_prix(p_liq)}
        </div>
        """,
            unsafe_allow_html=True,
        )