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


# Configuration Streamlit Mobile First & Dark Mode
st.set_page_config(
    page_title="Cockpit Trader Pro Live",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
    
    .sol-master-card { background: linear-gradient(135deg, #130a24 0%, #051410 100%); border-radius: 10px; padding: 14px; border: 2px solid #14F195; margin-bottom: 12px; }
    .grid-badge-buy { background-color: rgba(20, 241, 149, 0.15); color: #14F195; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #14F195; font-size: 12px; }
    .grid-badge-sell { background-color: rgba(255, 23, 68, 0.15); color: #FF1744; padding: 4px 8px; border-radius: 4px; font-weight: bold; border: 1px solid #FF1744; font-size: 12px; }
    
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
    .timer-badge { background-color: #161B22; color: #00E676; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)

FICHIER_COMPTES = "comptes_traders.json"
FICHIER_IA = "experience_ia_collective.json"

# 🌟 PIXEL AJOUTÉ AU RADAR ICI
PAIRES_RADAR = [
    "SOL-USD",
    "BTC-USD",
    "ETH-USD",
    "XRP-USD",
    "ZEC-USD",
    "PIPPIN-USD",
    "BNB-USD",
    "PIXEL-USD",
]
LISTE_PROFILS = ["Conservateur", "Intraday", "Scalping 1m", "Ultra-Scalp"]
analyzer = SentimentIntensityAnalyzer()


# ==========================================================
# ⚡ FLUX DE PRIX DIRECT MULTI-SOURCES (AVEC PIXEL)
# ==========================================================
def obtenir_prix_live_multi_sources():
    prix_dict = {}
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        url_mexc = "https://api.mexc.com/api/v3/ticker/price"
        res = requests.get(url_mexc, headers=headers, timeout=1.5).json()
        for it in res:
            s_name = it.get("symbol", "")
            # 🌟 PIXEL AJOUTÉ AUX FLUX DE PRIX
            for base in [
                "SOL",
                "BTC",
                "ETH",
                "XRP",
                "ZEC",
                "PIPPIN",
                "BNB",
                "PIXEL",
            ]:
                if s_name == f"{base}USDT":
                    prix_dict[f"{base}/USDT"] = float(it.get("price", 0))
    except Exception:
        pass

    if not prix_dict or "SOL/USDT" not in prix_dict:
        try:
            url_binance = "https://api.binance.com/api/v3/ticker/price"
            res3 = requests.get(url_binance, headers=headers, timeout=1.5).json()
            for it in res3:
                s_name = it.get("symbol", "")
                for base in [
                    "SOL",
                    "BTC",
                    "ETH",
                    "XRP",
                    "ZEC",
                    "BNB",
                    "PIXEL",
                ]:
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
            "solana_master_auto": False,
            "positions": {},
            "historique": [],
        },
        "Alex": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "solana_master_auto": False,
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
            "solana_master_auto": False,
            "positions": {},
            "historique": [],
        }
    modificateur_fn(comptes[nom_trader])
    sauvegarder_tous_les_comptes(comptes)


# ==========================================================
# 🧠 CERVEAU COLLECTIF DE L'IA (1M XP)
# ==========================================================
def charger_experience_ia_collective():
    if os.path.exists(FICHIER_IA):
        try:
            with open(FICHIER_IA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "xp_total": 1000000,
        "niveau": "Maître Quant Suprême 🥇 (1M XP)",
        "scores_paires": {p.split("-")[0]: 1.0 for p in PAIRES_RADAR},
        "cooldowns": {
            "SMC": 0,
            "Momentum": 0,
            "Tendance": 0,
            "Squeeze Breakout": 0,
        },
        "pertes_consecutives": {
            "SMC": 0,
            "Momentum": 0,
            "Tendance": 0,
            "Squeeze Breakout": 0,
        },
        "lecons_apprises": [
            "ADN 1M XP Validé sur Solana : Grid 0.35% + Squeeze 15m (Calmar 110.43).",
            "Paire PIXEL/USDT ajoutée au radar multi-profils.",
        ],
    }


def sauvegarder_experience_ia_collective(ia_data):
    with open(FICHIER_IA, "w", encoding="utf-8") as f:
        json.dump(ia_data, f, indent=4, ensure_ascii=False)


def mettre_a_jour_ia_collective(nom_trader, paire_brute, motif_famille, win, pnl):
    ia = charger_experience_ia_collective()
    paire = paire_brute.split("/")[0]

    ia["xp_total"] += 25 if win else 5
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
    if p < 0.01:
        return f"{p:.6f}"
    elif p < 0.1:
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
            tag = (
                '<span class="tag-bull">BULLISH</span>'
                if compound >= 0.15
                else (
                    '<span class="tag-bear">BEARISH</span>'
                    if compound <= -0.15
                    else '<span class="tag-neu">NEUTRE</span>'
                )
            )
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


@st.cache_data(ttl=8)
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
                threads=False,
            )
            donnees[intervalle] = df
        except Exception:
            donnees[intervalle] = None
    return donnees


# ==========================================================
# 👑 SCANNER SOLANA MASTER 1M XP (DUAL-ENGINE 15M)
# ==========================================================
@st.cache_data(ttl=6)
def analyser_solana_master_live():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://api.mexc.com/api/v3/klines?symbol=SOLUSDT&interval=15m&limit=45"
        res = requests.get(url, headers=headers, timeout=2).json()
        if not res or not isinstance(res, list):
            return None

        df = pd.DataFrame(
            res,
            columns=[
                "time",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "close_time",
                "qav",
            ],
        )
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = df[col].astype(float)
        df["Datetime"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("Datetime", inplace=True)

        BB_MULT = 1.7
        KC_MULT = 1.7
        GRID_STEP = 0.0035

        df["SMA20"] = df["Close"].rolling(20).mean()
        df["StdDev"] = df["Close"].rolling(20).std()
        df["BB_Upper"] = df["SMA20"] + (BB_MULT * df["StdDev"])
        df["BB_Lower"] = df["SMA20"] - (BB_MULT * df["StdDev"])

        hl = df["High"] - df["Low"]
        hc = (df["High"] - df["Close"].shift()).abs()
        lc = (df["Low"] - df["Close"].shift()).abs()
        df["ATR"] = (
            pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(20).mean()
        )
        df["EMA20"] = df["Close"].ewm(span=20, adjust=False).mean()
        df["KC_Upper"] = df["EMA20"] + (KC_MULT * df["ATR"])
        df["KC_Lower"] = df["EMA20"] - (KC_MULT * df["ATR"])

        df["Squeeze_ON"] = (df["BB_Lower"] > df["KC_Lower"]) & (
            df["BB_Upper"] < df["KC_Upper"]
        )

        val = df["Close"] - (
            (df["High"].rolling(20).max() + df["Low"].rolling(20).min()) / 2.0
            + df["SMA20"]
        ) / 2.0
        df["Momentum"] = val.rolling(20).mean()
        df["EMA50"] = df["Close"].ewm(span=50, adjust=False).mean()

        last_c = df.iloc[-1]
        prev_c = df.iloc[-2]

        p = float(last_c["Close"])
        atr = float(last_c["ATR"])
        sq_on = bool(last_c["Squeeze_ON"])
        mom = float(last_c["Momentum"])
        e50 = float(last_c["EMA50"])

        grid_levels = []
        for lvl in range(1, 4):
            grid_levels.append(
                {
                    "lvl": lvl,
                    "buy": round(p * (1 - (lvl * GRID_STEP)), 2),
                    "sell": round(p * (1 + (lvl * GRID_STEP)), 2),
                }
            )

        breakout_signal = None
        dist = max(atr * 1.2, p * 0.012)
        if not sq_on and abs(mom) > 0.03:
            if mom > 0 and p > e50:
                breakout_signal = {
                    "sens": "LONG 🟢",
                    "entree": p,
                    "sl": round(p - dist, 2),
                    "tp1": round(p + (2.2 * dist), 2),
                    "tp2": round(p + (4.5 * dist), 2),
                    "dist": dist,
                    "levier": 25,
                }
            elif mom < 0 and p < e50:
                breakout_signal = {
                    "sens": "SHORT 🔴",
                    "entree": p,
                    "sl": round(p + dist, 2),
                    "tp1": round(p - (2.2 * dist), 2),
                    "tp2": round(p - (4.5 * dist), 2),
                    "dist": dist,
                    "levier": 25,
                }

        return {
            "prix": p,
            "atr": atr,
            "squeeze_on": sq_on,
            "momentum": mom,
            "ema50": e50,
            "grid_levels": grid_levels,
            "grid_step": GRID_STEP * 100,
            "breakout_signal": breakout_signal,
        }
    except Exception:
        return None


def detecter_setup_a_plus_du_jour(donnees_globales):
    df_15m = donnees_globales.get("15m")
    df_1m = donnees_globales.get("1m")

    if df_15m is None or df_1m is None:
        return None

    setups_valides = []
    for paire in PAIRES_RADAR:
        nom_court = paire.split("-")[0]
        try:
            df_15 = (
                df_15m[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else df_15m.dropna()
            )
            df_1 = (
                df_1m[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else df_1m.dropna()
            )
            if len(df_15) < 30 or len(df_1) < 20:
                continue

            prix = float(df_1["Close"].iloc[-1])
            high_15 = float(df_15["High"].iloc[-1])
            low_15 = float(df_15["Low"].iloc[-1])

            df_15["EMA_50"] = df_15["Close"].ewm(span=50, adjust=False).mean()
            ema_50 = float(df_15["EMA_50"].iloc[-1])

            high_s = float(df_15["High"].iloc[-17:-1].max())
            low_s = float(df_15["Low"].iloc[-17:-1].min())

            hl = df_15["High"] - df_15["Low"]
            hc = (df_15["High"] - df_15["Close"].shift()).abs()
            lc = (df_15["Low"] - df_15["Close"].shift()).abs()
            atr_15 = float(
                pd.concat([hl, hc, lc], axis=1)
                .max(axis=1)
                .rolling(14)
                .mean()
                .iloc[-1]
            )

            sweep_h = any(
                df_15["High"].iloc[-k] > high_s and df_15["Close"].iloc[-k] < high_s
                for k in range(1, 3)
            )
            sweep_l = any(
                df_15["Low"].iloc[-k] < low_s and df_15["Close"].iloc[-k] > low_s
                for k in range(1, 3)
            )

            fvg_bear = (df_15["Low"].iloc[-3] > high_15) and (
                (df_15["Low"].iloc[-3] - high_15) > (atr_15 * 0.15)
            )
            fvg_bull = (low_15 > df_15["High"].iloc[-3]) and (
                (low_15 - df_15["High"].iloc[-3]) > (atr_15 * 0.15)
            )

            if (sweep_h or fvg_bear) and (prix < ema_50):
                entree_opt = high_s
                dist = max(high_15 - entree_opt + (0.05 * atr_15), 0.35 * atr_15)
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
                            "motif": "Sweep Majeur 15m + FVG (Amplitude 4h)",
                        }
                    )

            elif (sweep_l or fvg_bull) and (prix > ema_50):
                entree_opt = low_s
                dist = max(entree_opt - low_15 + (0.05 * atr_15), 0.35 * atr_15)
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
                            "motif": "Sweep Majeur 15m + FVG (Amplitude 4h)",
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

    data_15m = donnees_globales.get("15m")
    data_1m = donnees_globales.get("1m")
    if data_1m is None or data_15m is None:
        return []

    resultats = []
    for paire in PAIRES_RADAR:
        nom_court = paire.split("-")[0]
        try:
            df_15 = (
                data_15m[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else data_15m.dropna()
            )
            df_1 = (
                data_1m[paire].dropna()
                if len(PAIRES_RADAR) > 1
                else data_1m.dropna()
            )
            if len(df_15) < 20 or len(df_1) < 25:
                continue

            high_s_15 = float(df_15["High"].iloc[-16:-1].max())
            low_s_15 = float(df_15["Low"].iloc[-16:-1].min())
            df_15["EMA_50"] = df_15["Close"].ewm(span=50, adjust=False).mean()
            ema_50_15 = float(df_15["EMA_50"].iloc[-1])

            sweep_15_h = any(
                df_15["High"].iloc[-k] > high_s_15
                and df_15["Close"].iloc[-k] < high_s_15
                for k in range(1, 3)
            )
            sweep_15_l = any(
                df_15["Low"].iloc[-k] < low_s_15
                and df_15["Close"].iloc[-k] > low_s_15
                for k in range(1, 3)
            )

            prix = float(df_1["Close"].iloc[-1])
            open_p = float(df_1["Open"].iloc[-1])
            high = float(df_1["High"].iloc[-1])
            low = float(df_1["Low"].iloc[-1])
            high_s_1m = float(df_1["High"].iloc[-9:-2].max())
            low_s_1m = float(df_1["Low"].iloc[-9:-2].min())

            d = df_1["Close"].diff()
            g = d.where(d > 0, 0).rolling(7).mean()
            l = (-d.where(d < 0, 0)).rolling(7).mean()
            rsi_val = float((100 - (100 / (1 + (g / l)))).iloc[-1])

            hl = df_1["High"] - df_1["Low"]
            hc = (df_1["High"] - df_1["Close"].shift()).abs()
            lc = (df_1["Low"] - df_1["Close"].shift()).abs()
            atr_1m = float(
                pd.concat([hl, hc, lc], axis=1)
                .max(axis=1)
                .rolling(14)
                .mean()
                .iloc[-1]
            )

            df_1["Vol_MA"] = df_1["Volume"].rolling(15).mean()
            vol_fort = df_1["Volume"].iloc[-1] > (1.35 * df_1["Vol_MA"].iloc[-1])
            gros_corps = abs(prix - open_p) > (1.0 * atr_1m)

            fvg_bear_1m = (df_1["Low"].iloc[-3] > high) and (
                (df_1["Low"].iloc[-3] - high) > (atr_1m * 0.15)
            )
            fvg_bull_1m = (low > df_1["High"].iloc[-3]) and (
                (low - df_1["High"].iloc[-3]) > (atr_1m * 0.15)
            )

            mss_baissier = (prix < low_s_1m) and (prix < open_p)
            mss_haussier = (prix > high_s_1m) and (prix > open_p)

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
                if (
                    prix < ema_50_15
                    and sweep_15_h
                    and mss_baissier
                    and gros_corps
                ):
                    signal, motif = (
                        "🔴 SHORT",
                        "MSS 15m + Sweep Majeur",
                    )
                    opt_p = low_s_1m
                    dist = max(high - opt_p + (0.05 * atr_1m), 0.40 * atr_1m)
                    sl = opt_p + dist
                    tp1 = opt_p - (1.8 * dist)
                    tp2 = opt_p - (3.5 * dist)
                elif (
                    prix > ema_50_15
                    and sweep_15_l
                    and mss_haussier
                    and gros_corps
                ):
                    signal, motif = (
                        "🟢 LONG",
                        "MSS 15m + Sweep Majeur",
                    )
                    opt_p = high_s_1m
                    dist = max(opt_p - low + (0.05 * atr_1m), 0.40 * atr_1m)
                    sl = opt_p - dist
                    tp1 = opt_p + (1.8 * dist)
                    tp2 = opt_p + (3.5 * dist)

            elif profil_court == "Intraday":
                motif_famille = "SMC"
                if en_killzone and (sweep_15_h or sweep_15_l):
                    if (
                        sweep_15_h
                        and mss_baissier
                        and (fvg_bear_1m or vol_fort)
                    ):
                        signal, motif = "🔴 SHORT", "Killzone MSS + FVG"
                        opt_p = low_s_1m
                        dist = max(
                            high - opt_p + (0.05 * atr_1m), 0.35 * atr_1m
                        )
                        sl = opt_p + dist
                        tp1 = opt_p - (1.8 * dist)
                        tp2 = opt_p - (3.2 * dist)
                    elif (
                        sweep_15_l
                        and mss_haussier
                        and (fvg_bull_1m or vol_fort)
                    ):
                        signal, motif = "🟢 LONG", "Killzone MSS + FVG"
                        opt_p = high_s_1m
                        dist = max(
                            opt_p - low + (0.05 * atr_1m), 0.35 * atr_1m
                        )
                        sl = opt_p - dist
                        tp1 = opt_p + (1.8 * dist)
                        tp2 = opt_p + (3.2 * dist)

            elif profil_court == "Scalping 1m":
                motif_famille = "Momentum"
                if atr_1m >= 0.08 and vol_fort:
                    if (
                        (prix < ema_50_15)
                        and mss_baissier
                        and (fvg_bear_1m or gros_corps)
                    ):
                        signal, motif = (
                            "🔴 SHORT",
                            "MSS 1m + Momentum",
                        )
                        opt_p = prix
                        dist = max(
                            high - prix + (0.04 * atr_1m), 0.30 * atr_1m
                        )
                        sl = prix + dist
                        tp1 = prix - (1.8 * dist)
                        tp2 = prix - (3.5 * dist)
                    elif (
                        (prix > ema_50_15)
                        and mss_haussier
                        and (fvg_bull_1m or gros_corps)
                    ):
                        signal, motif = (
                            "🟢 LONG",
                            "MSS 1m + Momentum",
                        )
                        opt_p = prix
                        dist = max(prix - low + (0.04 * atr_1m), 0.30 * atr_1m)
                        sl = prix - dist
                        tp1 = prix + (1.8 * dist)
                        tp2 = prix + (3.5 * dist)

            else:
                motif_famille = "SMC"
                if atr_1m >= 0.08:
                    if (
                        (sweep_15_h or prix < ema_50_15)
                        and mss_baissier
                        and fvg_bear_1m
                    ):
                        signal, motif = (
                            "🔴 SHORT",
                            "Ancrage 15m ➔ FVG 1m",
                        )
                        opt_p = float(df_1["Low"].iloc[-3])
                        dist = max(
                            high - opt_p + (0.04 * atr_1m), 0.25 * atr_1m
                        )
                        sl = opt_p + dist
                        tp1 = opt_p - (1.8 * dist)
                        tp2 = opt_p - (3.8 * dist)
                    elif (
                        (sweep_15_l or prix > ema_50_15)
                        and mss_haussier
                        and fvg_bull_1m
                    ):
                        signal, motif = (
                            "🟢 LONG",
                            "Ancrage 15m ➔ FVG 1m",
                        )
                        opt_p = float(df_1["High"].iloc[-3])
                        dist = max(opt_p - low + (0.04 * atr_1m), 0.25 * atr_1m)
                        sl = opt_p - dist
                        tp1 = opt_p + (1.8 * dist)
                        tp2 = opt_p + (3.8 * dist)

            en_cooldown = ts_actuel < ia_data.get("cooldowns", {}).get(
                motif_famille, 0
            )
            if signal and en_cooldown:
                signal = None

            nom_paire = f"{nom_court}/USDT"
            resultats.append(
                {
                    "Paire": nom_paire,
                    "Prix": prix,
                    "High": high,
                    "Low": low,
                    "Range_Str": f"[{formater_prix(low_s_15)} - {formater_prix(high_s_15)}]",
                    "Signal_Detecte": signal,
                    "Motif": motif,
                    "Motif_Famille": motif_famille,
                    "Opt_Price": opt_p,
                    "SL": sl,
                    "TP1": tp1,
                    "TP2": tp2,
                    "RSI": f"{rsi_val:.1f}",
                    "Intervalle": "1m",
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
                    "solana_master_auto": False,
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
        "solana_master_auto": False,
        "positions": {},
        "historique": [],
    },
)

# ==========================================================
# 🎛️ EN-TÊTE FIXE DU COCKPIT D'ORIGINE
# ==========================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(
        f"### ⚡ Cockpit Pro <span class='user-badge'>👤 {trader_courant}</span>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.caption(f"🕒 Heure de Paris : **{obtenir_date_heure_paris()}**")

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

if "memoire_par_profil" not in st.session_state:
    st.session_state.memoire_par_profil = {p: {} for p in LISTE_PROFILS}


# ==========================================================
# 🌟 FRAGMENT AUTO-ACTUALISÉ FLUIDE
# ==========================================================
@st.fragment(run_every="8s")
def bloc_live_auto_actualise():
    maintenant_ts = time.time()
    prix_mexc_direct = obtenir_prix_live_multi_sources()
    donnees_globales = charger_donnees_marche_globales()
    sol_master_data = analyser_solana_master_live()

    # 1. Setup A+ Royal du jour
    setup_a_plus = detecter_setup_a_plus_du_jour(donnees_globales)
    if setup_a_plus:
        st.markdown(
            f"""
        <div class="gold-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="gold-title">👑 SETUP A+ DU JOUR : {setup_a_plus['paire']} ({setup_a_plus['sens']})</span>
                <span style="color:#00E6
