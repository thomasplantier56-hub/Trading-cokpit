from concurrent.futures import ThreadPoolExecutor
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

# Fuseau horaire Paris
try:
    import zoneinfo

    TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
except Exception:
    TZ_PARIS = datetime.timezone(datetime.timedelta(hours=2))


def obtenir_date_heure_paris(format_str="%H:%M:%S"):
    return datetime.datetime.now(TZ_PARIS).strftime(format_str)


st.set_page_config(
    page_title="Cockpit Trader Pro Live - Multi-Crypto Master",
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
    
    .pos-card { background-color: #0D1117; border-radius: 8px; padding: 12px; border: 1px solid #30363D; margin-bottom: 10px; }
    .alert-card-long { background-color: #04140B; border-radius: 8px; padding: 12px; border: 1px solid #00E676; margin-bottom: 10px; box-shadow: 0 0 15px rgba(0, 230, 118, 0.1); }
    .alert-card-short { background-color: #170508; border-radius: 8px; padding: 12px; border: 1px solid #FF1744; margin-bottom: 10px; box-shadow: 0 0 15px rgba(255, 23, 68, 0.1); }
    .opt-price { color: #FFD700; font-size: 16px; font-weight: bold; }
    .timer-badge { background-color: #161B22; color: #00E676; padding: 3px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; border: 1px solid #30363D; }
    .status-expired { background-color: rgba(255, 23, 68, 0.15); color: #FF1744; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; }
    .status-valid { background-color: rgba(0, 230, 118, 0.15); color: #00E676; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px; }
    
    .mexc-btn {
        background: linear-gradient(135deg, #0d1f18 0%, #06140e 100%);
        color: #14F195 !important;
        text-decoration: none !important;
        font-weight: bold;
        padding: 6px 12px;
        border-radius: 6px;
        border: 1px solid #14F195;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        transition: all 0.2s ease;
        margin-top: 4px;
    }
    .mexc-btn:hover {
        background: #14F195 !important;
        color: #000000 !important;
        box-shadow: 0 0 12px rgba(20, 241, 149, 0.4);
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==========================================================
# ☁️ CONNECTEUR CLOUD UPSTASH REDIS
# ==========================================================
def get_upstash_credentials():
    try:
        url = st.secrets.get("UPSTASH_REDIS_REST_URL")
        token = st.secrets.get("UPSTASH_REDIS_REST_TOKEN")
        if url and token:
            return url.strip(), token.strip()
    except Exception:
        pass
    return None, None


def cloud_get(key):
    url, token = get_upstash_credentials()
    if not url or not token:
        return None
    try:
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=["GET", key],
            timeout=3,
        )
        res = r.json()
        val = res.get("result")
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


def cloud_set(key, data):
    url, token = get_upstash_credentials()
    if not url or not token:
        return False
    try:
        requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=["SET", key, json.dumps(data, ensure_ascii=False)],
            timeout=3,
        )
        return True
    except Exception:
        return False


# ==========================================================
# 🌐 DICTIONNAIRE BILINGUE
# ==========================================================
I18N = {
    "FR": {
        "cockpit_title": "Cockpit Pro",
        "paris_time": "Heure de Paris :",
        "user_space": "Espace Utilisateur",
        "connected_as": "Connecté en tant que :",
        "create_profile": "Créer un profil",
        "input_name": "Prénom / Pseudo :",
        "validate": "Valider",
        "manage_pairs": "Gestion des Paires Radar",
        "manage_pairs_sub": "Ajoutez ou retirez des cryptos pour le radar :",
        "add_crypto_ph": "Ajouter (ex: DOGE, SUI, NEAR) :",
        "add_crypto_btn": "➕ Ajouter au Radar",
        "monitored_pairs": "Paires surveillées :",
        "active_profile": "Profil actif :",
        "setup_a_title": "SETUP A+ DU JOUR",
        "setup_a_waiting": "👑 <b>SETUP A+ DU JOUR :</b> ⚪ En attente. L'IA surveille le prochain alignement 5 étoiles !",
        "target_gain": "Gain Visé :",
        "optimal_entry": "Entrée Optimale (Limit) :",
        "stop_loss": "Stop-Loss :",
        "take_profit_royal": "Take-Profit Royal (Ratio 1:4.2) :",
        "suggested_margin": "Marge Conseillée :",
        "risk": "Risque :",
        "open_mexc": "🚀 Ouvrir {pair} sur MEXC Futures ↗️",
        "trader_on_mexc": "🚀 Trader {pair} sur MEXC Futures ↗️",
        "manage_on_mexc": "🚀 Gérer {pair} sur MEXC ↗️",
        "veille": "⚪ En veille",
        "tab_auto": "🤖 Auto ({user})",
        "tab_radar": "⚡ Radar ({profile})",
        "tab_master": "👑 Crypto Master (1M XP)",
        "tab_ia": "🧠 Cerveau IA",
        "tab_rank": "🏆 Classement",
        "tab_calc": "🧮 Calculateur",
        "balance_realized": "Solde Réalisé :",
        "toggle_auto_radar": "⚡ AUTO MULTI-RADAR",
        "reset_btn": "🔄 Reset solde à 1000 USDT",
        "open_pos_title": "🚀 Positions Ouvertes en Direct :",
        "no_open_pos": "👀 Aucune position ouverte pour le moment.",
        "recent_closed": "📜 Derniers Trades Clôturés :",
        "cut_btn": "🛑 Couper",
        "running_since": "En cours depuis :",
        "waiting": "⏳ Attente",
        "breakeven": "✅ Breakeven Verrouillé",
        "master_header": "👑 Crypto Master (Modèle 100 USDT)",
        "toggle_master_auto": "⚡ AUTOPILOTE MASTER",
        "master_auto_on": "🟢 AUTOPILOTE ACTIF : L'IA prend automatiquement tous les Breakouts 1M XP.",
        "master_auto_off": "⚪ MODE MANUEL : Surveillez les alertes ci-dessous et cliquez pour ouvrir un trade.",
        "regime_detected": "Régime Détecté (15m) :",
        "regime_comp": "🟢 COMPRESSION ACTIVE : MODE GRID MAKER (0% FEES)",
        "regime_exp": "🚀 EXPANSION : MODE SQUEEZE BREAKOUT",
        "regime_trans": "⚪ EN TRANSITION",
        "grid_title": "Grille Maker 0.35% (Ordres Post-Only MEXC) :",
        "orders_buy": "🛒 Ordres Achat Limit :",
        "orders_sell": "💰 Ordres Vente Limit :",
        "signal_breakout": "🚀 SIGNAL BREAKOUT 1M XP : {pair} {sens} (Levier x{lev})",
        "take_breakout_btn": "⚡ Prendre ce Breakout sur mon compte ({user})",
        "take_signal_btn": "⚡ Prendre {sens} sur {pair} ({user})",
        "status_valid": "🟢 ENTRÉE VALIDE",
        "status_expired": "⚠️ PÉRIMÉ (Le cours est déjà parti)",
        "pair_col": "Paire",
        "price_col": "Prix Actuel",
        "status_col": "Statut",
        "ia_level": "🏆 Niveau :",
        "ia_sub": "Chaque trade clôturé améliore les filtres de tout le groupe.",
        "calc_entry": "Entrée ($)",
        "calc_sl": "SL ($)",
        "calc_margin": "Marge (USDT)",
        "calc_liquidation": "Liquidation :",
    },
    "EN": {
        "cockpit_title": "Cockpit Pro",
        "paris_time": "Paris Time:",
        "user_space": "User Space",
        "connected_as": "Logged in as:",
        "create_profile": "Create Profile",
        "input_name": "Name / Handle:",
        "validate": "Submit",
        "manage_pairs": "Radar Pair Manager",
        "manage_pairs_sub": "Add or remove cryptos for live radar scanning:",
        "add_crypto_ph": "Add (e.g. DOGE, SUI, NEAR):",
        "add_crypto_btn": "➕ Add to Radar",
        "monitored_pairs": "Monitored Pairs:",
        "active_profile": "Active Profile:",
        "setup_a_title": "DAILY A+ SETUP",
        "setup_a_waiting": "👑 <b>DAILY A+ SETUP:</b> ⚪ Waiting. AI scanning for the next 5-star alignment!",
        "target_gain": "Target Gain:",
        "optimal_entry": "Optimal Entry (Limit):",
        "stop_loss": "Stop-Loss:",
        "take_profit_royal": "Royal Take-Profit (1:4.2 Ratio):",
        "suggested_margin": "Suggested Margin:",
        "risk": "Risk:",
        "open_mexc": "🚀 Open {pair} on MEXC Futures ↗️",
        "trader_on_mexc": "🚀 Trade {pair} on MEXC Futures ↗️",
        "manage_on_mexc": "🚀 Manage {pair} on MEXC ↗️",
        "veille": "⚪ Scanning",
        "tab_auto": "🤖 Auto ({user})",
        "tab_radar": "⚡ Radar ({profile})",
        "tab_master": "👑 Crypto Master (1M XP)",
        "tab_ia": "🧠 AI Brain",
        "tab_rank": "🏆 Leaderboard",
        "tab_calc": "🧮 Calculator",
        "balance_realized": "Realized Balance:",
        "toggle_auto_radar": "⚡ AUTO MULTI-RADAR",
        "reset_btn": "🔄 Reset balance to 1000 USDT",
        "open_pos_title": "🚀 Live Open Positions:",
        "no_open_pos": "👀 No active open positions right now.",
        "recent_closed": "📜 Recent Closed Trades:",
        "cut_btn": "🛑 Close",
        "running_since": "Running for:",
        "waiting": "⏳ Pending",
        "breakeven": "✅ Locked Breakeven",
        "master_header": "👑 Crypto Master (100 USDT Model)",
        "toggle_master_auto": "⚡ MASTER AUTOPILOT",
        "master_auto_on": "🟢 AUTOPILOT ACTIVE: AI executes all 1M XP Breakouts automatically.",
        "master_auto_off": "⚪ MANUAL MODE: Monitor alerts below and click to open a trade.",
        "regime_detected": "Detected Regime (15m):",
        "regime_comp": "🟢 ACTIVE COMPRESSION: GRID MAKER MODE (0% FEES)",
        "regime_exp": "🚀 EXPANSION: SQUEEZE BREAKOUT MODE",
        "regime_trans": "⚪ IN TRANSITION",
        "grid_title": "0.35% Maker Grid (MEXC Post-Only Orders):",
        "orders_buy": "🛒 Limit Buy Orders:",
        "orders_sell": "💰 Limit Sell Orders:",
        "signal_breakout": "🚀 1M XP BREAKOUT SIGNAL: {pair} {sens} (x{lev} Leverage)",
        "take_breakout_btn": "⚡ Take this Breakout on my account ({user})",
        "take_signal_btn": "⚡ Take {sens} on {pair} ({user})",
        "status_valid": "🟢 VALID ENTRY",
        "status_expired": "⚠️ EXPIRED (Price already ran away)",
        "pair_col": "Pair",
        "price_col": "Current Price",
        "status_col": "Status",
        "ia_level": "🏆 Level:",
        "ia_sub": "Every closed trade enhances the shared multi-pair filters.",
        "calc_entry": "Entry ($)",
        "calc_sl": "SL ($)",
        "calc_margin": "Margin (USDT)",
        "calc_liquidation": "Liquidation:",
    },
}

FICHIER_COMPTES = "comptes_traders.json"
FICHIER_IA = "experience_ia_collective.json"
FICHIER_PAIRES = "paires_radar.json"

LISTE_PROFILS = ["Conservateur", "Intraday", "Scalping 1m", "Ultra-Scalp"]
analyzer = SentimentIntensityAnalyzer()

PARAMETRES_STRATS = {
    "Ultra-Scalp": {"levier": 150, "marge": 25.0, "max_duree_sec": 720},
    "Scalping 1m": {"levier": 100, "marge": 35.0, "max_duree_sec": 1080},
    "Intraday": {"levier": 50, "marge": 50.0, "max_duree_sec": 2700},
    "Conservateur": {"levier": 20, "marge": 100.0, "max_duree_sec": 7200},
    "Master": {"levier": 25, "marge": 100.0, "max_duree_sec": 5400},
}


# ==========================================================
# 🪙 GESTION HYBRIDE DES PAIRES
# ==========================================================
def charger_paires_radar():
    p_cloud = cloud_get("paires_radar")
    if p_cloud and isinstance(p_cloud, list) and len(p_cloud) > 0:
        return p_cloud

    if os.path.exists(FICHIER_PAIRES):
        try:
            with open(FICHIER_PAIRES, "r", encoding="utf-8") as f:
                p = json.load(f)
                if p and isinstance(p, list):
                    return p
        except Exception:
            pass

    paires_defaut = [
        "SOL",
        "BTC",
        "ETH",
        "XRP",
        "ZEC",
        "PIPPIN",
        "BNB",
        "PIXEL",
    ]
    sauvegarder_paires_radar(paires_defaut)
    return paires_defaut


def sauvegarder_paires_radar(paires_list):
    cloud_set("paires_radar", paires_list)
    try:
        with open(FICHIER_PAIRES, "w", encoding="utf-8") as f:
            json.dump(paires_list, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def get_mexc_futures_url(paire_str):
    base = (
        paire_str.replace("/USDT", "")
        .replace("-USD", "")
        .replace("USDT", "")
        .strip()
        .upper()
    )
    return f"https://futures.mexc.com/exchange/{base}_USDT"


# ==========================================================
# ⚡ FLUX BOUGIES ET PRIX 100% MEXC NATIVE
# ==========================================================
def obtenir_prix_live_multi_sources(bases_actives):
    prix_dict = {}
    try:
        url_mexc = "https://api.mexc.com/api/v3/ticker/price"
        res = requests.get(
            url_mexc, headers={"User-Agent": "Mozilla/5.0"}, timeout=1.5
        ).json()
        for it in res:
            s_name = it.get("symbol", "")
            for base in bases_actives:
                if s_name == f"{base}USDT":
                    prix_dict[f"{base}/USDT"] = float(it.get("price", 0))
    except Exception:
        pass
    return prix_dict


def fetch_single_mexc_kline(base, interval, limit=60):
    try:
        url = f"https://api.mexc.com/api/v3/klines?symbol={base}USDT&interval={interval}&limit={limit}"
        res = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=2
        ).json()
        if not res or not isinstance(res, list):
            return base, None
        df = pd.DataFrame(
            res,
            columns=[
                "time",
                "Open",
                "High",
                "Low",
                "Close",
                "Volume",
                "c_time",
                "qav",
            ],
        )
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df[col] = df[col].astype(float)
        df["Datetime"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("Datetime", inplace=True)
        return base, df[["Open", "High", "Low", "Close", "Volume"]]
    except Exception:
        return base, None


@st.cache_data(ttl=8)
def charger_donnees_marche_globales(bases_actives):
    donnees = {"15m": {}, "5m": {}, "1m": {}}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for interval in ["15m", "5m", "1m"]:
            for base in bases_actives:
                futures.append(
                    (
                        interval,
                        executor.submit(
                            fetch_single_mexc_kline, base, interval, 60
                        ),
                    )
                )
        for interval, fut in futures:
            base, df = fut.result()
            if df is not None:
                donnees[interval][base] = df
    return donnees


# ==========================================================
# 📊 CALCULATEUR MULTI-TIMEFRAME
# ==========================================================
def calculer_rsi_series(series, period=14):
    d = series.diff()
    g = d.where(d > 0, 0).rolling(period).mean()
    l = (-d.where(d < 0, 0)).rolling(period).mean()
    rs = g / (l + 1e-9)
    return 100 - (100 / (1 + rs))


@st.cache_data(ttl=15)
def obtenir_stats_mtf_radar(nom_court):
    stats = {
        "range_15m": "N/A",
        "rsi_15m": "50.0",
        "range_30m": "N/A",
        "rsi_30m": "50.0",
        "range_1h": "N/A",
        "rsi_1h": "50.0",
        "range_4h": "N/A",
        "rsi_4h": "50.0",
        "range_1d": "N/A",
        "rsi_1d": "50.0",
    }
    try:
        _, df_15 = fetch_single_mexc_kline(nom_court, "15m", 120)
        _, df_1d = fetch_single_mexc_kline(nom_court, "1d", 30)

        if df_15 is not None and len(df_15) >= 20:
            rsi_15 = float(calculer_rsi_series(df_15["Close"], 14).iloc[-1])
            high_15 = float(df_15["High"].iloc[-16:].max())
            low_15 = float(df_15["Low"].iloc[-16:].min())
            stats["range_15m"] = f"[{formater_prix(low_15)} - {formater_prix(high_15)}]"
            stats["rsi_15m"] = f"{rsi_15:.1f}"

            df_30 = (
                df_15.resample("30min")
                .agg({"High": "max", "Low": "min", "Close": "last"})
                .dropna()
            )
            if len(df_30) >= 14:
                rsi_30 = float(calculer_rsi_series(df_30["Close"], 14).iloc[-1])
                high_30 = float(df_30["High"].iloc[-16:].max())
                low_30 = float(df_30["Low"].iloc[-16:].min())
                stats["range_30m"] = (
                    f"[{formater_prix(low_30)} - {formater_prix(high_30)}]"
                )
                stats["rsi_30m"] = f"{rsi_30:.1f}"

            df_1h = (
                df_15.resample("1h")
                .agg({"High": "max", "Low": "min", "Close": "last"})
                .dropna()
            )
            if len(df_1h) >= 14:
                rsi_1h = float(calculer_rsi_series(df_1h["Close"], 14).iloc[-1])
                high_1h = float(df_1h["High"].iloc[-24:].max())
                low_1h = float(df_1h["Low"].iloc[-24:].min())
                stats["range_1h"] = (
                    f"[{formater_prix(low_1h)} - {formater_prix(high_1h)}]"
                )
                stats["rsi_1h"] = f"{rsi_1h:.1f}"

            df_4h = (
                df_15.resample("4h")
                .agg({"High": "max", "Low": "min", "Close": "last"})
                .dropna()
            )
            if len(df_4h) >= 5:
                rsi_4h = float(
                    calculer_rsi_series(df_4h["Close"], min(len(df_4h) - 1, 14)).iloc[-1]
                )
                high_4h = float(df_4h["High"].iloc[-12:].max())
                low_4h = float(df_4h["Low"].iloc[-12:].min())
                stats["range_4h"] = (
                    f"[{formater_prix(low_4h)} - {formater_prix(high_4h)}]"
                )
                stats["rsi_4h"] = f"{rsi_4h:.1f}"

        if df_1d is not None and len(df_1d) >= 14:
            rsi_1d = float(calculer_rsi_series(df_1d["Close"], 14).iloc[-1])
            high_1d = float(df_1d["High"].iloc[-14:].max())
            low_1d = float(df_1d["Low"].iloc[-14:].min())
            stats["range_1d"] = (
                f"[{formater_prix(low_1d)} - {formater_prix(high_1d)}]"
            )
            stats["rsi_1d"] = f"{rsi_1d:.1f}"
    except Exception:
        pass
    return stats


# ==========================================================
# 👥 GESTION DES COMPTES (AUTO-RÉPARATION DU FORMAT)
# ==========================================================
def valider_format_comptes(data):
    """Vérifie si les données sont un dictionnaire valide de comptes et non un compte unique."""
    if not isinstance(data, dict):
        return False
    if "solde" in data or "capital_initial" in data:
        # Fichier corrompu par un objet de compte unique
        return False
    for k, v in data.items():
        if not isinstance(v, dict) or "solde" not in v:
            return False
    return True


def charger_tous_les_comptes():
    comptes_defaut = {
        "Thomas": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "master_auto": False,
            "positions": {},
            "historique": [],
        },
        "Alex": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "master_auto": False,
            "positions": {},
            "historique": [],
        },
        "Yeepse": {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "master_auto": False,
            "positions": {},
            "historique": [],
        },
    }

    # 1. Tentative Cloud Upstash
    c_cloud = cloud_get("comptes_traders")
    if c_cloud and valider_format_comptes(c_cloud):
        for k, v in comptes_defaut.items():
            if k not in c_cloud:
                c_cloud[k] = v
        return c_cloud

    # 2. Tentative Fichier Local
    if os.path.exists(FICHIER_COMPTES):
        try:
            with open(FICHIER_COMPTES, "r", encoding="utf-8") as f:
                c_charge = json.load(f)
                if valider_format_comptes(c_charge):
                    for k, v in comptes_defaut.items():
                        if k not in c_charge:
                            c_charge[k] = v
                    return c_charge
        except Exception:
            pass

    # 3. Réparation automatique immédiate
    sauvegarder_tous_les_comptes(comptes_defaut)
    return comptes_defaut


def sauvegarder_tous_les_comptes(comptes):
    if not valider_format_comptes(comptes):
        return  # Refuse d'écraser avec une structure corrompue
    cloud_set("comptes_traders", comptes)
    try:
        with open(FICHIER_COMPTES, "w", encoding="utf-8") as f:
            json.dump(comptes, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def mettre_a_jour_un_compte(nom_trader, modificateur_fn):
    comptes = charger_tous_les_comptes()
    if nom_trader not in comptes:
        comptes[nom_trader] = {
            "solde": 1000.0,
            "capital_initial": 1000.0,
            "auto_actif": False,
            "master_auto": False,
            "positions": {},
            "historique": [],
        }
    modificateur_fn(comptes[nom_trader])
    sauvegarder_tous_les_comptes(comptes)


def charger_experience_ia_collective(bases_actives):
    ia_cloud = cloud_get("experience_ia")
    if ia_cloud and isinstance(ia_cloud, dict):
        return ia_cloud

    if os.path.exists(FICHIER_IA):
        try:
            with open(FICHIER_IA, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "xp_total": 1000000,
        "niveau": "Maître Quant Suprême 🥇 (1M XP)",
        "scores_paires": {p: 1.0 for p in bases_actives},
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
            "ADN 1M XP Actif : Squeeze 15m + Grille 0.35% Maker (Profit Factor 3.08).",
            "Auto-réparation de base de données activée.",
        ],
    }


def sauvegarder_experience_ia_collective(ia_data):
    cloud_set("experience_ia", ia_data)
    try:
        with open(FICHIER_IA, "w", encoding="utf-8") as f:
            json.dump(ia_data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def mettre_a_jour_ia_collective(nom_trader, paire_brute, motif_famille, win, pnl):
    paires_actives = charger_paires_radar()
    ia = charger_experience_ia_collective(paires_actives)
    paire = (
        paire_brute.split("/")[0]
        .split("-")[0]
        .replace("USDT", "")
        .strip()
        .upper()
    )
    ia["xp_total"] += 25 if win else 5
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
    if p < 0.001:
        return f"{p:.7f}"
    elif p < 0.01:
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


# ==========================================================
# 👑 MOTEUR UNIVERSEL CRYPTO MASTER (15M)
# ==========================================================
@st.cache_data(ttl=6)
def analyser_crypto_master_live(symbol_base):
    try:
        _, df = fetch_single_mexc_kline(symbol_base, "15m", 45)
        if df is None or len(df) < 25:
            return None

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
                    "buy": round(p * (1 - (lvl * GRID_STEP)), 6),
                    "sell": round(p * (1 + (lvl * GRID_STEP)), 6),
                }
            )

        breakout_signal = None
        dist = max(atr * 1.2, p * 0.010)
        if not sq_on and abs(mom) > 0.03:
            if mom > 0 and p > e50:
                breakout_signal = {
                    "sens": "LONG 🟢",
                    "entree": p,
                    "sl": round(p - dist, 6),
                    "tp1": round(p + (2.2 * dist), 6),
                    "tp2": round(p + (4.5 * dist), 6),
                    "dist": dist,
                    "levier": 25,
                    "marge": 100.0,
                }
            elif mom < 0 and p < e50:
                breakout_signal = {
                    "sens": "SHORT 🔴",
                    "entree": p,
                    "sl": round(p + dist, 6),
                    "tp1": round(p - (2.2 * dist), 6),
                    "tp2": round(p - (4.5 * dist), 6),
                    "dist": dist,
                    "levier": 25,
                    "marge": 100.0,
                }

        return {
            "sym": symbol_base,
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


# ==========================================================
# 🎯 SETUP A+ DYNAMIQUE SUR RETEST
# ==========================================================
def detecter_setup_a_plus_du_jour(donnees_globales, bases_actives):
    data_15m = donnees_globales.get("15m", {})
    data_1m = donnees_globales.get("1m", {})

    setups_valides = []
    for nom_court in bases_actives:
        try:
            df_15 = data_15m.get(nom_court)
            df_1 = data_1m.get(nom_court)

            if df_15 is None or df_1 is None or len(df_15) < 20 or len(df_1) < 20:
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
                entree_opt = prix
                dist = max(
                    high_15 - entree_opt + (0.15 * atr_15),
                    0.50 * atr_15,
                    prix * 0.008,
                )
                sl = entree_opt + dist
                tp = entree_opt - (4.2 * dist)
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
                        "motif": "Sweep 15m + Rejet Pullback FVG",
                    }
                )
            elif (sweep_l or fvg_bull) and (prix > ema_50):
                entree_opt = prix
                dist = max(
                    entree_opt - low_15 + (0.15 * atr_15),
                    0.50 * atr_15,
                    prix * 0.008,
                )
                sl = entree_opt - dist
                tp = entree_opt + (4.2 * dist)
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
                        "motif": "Sweep 15m + Rebond Pullback FVG",
                    }
                )
        except Exception:
            continue
    return setups_valides[0] if setups_valides else None


# ==========================================================
# ⚡ MOTEUR RADAR MULTI-PROFIL
# ==========================================================
def analyser_profil(profil_court, donnees_globales, bases_actives):
    maintenant = datetime.datetime.now(datetime.timezone.utc)
    heure_utc = maintenant.hour
    en_killzone = (7 <= heure_utc <= 11) or (12 <= heure_utc <= 16)
    ia_data = charger_experience_ia_collective(bases_actives)
    ts_actuel = time.time()

    data_15m = donnees_globales.get("15m", {})
    data_1m = donnees_globales.get("1m", {})
    resultats = []

    for nom_court in bases_actives:
        try:
            df_15 = data_15m.get(nom_court)
            df_1 = data_1m.get(nom_court)

            if df_15 is None or df_1 is None or len(df_15) < 15 or len(df_1) < 15:
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

            high_s_1m = float(df_1["High"].iloc[-9:-1].max())
            low_s_1m = float(df_1["Low"].iloc[-9:-1].min())

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

            vol_fort = df_1["Volume"].iloc[-1] > (
                1.35 * df_1["Volume"].rolling(15).mean().iloc[-1]
            )
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
                    signal, motif = "🔴 SHORT", "MSS 15m + Sweep Majeur"
                    opt_p = prix
                    dist = max(
                        high_s_1m - opt_p + (0.15 * atr_1m),
                        0.70 * atr_1m,
                        prix * 0.008,
                    )
                    sl = opt_p + dist
                    tp1 = opt_p - (1.8 * dist)
                    tp2 = opt_p - (3.5 * dist)
                elif (
                    prix > ema_50_15
                    and sweep_15_l
                    and mss_haussier
                    and gros_corps
                ):
                    signal, motif = "🟢 LONG", "MSS 15m + Sweep Majeur"
                    opt_p = prix
                    dist = max(
                        opt_p - low_s_1m + (0.15 * atr_1m),
                        0.70 * atr_1m,
                        prix * 0.008,
                    )
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
                        opt_p = prix
                        dist = max(
                            high_s_1m - opt_p + (0.12 * atr_1m),
                            0.60 * atr_1m,
                            prix * 0.0065,
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
                        opt_p = prix
                        dist = max(
                            opt_p - low_s_1m + (0.12 * atr_1m),
                            0.60 * atr_1m,
                            prix * 0.0065,
                        )
                        sl = opt_p - dist
                        tp1 = opt_p + (1.8 * dist)
                        tp2 = opt_p + (3.2 * dist)

            elif profil_court == "Scalping 1m":
                motif_famille = "Momentum"
                if vol_fort:
                    if (
                        (prix < ema_50_15)
                        and mss_baissier
                        and (fvg_bear_1m or gros_corps)
                    ):
                        signal, motif = "🔴 SHORT", "MSS 1m + Momentum"
                        opt_p = prix
                        dist = max(
                            high_s_1m - opt_p + (0.10 * atr_1m),
                            0.55 * atr_1m,
                            prix * 0.0055,
                        )
                        sl = opt_p + dist
                        tp1 = opt_p - (1.8 * dist)
                        tp2 = opt_p - (3.5 * dist)
                    elif (
                        (prix > ema_50_15)
                        and mss_haussier
                        and (fvg_bull_1m or gros_corps)
                    ):
                        signal, motif = "🟢 LONG", "MSS 1m + Momentum"
                        opt_p = prix
                        dist = max(
                            opt_p - low_s_1m + (0.10 * atr_1m),
                            0.55 * atr_1m,
                            prix * 0.0055,
                        )
                        sl = opt_p - dist
                        tp1 = opt_p + (1.8 * dist)
                        tp2 = opt_p + (3.5 * dist)

            else:
                motif_famille = "SMC"
                if (
                    (sweep_15_h or prix < ema_50_15)
                    and mss_baissier
                    and fvg_bear_1m
                ):
                    signal, motif = "🔴 SHORT", "Ancrage 15m ➔ FVG 1m"
                    opt_p = prix
                    dist = max(
                        high_s_1m - opt_p + (0.10 * atr_1m),
                        0.50 * atr_1m,
                        prix * 0.0050,
                    )
                    sl = opt_p + dist
                    tp1 = opt_p - (1.8 * dist)
                    tp2 = opt_p - (3.8 * dist)
                elif (
                    (sweep_15_l or prix > ema_50_15)
                    and mss_haussier
                    and fvg_bull_1m
                ):
                    signal, motif = "🟢 LONG", "Ancrage 15m ➔ FVG 1m"
                    opt_p = prix
                    dist = max(
                        opt_p - low_s_1m + (0.10 * atr_1m),
                        0.50 * atr_1m,
                        prix * 0.0050,
                    )
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
                    "Nom_Court": nom_court,
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
                    "RSI": f"{rsi_val:.1f}",
                    "Intervalle": "1m",
                }
            )
        except Exception:
            continue
    return resultats


# ==========================================================
# 👤 GESTION DU PROFIL UTILISATEUR & LANGUE
# ==========================================================
comptes_actuels = charger_tous_les_comptes()
liste_noms = list(comptes_actuels.keys())
paires_actives = charger_paires_radar()

if "langue" not in st.session_state:
    st.session_state.langue = "FR"

st.sidebar.markdown("### 🌐 Langue / Language")
choix_langue = st.sidebar.selectbox(
    "Language",
    ["🇫🇷 Français", "🇬🇧 English"],
    index=0 if st.session_state.langue == "FR" else 1,
    label_visibility="collapsed",
)
st.session_state.langue = "FR" if "Français" in choix_langue else "EN"
LANG = st.session_state.langue


def t(key, **kwargs):
    text = I18N[LANG].get(key, I18N["FR"].get(key, key))
    return text.format(**kwargs) if kwargs else text


if "trader_session" not in st.session_state:
    st.session_state.trader_session = (
        "Thomas" if "Thomas" in liste_noms else liste_noms[0]
    )

st.sidebar.markdown(f"### 👤 {t('user_space')}")
idx_nom = (
    liste_noms.index(st.session_state.trader_session)
    if st.session_state.trader_session in liste_noms
    else 0
)
choix_trader = st.sidebar.selectbox(
    t("connected_as"), liste_noms, index=idx_nom, key="select_trader_box"
)
st.session_state.trader_session = choix_trader
trader_courant = st.session_state.trader_session

with st.sidebar.expander(f"➕ {t('create_profile')}"):
    nouveau_nom = st.text_input(t("input_name")).strip()
    if st.button(t("validate")):
        if nouveau_nom:
            comptes_frais = charger_tous_les_comptes()
            if nouveau_nom not in comptes_frais:
                comptes_frais[nouveau_nom] = {
                    "solde": 1000.0,
                    "capital_initial": 1000.0,
                    "auto_actif": False,
                    "master_auto": False,
                    "positions": {},
                    "historique": [],
                }
                sauvegarder_tous_les_comptes(comptes_frais)
            st.session_state.trader_session = nouveau_nom
            st.rerun()

# VOYANT STATUS CLOUD
up_url, _ = get_upstash_credentials()
if up_url:
    st.sidebar.markdown(
        "<span style='color:#14F195; font-size:12px; font-weight:bold;'>☁️"
        " Mémoire Cloud Active (Upstash)</span>",
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        "<span style='color:#FFB300; font-size:11px;'>⚠️ Stockage Local"
        " (Configure les Secrets Upstash)</span>",
        unsafe_allow_html=True,
    )

# GESTIONNAIRE DYNAMIQUE DE PAIRES
with st.sidebar.expander(f"🪙 {t('manage_pairs')}", expanded=False):
    st.caption(t("manage_pairs_sub"))
    nouvelle_paire_in = (
        st.text_input(t("add_crypto_ph"), key="input_new_crypto")
        .strip()
        .upper()
    )
    if st.button(t("add_crypto_btn"), key="btn_add_crypto"):
        if nouvelle_paire_in:
            nom_nettoye = (
                nouvelle_paire_in.replace("/USDT", "")
                .replace("-USD", "")
                .replace("USDT", "")
                .strip()
                .upper()
            )
            p_actuelles = charger_paires_radar()
            if nom_nettoye not in p_actuelles:
                p_actuelles.append(nom_nettoye)
                sauvegarder_paires_radar(p_actuelles)
                st.success(f"✅ {nom_nettoye}/USDT added !")
                st.rerun()

    st.markdown("---")
    st.markdown(f"<b>{t('monitored_pairs')}</b>", unsafe_allow_html=True)
    p_actuelles = charger_paires_radar()
    for p_sym in p_actuelles:
        c_p1, c_p2 = st.columns([3, 1])
        c_p1.markdown(f"• **{p_sym}/USDT**")
        if c_p2.button("❌", key=f"btn_del_pair_{p_sym}"):
            p_actuelles.remove(p_sym)
            sauvegarder_paires_radar(p_actuelles)
            st.rerun()

compte_actif = comptes_actuels.get(
    trader_courant,
    {
        "solde": 1000.0,
        "capital_initial": 1000.0,
        "auto_actif": False,
        "master_auto": False,
        "positions": {},
        "historique": [],
    },
)

# ==========================================================
# 🎛️ EN-TÊTE DU COCKPIT
# ==========================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(
        f"### ⚡ {t('cockpit_title')} <span class='user-badge'>👤 {trader_courant}</span>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.caption(f"🕒 {t('paris_time')} **{obtenir_date_heure_paris()}**")

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
    t("active_profile"),
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

if "memoire_par_profil" not in st.session_state:
    st.session_state.memoire_par_profil = {p: {} for p in LISTE_PROFILS}


# ==========================================================
# 🌟 FRAGMENT AUTO-ACTUALISÉ CORRIGÉ
# ==========================================================
@st.fragment(run_every="8s")
def bloc_live_auto_actualise():
    maintenant_ts = time.time()
    bases_actives = charger_paires_radar()
    prix_mexc_direct = obtenir_prix_live_multi_sources(bases_actives)
    donnees_globales = charger_donnees_marche_globales(bases_actives)

    if "selected_master_crypto" not in st.session_state:
        st.session_state.selected_master_crypto = "SOL"

    crypto_master = st.session_state.selected_master_crypto
    master_data = analyser_crypto_master_live(crypto_master)

    # 1. Setup A+ Royal du jour
    setup_a_plus = detecter_setup_a_plus_du_jour(
        donnees_globales, bases_actives
    )
    if setup_a_plus:
        url_mexc_a = get_mexc_futures_url(setup_a_plus["paire"])
        st.markdown(
            f"""
        <div class="gold-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="gold-title">👑 {t('setup_a_title')} : {setup_a_plus['paire']} ({setup_a_plus['sens']})</span>
                <span style="color:#00E676; font-weight:bold; font-size:15px;">{t('target_gain')} +{setup_a_plus['gain_vise']} USDT (1:4.2)</span>
            </div>
            <hr style="border-color:#FFD700; margin:6px 0;">
            🎯 <b>{t('optimal_entry')}</b> <span class="opt-price">{formater_prix(setup_a_plus['entree'])} USDT</span> | 🛑 <b>{t('stop_loss')}</b> {formater_prix(setup_a_plus['sl'])} USDT<br>
            🚀 <b>{t('take_profit_royal')}</b> <span style="color:#00E676; font-weight:bold;">{formater_prix(setup_a_plus['tp'])} USDT</span><br>
            💼 <b>{t('suggested_margin')}</b> {setup_a_plus['marge_suggeree']} USDT (x{setup_a_plus['levier']}) | 🛑 {t('risk')} -{setup_a_plus['perte_max']} USDT<br>
            <div style="margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
                <small style="color:#AAA;">💡 <i>{setup_a_plus['motif']}</i></small>
                <a href="{url_mexc_a}" target="_blank" class="mexc-btn">{t('open_mexc', pair=setup_a_plus['paire'])}</a>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""<div class="gold-card-empty">{t('setup_a_waiting')}</div>""",
            unsafe_allow_html=True,
        )

    # 2. Synchronisation des profils radar
    donnees_tous_profils = {}
    for p_nom in LISTE_PROFILS:
        if p_nom not in st.session_state.memoire_par_profil:
            st.session_state.memoire_par_profil[p_nom] = {}

        donnees_p = analyser_profil(p_nom, donnees_globales, bases_actives)
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
            p
            for p, info in mem_p.items()
            if maintenant_ts - info["timestamp"] > exp
        ]
        for p in a_suppr:
            del mem_p[p]

    # 3. Vue Panoramique
    col_c, col_i, col_s, col_u = st.columns(4)
    with col_c:
        st.markdown(
            f"""<div class="mini-card-conservateur"><b>🛡️ Conservateur (15m x20)</b><br>""",
            unsafe_allow_html=True,
        )
        sigs_c = st.session_state.memoire_par_profil.get("Conservateur", {})
        if sigs_c:
            for p, info in sigs_c.items():
                st.markdown(
                    f"**{info['signal']}** `{p}` 🎯"
                    f" {formater_prix(info['prix_entree'])}",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<span style='color:#6E7681;'>{t('veille')}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_i:
        st.markdown(
            f"""<div class="mini-card-intraday"><b>⚖️ Intraday (5m x50)</b><br>""",
            unsafe_allow_html=True,
        )
        sigs_i = st.session_state.memoire_par_profil.get("Intraday", {})
        if sigs_i:
            for p, info in sigs_i.items():
                st.markdown(
                    f"**{info['signal']}** `{p}` 🎯"
                    f" {formater_prix(info['prix_entree'])}",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<span style='color:#6E7681;'>{t('veille')}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_s:
        st.markdown(
            f"""<div class="mini-card-scalping"><b>⚡ Scalp (1m x100)</b><br>""",
            unsafe_allow_html=True,
        )
        sigs_s = st.session_state.memoire_par_profil.get("Scalping 1m", {})
        if sigs_s:
            for p, info in sigs_s.items():
                st.markdown(
                    f"**{info['signal']}** `{p}` 🎯"
                    f" {formater_prix(info['prix_entree'])}",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<span style='color:#6E7681;'>{t('veille')}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with col_u:
        st.markdown(
            f"""<div class="mini-card-ultrascalp"><b>🔥 Ultra (1m x150)</b><br>""",
            unsafe_allow_html=True,
        )
        sigs_u = st.session_state.memoire_par_profil.get("Ultra-Scalp", {})
        if sigs_u:
            for p, info in sigs_u.items():
                st.markdown(
                    f"**{info['signal']}** `{p}` 🎯"
                    f" {formater_prix(info['prix_entree'])}",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<span style='color:#6E7681;'>{t('veille')}</span>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # 4. MOTEUR AUTO-TRADER (BUG DOUBLE SAUVEGARDE SUPPRIMÉ)
    compte_actuel = charger_tous_les_comptes().get(trader_courant, compte_actif)

    def executer_moteur_complet(compte):
        heure_fr_trade = obtenir_date_heure_paris("%H:%M:%S")
        ts_maintenant = time.time()

        # A. Positions Master
        for pos_k in list(compte.get("positions", {}).keys()):
            if "Master_" in pos_k:
                pos_m = compte["positions"][pos_k]
                paire_m = pos_m.get("paire", "SOL/USDT")
                p_direct = prix_mexc_direct.get(paire_m, pos_m.get("entree", 0))

                sens_m = pos_m.get("sens", "LONG")
                entree_m = float(pos_m.get("entree", p_direct))
                sl_m = float(pos_m.get("sl", 0))
                tp1_m = float(pos_m.get("tp1", 0))
                tp2_m = float(pos_m.get("tp2", 0))
                marge_m = float(pos_m.get("marge", 100.0))
                levier_m = float(pos_m.get("levier", 25))
                notionnel_m = marge_m * levier_m
                tp1_hit_m = pos_m.get("tp1_hit", False)

                ts_open_m = pos_m.get("open_timestamp", ts_maintenant)
                duree_m = ts_maintenant - ts_open_m

                is_long_m = "LONG" in sens_m
                pnl_flottant_m = (
                    ((p_direct - entree_m) / entree_m) * notionnel_m
                    if is_long_m
                    else ((entree_m - p_direct) / entree_m) * notionnel_m
                )
                roe_m = (pnl_flottant_m / marge_m) * 100

                if roe_m >= 25.0 and not tp1_hit_m:
                    pos_m["sl"] = (
                        entree_m + (0.001 * entree_m)
                        if is_long_m
                        else entree_m - (0.001 * entree_m)
                    )
                if roe_m >= 50.0 and not tp1_hit_m:
                    pos_m["sl"] = (
                        entree_m + (0.003 * entree_m)
                        if is_long_m
                        else entree_m - (0.003 * entree_m)
                    )

                if duree_m > 5400 and abs(roe_m) < 15.0:
                    compte["solde"] += pnl_flottant_m
                    mettre_a_jour_ia_collective(
                        trader_courant,
                        paire_m,
                        "Squeeze Master",
                        pnl_flottant_m >= 0,
                        pnl_flottant_m,
                    )
                    compte["historique"].insert(
                        0,
                        {
                            "strat": "Crypto Master",
                            "paire": paire_m,
                            "sens": sens_m,
                            "pnl": round(pnl_flottant_m, 2),
                            "win": pnl_flottant_m >= 0,
                            "date": f"{heure_fr_trade} (Time-Stop)",
                        },
                    )
                    del compte["positions"][pos_k]
                    continue

                if is_long_m:
                    if not tp1_hit_m and p_direct >= tp1_m:
                        pos_m["tp1_hit"] = True
                        pnl_60 = ((tp1_m - entree_m) / entree_m) * (
                            notionnel_m * 0.60
                        )
                        compte["solde"] += pnl_60
                        pos_m["sl"] = entree_m + (pos_m.get("dist", 1.0) * 0.35)
                    elif tp1_hit_m and p_direct >= tp2_m:
                        pnl_40 = ((tp2_m - entree_m) / entree_m) * (
                            notionnel_m * 0.40
                        )
                        pnl_tot = (
                            ((tp1_m - entree_m) / entree_m) * (notionnel_m * 0.60)
                            + pnl_40
                        )
                        compte["solde"] += pnl_40
                        mettre_a_jour_ia_collective(
                            trader_courant,
                            paire_m,
                            "Squeeze Breakout",
                            True,
                            pnl_tot,
                        )
                        compte["historique"].insert(
                            0,
                            {
                                "strategie": "👑 Crypto Master 1M XP",
                                "paire": paire_m,
                                "sens": sens_m,
                                "pnl": round(pnl_tot, 2),
                                "win": True,
                                "date": heure_fr_trade,
                            },
                        )
                        del compte["positions"][pos_k]
                    elif p_direct <= sl_m:
                        pnl_tot = (
                            ((tp1_m - entree_m) / entree_m) * (notionnel_m * 0.60)
                            if tp1_hit_m
                            else ((sl_m - entree_m) / entree_m) * notionnel_m
                        )
                        compte["solde"] += (
                            ((sl_m - entree_m) / entree_m) * (notionnel_m * 0.40)
                            if tp1_hit_m
                            else pnl_tot
                        )
                        mettre_a_jour_ia_collective(
                            trader_courant,
                            paire_m,
                            "Squeeze Breakout",
                            tp1_hit_m,
                            pnl_tot,
                        )
                        compte["historique"].insert(
                            0,
                            {
                                "strategie": "👑 Crypto Master 1M XP",
                                "paire": paire_m,
                                "sens": sens_m,
                                "pnl": round(pnl_tot, 2),
                                "win": tp1_hit_m,
                                "date": heure_fr_trade,
                            },
                        )
                        del compte["positions"][pos_k]
                else:
                    if not tp1_hit_m and p_direct <= tp1_m:
                        pos_m["tp1_hit"] = True
                        pnl_60 = ((entree_m - tp1_m) / entree_m) * (
                            notionnel_m * 0.60
                        )
                        compte["solde"] += pnl_60
                        pos_m["sl"] = entree_m - (pos_m.get("dist", 1.0) * 0.35)
                    elif tp1_hit_m and p_direct <= tp2_m:
                        pnl_40 = ((entree_m - tp2_m) / entree_m) * (
                            notionnel_m * 0.40
                        )
                        pnl_tot = (
                            ((entree_m - tp1_m) / entree_m) * (notionnel_m * 0.60)
                            + pnl_40
                        )
                        compte["solde"] += pnl_40
                        mettre_a_jour_ia_collective(
                            trader_courant,
                            paire_m,
                            "Squeeze Breakout",
                            True,
                            pnl_tot,
                        )
                        compte["historique"].insert(
                            0,
                            {
                                "strategie": "👑 Crypto Master 1M XP",
                                "paire": paire_m,
                                "sens": sens_m,
                                "pnl": round(pnl_tot, 2),
                                "win": True,
                                "date": heure_fr_trade,
                            },
                        )
                        del compte["positions"][pos_k]
                    elif p_direct >= sl_m:
                        pnl_tot = (
                            ((entree_m - tp1_m) / entree_m) * (notionnel_m * 0.60)
                            if tp1_hit_m
                            else ((entree_m - sl_m) / entree_m) * notionnel_m
                        )
                        compte["solde"] += (
                            ((entree_m - sl_m) / entree_m) * (notionnel_m * 0.40)
                            if tp1_hit_m
                            else pnl_tot
                        )
                        mettre_a_jour_ia_collective(
                            trader_courant,
                            paire_m,
                            "Squeeze Breakout",
                            tp1_hit_m,
                            pnl_tot,
                        )
                        compte["historique"].insert(
                            0,
                            {
                                "strategie": "👑 Crypto Master 1M XP",
                                "paire": paire_m,
                                "sens": sens_m,
                                "pnl": round(pnl_tot, 2),
                                "win": tp1_hit_m,
                                "date": heure_fr_trade,
                            },
                        )
                        del compte["positions"][pos_k]

        # B. Prise auto Master
        if compte.get("master_auto", False) and master_data:
            bo = master_data.get("breakout_signal")
            paire_m_cle = f"Master_{master_data['sym']}/USDT"
            if bo and paire_m_cle not in compte.get("positions", {}):
                compte["positions"][paire_m_cle] = {
                    "strategie": f"👑 {master_data['sym']} Master 1M XP",
                    "paire": f"{master_data['sym']}/USDT",
                    "sens": bo["sens"],
                    "motif": "Squeeze Breakout 15m (100$)",
                    "entree": bo["entree"],
                    "sl": bo["sl"],
                    "tp1": bo["tp1"],
                    "tp2": bo["tp2"],
                    "marge": 100.0,
                    "levier": bo["levier"],
                    "tp1_hit": False,
                    "date_open": heure_fr_trade,
                    "open_timestamp": ts_maintenant,
                    "dist": bo.get("dist", 1.0),
                }

        # C. Exécution classique du radar multi-profils
        if compte.get("auto_actif", False):
            for p_nom in LISTE_PROFILS:
                param_strat = PARAMETRES_STRATS.get(
                    p_nom, {"levier": 50, "marge": 35.0, "max_duree_sec": 1080}
                )
                levier_strat = param_strat["levier"]
                marge_strat = param_strat["marge"]
                max_duree = param_strat["max_duree_sec"]

                for d in donnees_tous_profils.get(p_nom, []):
                    paire_reelle = d.get("Paire", "")
                    cle_pos = f"{p_nom}_{paire_reelle}"
                    p_live = prix_mexc_direct.get(
                        paire_reelle, d.get("Prix", 0)
                    )
                    motif_fam = d.get("Motif_Famille", "SMC")

                    if cle_pos in compte.get("positions", {}):
                        pos = compte["positions"][cle_pos]
                        sens = pos.get("sens", "LONG")
                        p_entree = float(pos.get("entree", p_live))
                        sl = float(pos.get("sl", 0))
                        tp1 = float(pos.get("tp1", 0))
                        tp2 = float(pos.get("tp2", 0))
                        marge_p = float(pos.get("marge", marge_strat))
                        levier_p = float(pos.get("levier", levier_strat))
                        notionnel = marge_p * levier_p
                        tp1_hit = pos.get("tp1_hit", False)

                        ts_open = pos.get("open_timestamp", ts_maintenant)
                        duree_trade = ts_maintenant - ts_open
                        is_long = "LONG" in sens
                        pnl_flottant = (
                            ((p_live - p_entree) / p_entree) * notionnel
                            if is_long
                            else ((p_entree - p_live) / p_entree) * notionnel
                        )
                        roe_trade = (pnl_flottant / marge_p) * 100

                        if roe_trade >= 25.0 and not tp1_hit:
                            pos["sl"] = (
                                p_entree + (0.001 * p_entree)
                                if is_long
                                else p_entree - (0.001 * p_entree)
                            )
                        if roe_trade >= 50.0 and not tp1_hit:
                            pos["sl"] = (
                                p_entree + (0.003 * p_entree)
                                if is_long
                                else p_entree - (0.003 * p_entree)
                            )

                        if duree_trade > max_duree:
                            compte["solde"] += pnl_flottant
                            mettre_a_jour_ia_collective(
                                trader_courant,
                                paire_reelle,
                                motif_fam,
                                pnl_flottant >= 0,
                                pnl_flottant,
                            )
                            compte["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire_reelle,
                                    "sens": sens,
                                    "pnl": round(pnl_flottant, 2),
                                    "win": pnl_flottant >= 0,
                                    "date": f"{heure_fr_trade} (Time-Stop)",
                                },
                            )
                            del compte["positions"][cle_pos]
                            continue

                        if not is_long:
                            if not tp1_hit and p_live <= tp1:
                                pos["tp1_hit"] = True
                                pnl_50 = (
                                    (p_entree - tp1) / p_entree
                                ) * (notionnel * 0.5)
                                compte["solde"] += pnl_50
                                pos["sl"] = p_entree
                            elif tp1_hit and p_live <= tp2:
                                pnl_runner = (
                                    (p_entree - tp2) / p_entree
                                ) * (notionnel * 0.5)
                                pnl_tot = (
                                    (p_entree - tp1) / p_entree
                                ) * (notionnel * 0.5) + pnl_runner
                                compte["solde"] += pnl_runner
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire_reelle,
                                    motif_fam,
                                    True,
                                    pnl_tot,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire_reelle,
                                        "sens": sens,
                                        "pnl": round(pnl_tot, 2),
                                        "win": True,
                                        "date": heure_fr_trade,
                                    },
                                )
                                del compte["positions"][cle_pos]
                            elif p_live >= sl:
                                pnl = (
                                    (p_entree - sl) / p_entree
                                ) * notionnel if not tp1_hit else ((p_entree - tp1) / p_entree) * (notionnel * 0.5)
                                if not tp1_hit:
                                    compte["solde"] += pnl
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire_reelle,
                                    motif_fam,
                                    tp1_hit,
                                    pnl,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire_reelle,
                                        "sens": sens,
                                        "pnl": round(pnl, 2),
                                        "win": tp1_hit,
                                        "date": heure_fr_trade,
                                    },
                                )
                                del compte["positions"][cle_pos]
                        else:
                            if not tp1_hit and p_live >= tp1:
                                pos["tp1_hit"] = True
                                pnl_50 = (
                                    (tp1 - p_entree) / p_entree
                                ) * (notionnel * 0.5)
                                compte["solde"] += pnl_50
                                pos["sl"] = p_entree
                            elif tp1_hit and p_live >= tp2:
                                pnl_runner = (
                                    (tp2 - p_entree) / p_entree
                                ) * (notionnel * 0.5)
                                pnl_tot = (
                                    (tp1 - p_entree) / p_entree
                                ) * (notionnel * 0.5) + pnl_runner
                                compte["solde"] += pnl_runner
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire_reelle,
                                    motif_fam,
                                    True,
                                    pnl_tot,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire_reelle,
                                        "sens": sens,
                                        "pnl": round(pnl_tot, 2),
                                        "win": True,
                                        "date": heure_fr_trade,
                                    },
                                )
                                del compte["positions"][cle_pos]
                            elif p_live <= sl:
                                pnl = (
                                    (sl - p_entree) / p_entree
                                ) * notionnel if not tp1_hit else ((tp1 - p_entree) / p_entree) * (notionnel * 0.5)
                                if not tp1_hit:
                                    compte["solde"] += pnl
                                mettre_a_jour_ia_collective(
                                    trader_courant,
                                    paire_reelle,
                                    motif_fam,
                                    tp1_hit,
                                    pnl,
                                )
                                compte["historique"].insert(
                                    0,
                                    {
                                        "strategie": p_nom,
                                        "paire": paire_reelle,
                                        "sens": sens,
                                        "pnl": round(pnl, 2),
                                        "win": tp1_hit,
                                        "date": heure_fr_trade,
                                    },
                                )
                                del compte["positions"][cle_pos]

                    elif len(compte["positions"]) < 4 and d.get(
                        "Signal_Detecte"
                    ):
                        compte["positions"][cle_pos] = {
                            "strategie": p_nom,
                            "paire": paire_reelle,
                            "sens": d["Signal_Detecte"],
                            "motif": d["Motif"],
                            "entree": d["Opt_Price"],
                            "sl": d["SL"],
                            "tp1": d["TP1"],
                            "tp2": d["TP2"],
                            "marge": marge_strat,
                            "levier": levier_strat,
                            "tp1_hit": False,
                            "date_open": heure_fr_trade,
                            "open_timestamp": ts_maintenant,
                        }

    mettre_a_jour_un_compte(trader_courant, executer_moteur_complet)

    # 5. ONGLETS DU COCKPIT BILINGUE
    tab_auto, tab_radar, tab_master, tab_ia, tab_classement, tab_calc = st.tabs(
        [
            t("tab_auto", user=trader_courant),
            t("tab_radar", profile=profil_cle),
            t("tab_master"),
            t("tab_ia"),
            t("tab_rank"),
            t("tab_calc"),
        ]
    )

    # ======================================================
    # 👑 ONGLET CRYPTO MASTER MULTI-PAIRES (MODÈLE 100$)
    # ======================================================
    with tab_master:
        c_fresh = charger_tous_les_comptes().get(trader_courant, compte_actif)
        col_sm1, col_sm2 = st.columns([3, 2])
        with col_sm1:
            st.markdown(
                f"#### {t('master_header')} <span class='user-badge'>👤"
                f" {trader_courant}</span>",
                unsafe_allow_html=True,
            )
        with col_sm2:
            mode_auto_master = st.toggle(
                t("toggle_master_auto"),
                value=c_fresh.get("master_auto", False),
                key="toggle_master_auto_switch_v23",
            )
            if mode_auto_master != c_fresh.get("master_auto", False):

                def set_auto_master(c):
                    c["master_auto"] = mode_auto_master

                mettre_a_jour_un_compte(trader_courant, set_auto_master)
                st.rerun()

        sel_c1, sel_c2 = st.columns([2, 2])
        with sel_c1:
            choix_crypto_master = st.selectbox(
                "Sélectionner la crypto Master :",
                bases_actives,
                index=(
                    bases_actives.index(st.session_state.selected_master_crypto)
                    if st.session_state.selected_master_crypto in bases_actives
                    else 0
                ),
            )
            st.session_state.selected_master_crypto = choix_crypto_master

        master_data_live = analyser_crypto_master_live(choix_crypto_master)
        url_master_mexc = get_mexc_futures_url(f"{choix_crypto_master}/USDT")

        if mode_auto_master:
            st.markdown(
                f"""<div style="background-color:rgba(20,241,149,0.12); padding:8px; border-radius:6px; border:1px solid #14F195; font-size:13px; color:#14F195; font-weight:bold; margin-bottom:8px;">
                {t('master_auto_on')} (Marge : 100 USDT | Levier x25)
            </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""<div style="background-color:#0D1117; padding:8px; border-radius:6px; border:1px dashed #30363D; font-size:13px; color:#8B949E; margin-bottom:8px;">
                {t('master_auto_off')}
            </div>""",
                unsafe_allow_html=True,
            )

        if master_data_live:
            p_live_m = master_data_live["prix"]
            sq_on = master_data_live["squeeze_on"]
            mom = master_data_live["momentum"]
            atr = master_data_live["atr"]
            bo = master_data_live["breakout_signal"]

            regime_titre = (
                t("regime_comp") if sq_on else t("regime_exp")
            )
            regime_color = "#14F195" if sq_on else "#00E5FF"

            st.markdown(
                f"""
            <div class="sol-master-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#14F195; font-size:17px; font-weight:bold;">{choix_crypto_master} / USDT (MEXC FUTURES)</span>
                    <span style="color:#FFF; font-weight:bold; font-size:16px;">{formater_prix(p_live_m)} $</span>
                </div>
                <hr style="border-color:#14F195; margin:6px 0;">
                <b>{t('regime_detected')}</b> <span style="color:{regime_color}; font-weight:bold;">{regime_titre}</span><br>
                📊 <b>Momentum :</b> <span style="color:{'#00E676' if mom >= 0 else '#FF1744'}; font-weight:bold;">{mom:+.3f}</span> | ⚡ <b>ATR 15m :</b> {atr:.4f} $ | 📉 <b>EMA 50 :</b> {master_data_live['ema50']:.4f} $<br>
                <div style="margin-top:6px;">
                    <a href="{url_master_mexc}" target="_blank" class="mexc-btn">{t('manage_on_mexc', pair=f'{choix_crypto_master}/USDT')}</a>
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            if sq_on:
                st.markdown(f"#### {t('grid_title')}")
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    st.markdown(
                        f"<b>{t('orders_buy')}</b>", unsafe_allow_html=True
                    )
                    for lvl in master_data_live["grid_levels"]:
                        st.markdown(
                            f"<span class='grid-badge-buy'>Achat L{lvl['lvl']}"
                            f" : {lvl['buy']} $</span>"
                            f" (-{lvl['lvl']*0.35:.2f}%)",
                            unsafe_allow_html=True,
                        )
                with col_g2:
                    st.markdown(
                        f"<b>{t('orders_sell')}</b>", unsafe_allow_html=True
                    )
                    for lvl in master_data_live["grid_levels"]:
                        st.markdown(
                            f"<span class='grid-badge-sell'>Vente L{lvl['lvl']}"
                            f" : {lvl['sell']} $</span>"
                            f" (+{lvl['lvl']*0.35:.2f}%)",
                            unsafe_allow_html=True,
                        )

            if bo:
                st.markdown(
                    f"""
                <div class="{'alert-card-long' if 'LONG' in bo['sens'] else 'alert-card-short'}">
                    <b>{t('signal_breakout', pair=choix_crypto_master, sens=bo['sens'], lev=bo['levier'])}</b><br>
                    🎯 <b>{t('optimal_entry')}</b> <span class="opt-price">{formater_prix(bo['entree'])} USDT</span> | 🛑 <b>{t('stop_loss')}</b> {formater_prix(bo['sl'])} USDT<br>
                    💰 <b>TP1 (2.2R - 60%) :</b> {formater_prix(bo['tp1'])} USDT | 👑 <b>TP2 (4.5R - 40%) :</b> <span style="color:#00E676; font-weight:bold;">{formater_prix(bo['tp2'])} USDT</span><br>
                    💼 <b>Marge :</b> 100 USDT | 🔒 <b>Profit-Locking :</b> Breakeven dès +25% ROE | ⏱️ <b>Time-Stop :</b> 90m
                </div>
                """,
                    unsafe_allow_html=True,
                )

                if not mode_auto_master:
                    if st.button(
                        t("take_breakout_btn", user=trader_courant),
                        key=f"btn_manual_take_master_{choix_crypto_master}_v23",
                    ):

                        def ajouter_pos_manuel(c):
                            cle_pos_m = f"Master_{choix_crypto_master}/USDT"
                            c["positions"][cle_pos_m] = {
                                "strategie": (
                                    f"👑 {choix_crypto_master} Master 1M XP"
                                ),
                                "paire": f"{choix_crypto_master}/USDT",
                                "sens": bo["sens"],
                                "motif": "Squeeze Breakout (Manuel 100$)",
                                "entree": bo["entree"],
                                "sl": bo["sl"],
                                "tp1": bo["tp1"],
                                "tp2": bo["tp2"],
                                "marge": 100.0,
                                "levier": bo["levier"],
                                "tp1_hit": False,
                                "date_open": obtenir_date_heure_paris(
                                    "%H:%M:%S"
                                ),
                                "open_timestamp": time.time(),
                                "dist": bo.get("dist", 1.0),
                            }

                        mettre_a_jour_un_compte(
                            trader_courant, ajouter_pos_manuel
                        )
                        st.success(
                            f"✅ Position {choix_crypto_master} Master"
                            f" ({trader_courant}) OK !"
                        )
                        st.rerun()
            elif not sq_on and not bo:
                st.info(t("regime_trans"))
        else:
            st.warning(f"⏳ Live MEXC {choix_crypto_master} Feed...")

    # ======================================================
    # 🤖 ONGLET AUTO : POSITIONS OUVERTES & LIENS DIRECTS
    # ======================================================
    with tab_auto:
        c_fresh = charger_tous_les_comptes().get(trader_courant, compte_actif)
        col_t1, col_t2 = st.columns([2, 1])
        pnl_auto = c_fresh["solde"] - c_fresh["capital_initial"]

        with col_t1:
            st.markdown(
                f"💰 <b>{t('balance_realized')}</b> `{c_fresh['solde']:.2f}"
                " USDT` | **PnL :** <span"
                f" style='color:{'#00E676' if pnl_auto >= 0 else '#FF5252'};"
                f" font-weight:bold;'>{pnl_auto:+.2f} USDT</span>",
                unsafe_allow_html=True,
            )
        with col_t2:
            nouvel_etat = st.toggle(
                t("toggle_auto_radar"),
                value=c_fresh.get("auto_actif", False),
                key="toggle_auto_live_radar_v23",
            )
            if nouvel_etat != c_fresh.get("auto_actif", False):

                def toggle_etat(c):
                    c["auto_actif"] = nouvel_etat

                mettre_a_jour_un_compte(trader_courant, toggle_etat)
                st.rerun()

        if c_fresh.get("positions"):
            st.markdown(f"#### {t('open_pos_title')}")
            for cle, pos in list(c_fresh["positions"].items()):
                strat_nom = pos.get("strategie", "Auto")
                paire_nom = pos.get(
                    "paire", cle.split("_")[1] if "_" in cle else "SOL/USDT"
                )
                sens_nom = pos.get("sens", "LONG")
                levier_nom = pos.get("levier", 50)
                marge_nom = float(pos.get("marge", 35.0))
                notionnel_nom = marge_nom * levier_nom

                entree_val = float(pos.get("entree", 0))
                sl_val = float(pos.get("sl", 0))
                tp1_val = float(pos.get("tp1", 0))
                tp2_val = float(pos.get("tp2", 0))
                tp1_statut = (
                    t("breakeven") if pos.get("tp1_hit", False) else t("waiting")
                )

                p_actuel = prix_mexc_direct.get(paire_nom, entree_val)
                if entree_val > 0:
                    pnl_flottant = (
                        ((p_actuel - entree_val) / entree_val) * notionnel_nom
                        if "LONG" in sens_nom
                        else ((entree_val - p_actuel) / entree_val)
                        * notionnel_nom
                    )
                    roe_flottant = (pnl_flottant / marge_nom) * 100
                else:
                    pnl_flottant, roe_flottant = 0.0, 0.0

                pnl_color = "#00E676" if pnl_flottant >= 0 else "#FF1744"

                ts_open = pos.get("open_timestamp", maintenant_ts - 120)
                duree_sec = int(max(0, maintenant_ts - ts_open))
                hours, remainder = divmod(duree_sec, 3600)
                mins, secs = divmod(remainder, 60)
                chrono_str = (
                    f"{hours}h {mins}m"
                    if hours > 0
                    else (f"{mins}m {secs}s" if mins > 0 else f"{secs}s")
                )

                url_mexc_pos = get_mexc_futures_url(paire_nom)

                col_p1, col_p2 = st.columns([4, 1])
                with col_p1:
                    st.markdown(
                        f"""
                    <div class="pos-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <b>[{strat_nom}] {paire_nom} ({sens_nom} x{levier_nom})</b>
                            <span style="color:{pnl_color}; font-weight:bold; font-size:14px;">
                                PnL : {pnl_flottant:+.2f} USDT ({roe_flottant:+.1f}%)
                            </span>
                        </div>
                        <hr style="border-color:#30363D; margin:6px 0;">
                        🎯 <b>{t('optimal_entry')}</b> {formater_prix(entree_val)} | 🛑 <b>{t('stop_loss')}</b> {formater_prix(sl_val)} | ⏱️ <b>{t('running_since')}</b> <span class="timer-badge">{chrono_str}</span><br>
                        💰 <b>TP1 :</b> {formater_prix(tp1_val)} [{tp1_statut}] | 🚀 <b>TP2 :</b> {formater_prix(tp2_val)}<br>
                        <a href="{url_mexc_pos}" target="_blank" class="mexc-btn">{t('manage_on_mexc', pair=paire_nom)}</a>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )
                with col_p2:
                    if st.button(
                        t("cut_btn"),
                        key=f"btn_close_pos_{cle}_v23",
                        help=f"Close {paire_nom} at market price",
                    ):

                        def couper_pos(c):
                            if cle in c.get("positions", {}):
                                c["solde"] += pnl_flottant
                                c["historique"].insert(
                                    0,
                                    {
                                        "strategie": strat_nom,
                                        "paire": paire_nom,
                                        "sens": sens_nom,
                                        "pnl": round(pnl_flottant, 2),
                                        "win": pnl_flottant >= 0,
                                        "date": obtenir_date_heure_paris(
                                            "%H:%M:%S"
                                        ),
                                    },
                                )
                                del c["positions"][cle]

                        mettre_a_jour_un_compte(trader_courant, couper_pos)
                        st.rerun()
        else:
            st.caption(t("no_open_pos"))

        if c_fresh.get("historique"):
            st.markdown(f"#### {t('recent_closed')}")
            st.dataframe(
                pd.DataFrame(c_fresh["historique"][:6]), hide_index=True
            )

        if st.button(t("reset_btn"), key="btn_reset_v23"):

            def reset_c(c):
                c["solde"] = 1000.0
                c["capital_initial"] = 1000.0
                c["auto_actif"] = False
                c["master_auto"] = False
                c["positions"] = {}
                c["historique"] = []

            mettre_a_jour_un_compte(trader_courant, reset_c)
            st.rerun()

    # ======================================================
    # ⚡ ONGLET RADAR MULTI-TIMEFRAME
    # ======================================================
    with tab_radar:
        memoire_active = st.session_state.memoire_par_profil.get(profil_cle, {})

        if memoire_active:
            for p, info in list(memoire_active.items()):
                temps_restant = int(
                    durees_profils.get(profil_cle, 120)
                    - (maintenant_ts - info["timestamp"])
                )
                if temps_restant > 0:
                    classe = (
                        "alert-card-long"
                        if "LONG" in info["signal"]
                        else "alert-card-short"
                    )
                    p_reel = prix_mexc_direct.get(p, info["prix_entree"])
                    p_entree = info["prix_entree"]
                    url_mexc_signal = get_mexc_futures_url(p)

                    is_long = "LONG" in info["signal"]
                    ecart_pct = (
                        (p_reel - p_entree) / p_entree
                        if is_long
                        else (p_entree - p_reel) / p_entree
                    )
                    est_perime = ecart_pct > 0.0025

                    badge_statut = (
                        f'<span class="status-expired">{t("status_expired")}</span>'
                        if est_perime
                        else f'<span class="status-valid">{t("status_valid")}</span>'
                    )

                    st.markdown(
                        f"""
                    <div class="{classe}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="font-size:15px; font-weight:bold;">⚡ {info['signal']} : {p} ({info['motif']})</span>
                            <span>{badge_statut} <span class="timer-badge">⏱️ {temps_restant}s</span></span>
                        </div>
                        <hr style="border-color:rgba(255,255,255,0.1); margin:6px 0;">
                        🎯 <b>{t('optimal_entry')}</b> <span class="opt-price">{formater_prix(info['prix_entree'])} USDT</span> ({t('price_col')}: {formater_prix(p_reel)})<br>
                        🛑 <b>{t('stop_loss')}</b> {formater_prix(info['sl'])} | 💰 <b>TP1 :</b> {formater_prix(info['tp1'])} | 🚀 <b>TP2 :</b> {formater_prix(info['tp2'])}<br>
                        <div style="margin-top:6px;">
                            <a href="{url_mexc_signal}" target="_blank" class="mexc-btn">{t('trader_on_mexc', pair=p)}</a>
                        </div>
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

                    if not est_perime:
                        if st.button(
                            t(
                                "take_signal_btn",
                                sens=info["signal"],
                                pair=p,
                                user=trader_courant,
                            ),
                            key=f"btn_radar_take_{p}_v23",
                        ):

                            def prendre_pos_radar(c):
                                cle = f"{profil_cle}_{p}"
                                p_strat = PARAMETRES_STRATS.get(
                                    profil_cle, {"levier": 50, "marge": 35.0}
                                )
                                c["positions"][cle] = {
                                    "strategie": profil_cle,
                                    "paire": p,
                                    "sens": (
                                        "LONG"
                                        if "LONG" in info["signal"]
                                        else "SHORT"
                                    ),
                                    "motif": info["motif"],
                                    "entree": info["prix_entree"],
                                    "sl": info["sl"],
                                    "tp1": info["tp1"],
                                    "tp2": info["tp2"],
                                    "marge": p_strat["marge"],
                                    "levier": p_strat["levier"],
                                    "tp1_hit": False,
                                    "date_open": obtenir_date_heure_paris(
                                        "%H:%M:%S"
                                    ),
                                    "open_timestamp": time.time(),
                                }

                            mettre_a_jour_un_compte(
                                trader_courant, prendre_pos_radar
                            )
                            st.success(
                                f"✅ Position {p} ({trader_courant}) OK !"
                            )
                            st.rerun()

        donnees_dict = {
            d["Paire"]: d for d in donnees_tous_profils.get(profil_cle, [])
        }
        lignes_tableau = []

        for nom_court in bases_actives:
            paire_nom = f"{nom_court}/USDT"
            d = donnees_dict.get(paire_nom, {})

            statut = (
                memoire_active[paire_nom]["signal"]
                if paire_nom in memoire_active
                else t("veille")
            )
            prix_reel_mexc = prix_mexc_direct.get(
                paire_nom, d.get("Prix", "N/A")
            )
            mtf = obtenir_stats_mtf_radar(nom_court)

            lignes_tableau.append(
                {
                    t("pair_col"): paire_nom,
                    t("price_col"): formater_prix(prix_reel_mexc),
                    t("status_col"): statut,
                    "Range 15m": mtf["range_15m"],
                    "RSI 15m": mtf["rsi_15m"],
                    "Range 30m": mtf["range_30m"],
                    "RSI 30m": mtf["rsi_30m"],
                    "Range 1h": mtf["range_1h"],
                    "RSI 1h": mtf["rsi_1h"],
                    "Range 4h": mtf["range_4h"],
                    "RSI 4h": mtf["rsi_4h"],
                    "Range 1j": mtf["range_1d"],
                    "RSI 1j": mtf["rsi_1d"],
                }
            )

        st.dataframe(
            pd.DataFrame(lignes_tableau),
            hide_index=True,
            use_container_width=True,
        )

    with tab_ia:
        ia_stats = charger_experience_ia_collective(bases_actives)
        st.markdown(
            f"""
        <div class="xp-card">
            <b>{t('ia_level')} <span style="color:#00E676;">{ia_stats['niveau']}</span></b> (⭐ {ia_stats['xp_total']} XP)<br>
            <small>{t('ia_sub')}</small>
        </div>
        """,
            unsafe_allow_html=True,
        )
        for lecon in ia_stats["lecons_apprises"][:4]:
            st.caption(f"• {lecon}")

    # ======================================================
    # 🏆 CLASSEMENT LIVE : SÉCURISÉ CONTRE LES ERREURS DE TYPE
    # ======================================================
    with tab_classement:
        liste_classement = []
        comptes_live = charger_tous_les_comptes()
        for nom, c in comptes_live.items():
            if not isinstance(c, dict):
                continue
            pnl = c.get("solde", 1000.0) - c.get("capital_initial", 1000.0)
            trades_nb = len(c.get("historique", []))
            wins = sum(1 for tr in c.get("historique", []) if tr.get("win", False))
            wr = (wins / trades_nb * 100) if trades_nb > 0 else 0.0
            liste_classement.append(
                {
                    "Trader": f"👤 {nom}",
                    "Solde / Balance": f"{c.get('solde', 1000.0):.1f} $",
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
            use_container_width=True,
        )

    with tab_calc:
        c1, c2 = st.columns(2)
        paire_sel = c1.selectbox(
            t("pair_col"), [f"{p}/USDT" for p in bases_actives]
        )
        sens_sel = c2.radio(
            "Sens / Direction", ["LONG 🟢", "SHORT 🔴"], horizontal=True
        )
        is_long = "LONG" in sens_sel

        col_e, col_sl = st.columns(2)
        p_entree = col_e.number_input(
            t("calc_entry"), value=106.20, step=0.01, format="%.5f"
        )
        p_sl = col_sl.number_input(
            t("calc_sl"), value=105.90, step=0.01, format="%.5f"
        )
        marge_fixe = st.number_input(t("calc_margin"), value=10.0, step=5.0)

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
                <b>{t('calc_margin')} :</b> {marge_fixe:.1f} USDT (x{levier_suggere}) | <b>{t('stop_loss')}</b> <span style="color:#FF5252;">-{perte_sl:.2f}$ ({pct_dist:.2%})</span><br>
                🎯 <b>TP1 :</b> {formater_prix(tp1)} | 🚀 <b>TP2 Runner :</b> {formater_prix(tp2)}<br>
                💀 <b>{t('calc_liquidation')}</b> {formater_prix(p_liq)}
            </div>
            """,
                unsafe_allow_html=True,
            )


# Lancement du fragment fluide
bloc_live_auto_actualise()
