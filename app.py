from concurrent.futures import ThreadPoolExecutor
import datetime
import json
import os
import time
import numpy as np
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# Imports officiels SDK Google Gemini
from google import genai
from google.genai import types

# Fuseau horaire Paris
try:
    import zoneinfo
    TZ_PARIS = zoneinfo.ZoneInfo("Europe/Paris")
except Exception:
    TZ_PARIS = datetime.timezone(datetime.timedelta(hours=2))


def obtenir_date_heure_paris(format_str="%d/%m %H:%M:%S"):
    return datetime.datetime.now(TZ_PARIS).strftime(format_str)


st.set_page_config(
    page_title="Cockpit Pro - ICT, Scalping & Macro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    .stApp { background-color: #000000; color: #E6EDF3; }
    .metric-card { background-color: #0D1117; border-radius: 8px; padding: 12px; border-left: 3px solid #2962FF; margin-bottom: 8px; }
    .user-badge { background-color: #061A0E; color: #00E676; padding: 4px 10px; border-radius: 5px; font-weight: bold; border: 1px solid #00E676; font-size: 13px; }
    
    .gemini-box { background: linear-gradient(135deg, #0D1117 0%, #111827 100%); border-radius: 10px; padding: 14px; border: 1px solid #30363D; margin-bottom: 12px; }
    .pos-card { background-color: #0D1117; border-radius: 8px; padding: 12px; border: 1px solid #30363D; margin-bottom: 10px; }
    .alert-card-long { background-color: #04140B; border-radius: 8px; padding: 14px; border: 1px solid #00E676; margin-bottom: 10px; }
    .alert-card-short { background-color: #170508; border-radius: 8px; padding: 14px; border: 1px solid #FF1744; margin-bottom: 10px; }
    .opt-price { color: #FFD700; font-size: 16px; font-weight: bold; }
    .timer-badge { background-color: #161B22; color: #00E676; padding: 3px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; border: 1px solid #30363D; }
    
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
        margin-top: 6px;
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
# ☁️ CONNECTEUR CLOUD UPSTASH (PERSISTANCE DES COMPTES)
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
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=["GET", key],
            timeout=2.0,
        )
        val = r.json().get("result")
        if val:
            return json.loads(val)
    except Exception:
        pass
    return None


def cloud_mget(keys):
    url, token = get_upstash_credentials()
    if not url or not token or not keys:
        return [None] * len(keys)
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=["MGET"] + list(keys),
            timeout=2.0,
        )
        results = r.json().get("result", [])
        parsed = []
        for val in results:
            if val:
                try:
                    parsed.append(json.loads(val))
                except Exception:
                    parsed.append(None)
            else:
                parsed.append(None)
        return parsed
    except Exception:
        return [None] * len(keys)


def cloud_set(key, data):
    url, token = get_upstash_credentials()
    if not url or not token:
        return False
    try:
        requests.post(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=["SET", key, json.dumps(data, ensure_ascii=False)],
            timeout=2.0,
        )
        return True
    except Exception:
        return False


# ==========================================================
# 👥 GESTION DES PROFILS TRADERS & PAIRES RADAR
# ==========================================================
FICHIER_PAIRES = "paires_radar.json"

TRADERS_INITIAUX = {
    "Thomas": {"solde": 1167.37, "capital_initial": 1000.0, "total_trades": 18, "total_wins": 11},
    "Alex": {"solde": 1000.0, "capital_initial": 1000.0, "total_trades": 0, "total_wins": 0},
    "Yeepse": {"solde": 1207.00, "capital_initial": 1000.0, "total_trades": 214, "total_wins": 79},
}


def charger_un_compte(nom_trader):
    init_vals = TRADERS_INITIAUX.get(
        nom_trader,
        {"solde": 1000.0, "capital_initial": 1000.0, "total_trades": 0, "total_wins": 0},
    )
    c_cloud = cloud_get(f"compte_trader_{nom_trader}")
    if c_cloud and isinstance(c_cloud, dict) and "solde" in c_cloud:
        if "total_trades" not in c_cloud or c_cloud["total_trades"] == 0:
            c_cloud["total_trades"] = max(c_cloud.get("total_trades", 0), init_vals["total_trades"])
            c_cloud["total_wins"] = max(c_cloud.get("total_wins", 0), init_vals["total_wins"])
        if "historique" not in c_cloud:
            c_cloud["historique"] = []
        if "positions" not in c_cloud:
            c_cloud["positions"] = {}
        return c_cloud

    f_local = f"compte_{nom_trader}.json"
    if os.path.exists(f_local):
        try:
            with open(f_local, "r", encoding="utf-8") as f:
                c = json.load(f)
                if isinstance(c, dict) and "solde" in c:
                    return c
        except Exception:
            pass

    c_new = {
        "solde": init_vals["solde"],
        "capital_initial": init_vals["capital_initial"],
        "total_trades": init_vals["total_trades"],
        "total_wins": init_vals["total_wins"],
        "auto_actif": False,
        "positions": {},
        "historique": [],
    }
    sauvegarder_un_compte(nom_trader, c_new)
    return c_new


def sauvegarder_un_compte(nom_trader, data):
    if not isinstance(data, dict) or "solde" not in data:
        return
    cloud_set(f"compte_trader_{nom_trader}", data)
    try:
        with open(f"compte_{nom_trader}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass


def charger_tous_les_comptes_rapide():
    traders_connus = list(TRADERS_INITIAUX.keys())
    custom_traders = cloud_get("liste_noms_traders") or []
    all_traders = list(dict.fromkeys(traders_connus + custom_traders))
    keys = [f"compte_trader_{t_nom}" for t_nom in all_traders]
    batch_results = cloud_mget(keys)

    comptes = {}
    for idx, t_nom in enumerate(all_traders):
        c = batch_results[idx]
        init_vals = TRADERS_INITIAUX.get(
            t_nom,
            {"solde": 1000.0, "capital_initial": 1000.0, "total_trades": 0, "total_wins": 0},
        )
        if c and isinstance(c, dict) and "solde" in c:
            if "total_trades" not in c or c["total_trades"] == 0:
                c["total_trades"] = max(c.get("total_trades", 0), init_vals["total_trades"])
                c["total_wins"] = max(c.get("total_wins", 0), init_vals["total_wins"])
            comptes[t_nom] = c
        else:
            comptes[t_nom] = charger_un_compte(t_nom)
    return comptes


def mettre_a_jour_un_compte(nom_trader, modificateur_fn):
    compte = charger_un_compte(nom_trader)
    modificateur_fn(compte)
    sauvegarder_un_compte(nom_trader, compte)


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
    paires_defaut = ["SOL", "BTC", "ETH", "XRP", "ZEC", "BNB", "SUI", "DOGE"]
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
    base = paire_str.replace("/USDT", "").replace("-USD", "").replace("USDT", "").strip().upper()
    return f"https://futures.mexc.com/exchange/{base}_USDT"


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


# ==========================================================
# ⚡ FLUX DE DONNÉES MEXC OPTIMISÉ (ZÉRO LATENCE)
# ==========================================================
@st.cache_data(ttl=5)
def obtenir_prix_live_multi_sources(bases_actives):
    prix_dict = {}
    try:
        url_mexc = "https://api.mexc.com/api/v3/ticker/price"
        res = requests.get(url_mexc, headers={"User-Agent": "Mozilla/5.0"}, timeout=1.5).json()
        bases_set = {f"{b}USDT": b for b in bases_actives}
        for it in res:
            s_name = it.get("symbol", "")
            if s_name in bases_set:
                base = bases_set[s_name]
                prix_dict[f"{base}/USDT"] = float(it.get("price", 0))
    except Exception:
        pass
    return prix_dict


def fetch_single_mexc_kline(base, interval, limit=60):
    try:
        url = f"https://api.mexc.com/api/v3/klines?symbol={base}USDT&interval={interval}&limit={limit}"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=2.0).json()
        if not res or not isinstance(res, list):
            return base, None
        df = pd.DataFrame(
            res,
            columns=["time", "Open", "High", "Low", "Close", "Volume", "c_time", "qav"],
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
    donnees = {"15m": {}, "1m": {}}
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = []
        for interval in ["15m", "1m"]:
            for base in bases_actives:
                futures.append(
                    (interval, executor.submit(fetch_single_mexc_kline, base, interval, 60))
                )
        for interval, fut in futures:
            base, df = fut.result()
            if df is not None:
                donnees[interval][base] = df
    return donnees


def calculer_rsi_series(series, period=14):
    d = series.diff()
    g = d.where(d > 0, 0).rolling(period).mean()
    l = (-d.where(d < 0, 0)).rolling(period).mean()
    rs = g / (l + 1e-9)
    return 100 - (100 / (1 + rs))


# ==========================================================
# 🤖 AGENT DE TRADING GEMINI (MACRO + TECHNIQUE)
# ==========================================================
def analyser_marche_avec_gemini(paire, prix_actuel, rsi_1m, rsi_15m, range_15m):
    api_key = st.secrets.get("GEMINI_API_KEY", "VOTRE_CLE_API_ICI")
    if api_key == "VOTRE_CLE_API_ICI":
        return {"erreur": "Clé API Gemini manquante dans les Secrets Streamlit (GEMINI_API_KEY)."}
    
    try:
        client = genai.Client(api_key=api_key)
        nom_crypto = paire.split("/")[0]
        
        prompt = f"""
        Tu es un analyste quantitatif, ICT et macro-économique senior.
        Analyse la paire {paire} en temps réel.
        
        DONNÉES TECHNIQUES ACTUELLES :
        - Prix : {prix_actuel} USDT
        - RSI 1m (Scalping) : {rsi_1m}
        - RSI 15m (Structure ICT) : {rsi_15m}
        - Range 15m récent : {range_15m}
        
        INSTRUCTIONS :
        1. Utilise Google Search pour vérifier les actualités des dernières 24h sur {nom_crypto} ainsi que le contexte macro-économique (S&P 500, Nasdaq, Pétrole, VIX, Dollar/Taux).
        2. Évalue si le flux macro est favorable (Risk-On) ou dangereux (Risk-Off) pour {nom_crypto}.
        3. Donne une instruction claire.
        
        Réponds OBLIGATOIREMENT en JSON valide avec cette structure exacte :
        {{
            "recommandation": "ACHAT" | "VENTE" | "ATTENTE",
            "confiance": entier entre 0 et 100,
            "analyse_technique": "Diagnostic technique précis (1 à 2 phrases)",
            "analyse_macro": "Contexte macro (S&P, Pétrole, VIX, news crypto) en direct (2 phrases)",
            "justification": "Plan d'action concret et niveaux à surveiller"
        }}
        """
        
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                response_mime_type="application/json",
                temperature=0.2,
                safety_settings=[
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                    types.SafetySetting(
                        category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        threshold=types.HarmBlockThreshold.BLOCK_NONE,
                    ),
                ],
            ),
        )
        
        if not response.text:
            raison = "Inconnue"
            if response.candidates and len(response.candidates) > 0:
                raison = str(response.candidates[0].finish_reason)
            return {"erreur": f"Réponse vide de l'API. Raison : {raison}"}
        
        return json.loads(response.text)
    except Exception as e:
        return {"erreur": f"Erreur lors de l'analyse IA : {str(e)}"}


# ==========================================================
# 💧 MOTEUR 1 : DÉTECTION ICT (SWEEP ➔ MSS ➔ FVG SUR 15M)
# ==========================================================
def scanner_marche_ict(donnees_globales, bases_actives):
    data_15m = donnees_globales.get("15m", {})
    signaux_ict = []
    resume_ict = []

    for nom_court in bases_actives:
        try:
            df = data_15m.get(nom_court)
            if df is None or len(df) < 20:
                continue

            prix_actuel = float(df["Close"].iloc[-1])
            rsi_15 = float(calculer_rsi_series(df["Close"], 14).iloc[-1])

            c1_high, c1_low = float(df["High"].iloc[-3]), float(df["Low"].iloc[-3])
            c2_high, c2_low = float(df["High"].iloc[-2]), float(df["Low"].iloc[-2])
            c3_high, c3_low = float(df["High"].iloc[-1]), float(df["Low"].iloc[-1])
            c3_close = float(df["Close"].iloc[-1])

            high_recent = float(df["High"].iloc[-15:-3].max())
            low_recent = float(df["Low"].iloc[-15:-3].min())

            sweep_bullish = (c1_low < low_recent) or (c2_low < low_recent)
            sweep_bearish = (c1_high > high_recent) or (c2_high > high_recent)

            mss_bullish = c3_close > float(df["High"].iloc[-6:-2].max())
            mss_bearish = c3_close < float(df["Low"].iloc[-6:-2].min())

            fvg_bullish = c3_low > c1_high
            fvg_bearish = c3_high < c1_low

            statut_etapes = []
            if sweep_bullish:
                statut_etapes.append("1️⃣ Sweep Bas ✅")
            elif sweep_bearish:
                statut_etapes.append("1️⃣ Sweep Haut ✅")

            if mss_bullish:
                statut_etapes.append("2️⃣ MSS Haussier ✅")
            elif mss_bearish:
                statut_etapes.append("2️⃣ MSS Baissier ✅")

            if fvg_bullish:
                statut_etapes.append(f"3️⃣ FVG Bull ({formater_prix(c1_high)}) ✅")
            elif fvg_bearish:
                statut_etapes.append(f"3️⃣ FVG Bear ({formater_prix(c1_low)}) ✅")

            if sweep_bullish and mss_bullish and fvg_bullish and (c3_low - c1_high) > 0:
                risque = max(abs(c1_high - c1_low), prix_actuel * 0.005)
                signaux_ict.append({
                    "strategie": "💧 ICT 15m",
                    "paire": f"{nom_court}/USDT",
                    "sens": "LONG 🟢",
                    "prix_actuel": prix_actuel,
                    "entree": c1_high,
                    "sl": c1_low,
                    "tp1": c1_high + (1.5 * risque),
                    "tp2": c1_high + (2.5 * risque),
                    "marge": 50.0,
                    "levier": 30,
                    "motif": "Séquence ICT : Sweep Bas ➔ MSS ➔ FVG",
                })

            elif sweep_bearish and mss_bearish and fvg_bearish and (c1_low - c3_high) > 0:
                risque = max(abs(c1_high - c1_low), prix_actuel * 0.005)
                signaux_ict.append({
                    "strategie": "💧 ICT 15m",
                    "paire": f"{nom_court}/USDT",
                    "sens": "SHORT 🔴",
                    "prix_actuel": prix_actuel,
                    "entree": c1_low,
                    "sl": c1_high,
                    "tp1": c1_low - (1.5 * risque),
                    "tp2": c1_low - (2.5 * risque),
                    "marge": 50.0,
                    "levier": 30,
                    "motif": "Séquence ICT : Sweep Haut ➔ MSS ➔ FVG",
                })

            resume_ict.append({
                "Paire": f"{nom_court}/USDT",
                "Prix": formater_prix(prix_actuel),
                "Liquidité Basse (15m)": formater_prix(low_recent),
                "Liquidité Haute (15m)": formater_prix(high_recent),
                "RSI 15m": f"{rsi_15:.1f}",
                "Étapes ICT détectées": " | ".join(statut_etapes) if statut_etapes else "⚪ En observation",
            })
        except Exception:
            continue

    return signaux_ict, resume_ict


# ==========================================================
# ⚡ MOTEUR 2 : SCANNER SCALPING PUR (1M)
# ==========================================================
def scanner_scalping_1m(donnees_globales, bases_actives):
    data_15m = donnees_globales.get("15m", {})
    data_1m = donnees_globales.get("1m", {})
    signaux_scalp = []
    tableau_scalp = []

    for nom_court in bases_actives:
        try:
            df_15 = data_15m.get(nom_court)
            df_1 = data_1m.get(nom_court)
            if df_15 is None or df_1 is None or len(df_15) < 15 or len(df_1) < 15:
                continue

            ema_50_15 = float(df_15["Close"].ewm(span=50, adjust=False).mean().iloc[-1])
            prix = float(df_1["Close"].iloc[-1])
            open_p = float(df_1["Open"].iloc[-1])
            high = float(df_1["High"].iloc[-1])
            low = float(df_1["Low"].iloc[-1])

            high_s_1m = float(df_1["High"].iloc[-9:-1].max())
            low_s_1m = float(df_1["Low"].iloc[-9:-1].min())

            rsi_1m = float(calculer_rsi_series(df_1["Close"], 7).iloc[-1])
            rsi_15m = float(calculer_rsi_series(df_15["Close"], 14).iloc[-1])

            hl = df_1["High"] - df_1["Low"]
            hc = (df_1["High"] - df_1["Close"].shift()).abs()
            lc = (df_1["Low"] - df_1["Close"].shift()).abs()
            atr_1m = float(pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean().iloc[-1])

            vol_ratio = float(df_1["Volume"].iloc[-1] / (df_1["Volume"].rolling(15).mean().iloc[-1] + 1e-9))
            vol_fort = vol_ratio > 1.30
            gros_corps = abs(prix - open_p) > (0.9 * atr_1m)

            fvg_bear_1m = (df_1["Low"].iloc[-3] > high) and ((df_1["Low"].iloc[-3] - high) > (atr_1m * 0.12))
            fvg_bull_1m = (low > df_1["High"].iloc[-3]) and ((low - df_1["High"].iloc[-3]) > (atr_1m * 0.12))

            mss_baissier = (prix < low_s_1m) and (prix < open_p)
            mss_haussier = (prix > high_s_1m) and (prix > open_p)

            signal, motif, sl, tp1, tp2 = None, "⚪ Calme", None, None, None

            if mss_haussier and (vol_fort or fvg_bull_1m or gros_corps):
                signal = "LONG 🟢"
                motif = "Scalp 1m : Cassure + Volume/FVG"
                dist = max(prix - low_s_1m + (0.10 * atr_1m), 0.55 * atr_1m, prix * 0.005)
                sl = prix - dist
                tp1 = prix + (1.8 * dist)
                tp2 = prix + (3.5 * dist)
            elif mss_baissier and (vol_fort or fvg_bear_1m or gros_corps):
                signal = "SHORT 🔴"
                motif = "Scalp 1m : Cassure + Volume/FVG"
                dist = max(high_s_1m - prix + (0.10 * atr_1m), 0.55 * atr_1m, prix * 0.005)
                sl = prix + dist
                tp1 = prix - (1.8 * dist)
                tp2 = prix - (3.5 * dist)

            if signal:
                signaux_scalp.append({
                    "strategie": "⚡ Scalping 1m",
                    "paire": f"{nom_court}/USDT",
                    "sens": signal,
                    "motif": motif,
                    "entree": prix,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "marge": 35.0,
                    "levier": 100,
                })

            tableau_scalp.append({
                "Paire": f"{nom_court}/USDT",
                "Prix Actuel": formater_prix(prix),
                "Signal 1m": signal if signal else "⚪ En veille",
                "Tendance 15m": "🟢 Haussière" if prix > ema_50_15 else "🔴 Baissière",
                "RSI 1m": f"{rsi_1m:.1f}",
                "RSI 15m": f"{rsi_15m:.1f}",
                "Volume Ratio": f"x{vol_ratio:.1f}",
            })
        except Exception:
            continue

    return signaux_scalp, tableau_scalp


# ==========================================================
# ⚙️ MOTEUR D'EXÉCUTION ET DE SUIVI DES TRADES PAR PROFIL
# ==========================================================
def synchroniser_trades_du_profil(nom_trader, prix_mexc_direct, signaux_ict, signaux_scalp):
    """
    Met à jour les positions ouvertes (TP1, Breakeven, TP2, SL, Time-Stop)
    et prend automatiquement les nouveaux signaux si l'Autopilote du profil est actif.
    Tous les trades sont enregistrés dans l'historique permanent du profil.
    """
    def maj_fn(compte):
        maintenant_ts = time.time()
        date_str = obtenir_date_heure_paris("%d/%m %H:%M:%S")

        # 1. Gestion des positions ouvertes
        for cle_pos, pos in list(compte.get("positions", {}).items()):
            paire_p = pos.get("paire", "SOL/USDT")
            strat_p = pos.get("strategie", "⚡ Scalping 1m")
            sens_p = pos.get("sens", "LONG 🟢")
            is_long = "LONG" in sens_p
            p_entree = float(pos.get("entree", 0))
            if p_entree <= 0:
                continue

            p_live = float(prix_mexc_direct.get(paire_p, p_entree))
            sl = float(pos.get("sl", 0))
            tp1 = float(pos.get("tp1", 0))
            tp2 = float(pos.get("tp2", 0))
            marge = float(pos.get("marge", 35.0))
            levier = float(pos.get("levier", 50))
            notionnel = marge * levier
            tp1_hit = bool(pos.get("tp1_hit", False))
            duree_sec = maintenant_ts - float(pos.get("open_timestamp", maintenant_ts))

            pnl_flottant = (
                ((p_live - p_entree) / p_entree) * notionnel
                if is_long
                else ((p_entree - p_live) / p_entree) * notionnel
            )
            roe_pct = (pnl_flottant / marge) * 100

            # Verrouillage automatique du Breakeven dès +25% ROE
            if roe_pct >= 25.0 and not tp1_hit:
                pos["sl"] = p_entree * (1.001 if is_long else 0.999)
                sl = pos["sl"]

            # Time-Stop (25 min pour Scalping 1m, 2h pour ICT 15m)
            max_duree = 7200 if "ICT" in strat_p else 1500
            if duree_sec > max_duree:
                compte["solde"] += pnl_flottant
                compte["total_trades"] = compte.get("total_trades", 0) + 1
                if pnl_flottant >= 0:
                    compte["total_wins"] = compte.get("total_wins", 0) + 1
                compte["historique"].insert(0, {
                    "date": f"{date_str} (Time-Stop)",
                    "strategie": strat_p,
                    "paire": paire_p,
                    "sens": sens_p,
                    "entree": formater_prix(p_entree),
                    "sortie": formater_prix(p_live),
                    "pnl": round(pnl_flottant, 2),
                    "win": pnl_flottant >= 0,
                })
                del compte["positions"][cle_pos]
                continue

            # Vérification TP1 / TP2 / SL
            if is_long:
                if not tp1_hit and p_live >= tp1:
                    pos["tp1_hit"] = True
                    pnl_50 = ((tp1 - p_entree) / p_entree) * (notionnel * 0.5)
                    compte["solde"] += pnl_50
                    pos["sl"] = p_entree
                elif tp1_hit and p_live >= tp2:
                    pnl_runner = ((tp2 - p_entree) / p_entree) * (notionnel * 0.5)
                    pnl_tot = ((tp1 - p_entree) / p_entree) * (notionnel * 0.5) + pnl_runner
                    compte["solde"] += pnl_runner
                    compte["total_trades"] = compte.get("total_trades", 0) + 1
                    compte["total_wins"] = compte.get("total_wins", 0) + 1
                    compte["historique"].insert(0, {
                        "date": f"{date_str} (TP2 Full)",
                        "strategie": strat_p,
                        "paire": paire_p,
                        "sens": sens_p,
                        "entree": formater_prix(p_entree),
                        "sortie": formater_prix(tp2),
                        "pnl": round(pnl_tot, 2),
                        "win": True,
                    })
                    del compte["positions"][cle_pos]
                elif p_live <= sl:
                    pnl = ((sl - p_entree) / p_entree) * notionnel if not tp1_hit else ((tp1 - p_entree) / p_entree) * (notionnel * 0.5)
                    if not tp1_hit:
                        compte["solde"] += pnl
                    compte["total_trades"] = compte.get("total_trades", 0) + 1
                    if tp1_hit:
                        compte["total_wins"] = compte.get("total_wins", 0) + 1
                    compte["historique"].insert(0, {
                        "date": f"{date_str} ({'BE après TP1' if tp1_hit else 'SL'})",
                        "strategie": strat_p,
                        "paire": paire_p,
                        "sens": sens_p,
                        "entree": formater_prix(p_entree),
                        "sortie": formater_prix(sl),
                        "pnl": round(pnl, 2),
                        "win": tp1_hit,
                    })
                    del compte["positions"][cle_pos]
            else:
                if not tp1_hit and p_live <= tp1:
                    pos["tp1_hit"] = True
                    pnl_50 = ((p_entree - tp1) / p_entree) * (notionnel * 0.5)
                    compte["solde"] += pnl_50
                    pos["sl"] = p_entree
                elif tp1_hit and p_live <= tp2:
                    pnl_runner = ((p_entree - tp2) / p_entree) * (notionnel * 0.5)
                    pnl_tot = ((p_entree - tp1) / p_entree) * (notionnel * 0.5) + pnl_runner
                    compte["solde"] += pnl_runner
                    compte["total_trades"] = compte.get("total_trades", 0) + 1
                    compte["total_wins"] = compte.get("total_wins", 0) + 1
                    compte["historique"].insert(0, {
                        "date": f"{date_str} (TP2 Full)",
                        "strategie": strat_p,
                        "paire": paire_p,
                        "sens": sens_p,
                        "entree": formater_prix(p_entree),
                        "sortie": formater_prix(tp2),
                        "pnl": round(pnl_tot, 2),
                        "win": True,
                    })
                    del compte["positions"][cle_pos]
                elif p_live >= sl:
                    pnl = ((p_entree - sl) / p_entree) * notionnel if not tp1_hit else ((p_entree - tp1) / p_entree) * (notionnel * 0.5)
                    if not tp1_hit:
                        compte["solde"] += pnl
                    compte["total_trades"] = compte.get("total_trades", 0) + 1
                    if tp1_hit:
                        compte["total_wins"] = compte.get("total_wins", 0) + 1
                    compte["historique"].insert(0, {
                        "date": f"{date_str} ({'BE après TP1' if tp1_hit else 'SL'})",
                        "strategie": strat_p,
                        "paire": paire_p,
                        "sens": sens_p,
                        "entree": formater_prix(p_entree),
                        "sortie": formater_prix(sl),
                        "pnl": round(pnl, 2),
                        "win": tp1_hit,
                    })
                    del compte["positions"][cle_pos]

        # 2. Ouverture automatique des trades générés si l'Autopilote est activé (max 5 simultanés)
        if compte.get("auto_actif", False):
            tous_signaux = signaux_ict + signaux_scalp
            for sig in tous_signaux:
                if len(compte["positions"]) >= 5:
                    break
                cle_nouvelle = f"{sig['strategie']}_{sig['paire']}"
                if cle_nouvelle not in compte["positions"]:
                    compte["positions"][cle_nouvelle] = {
                        "strategie": sig["strategie"],
                        "paire": sig["paire"],
                        "sens": sig["sens"],
                        "motif": sig["motif"],
                        "entree": sig["entree"],
                        "sl": sig["sl"],
                        "tp1": sig["tp1"],
                        "tp2": sig["tp2"],
                        "marge": sig["marge"],
                        "levier": sig["levier"],
                        "tp1_hit": False,
                        "date_open": date_str,
                        "open_timestamp": maintenant_ts,
                    }

    mettre_a_jour_un_compte(nom_trader, maj_fn)


# ==========================================================
# 👤 BARRE LATÉRALE : PROFIL UTILISATEUR & PAIRES
# ==========================================================
comptes_actuels = charger_tous_les_comptes_rapide()
liste_noms = list(comptes_actuels.keys())

if "trader_session" not in st.session_state:
    st.session_state.trader_session = "Thomas" if "Thomas" in liste_noms else liste_noms[0]

st.sidebar.markdown("### 👤 Profil Trader Actif")
idx_nom = liste_noms.index(st.session_state.trader_session) if st.session_state.trader_session in liste_noms else 0
choix_trader = st.sidebar.selectbox("Sélectionner le profil :", liste_noms, index=idx_nom)
st.session_state.trader_session = choix_trader
trader_courant = st.session_state.trader_session

with st.sidebar.expander("➕ Créer un nouveau profil"):
    nouveau_nom = st.text_input("Prénom / Pseudo :").strip()
    if st.button("Valider la création"):
        if nouveau_nom:
            charger_un_compte(nouveau_nom)
            custom_traders = cloud_get("liste_noms_traders") or []
            if nouveau_nom not in custom_traders:
                custom_traders.append(nouveau_nom)
                cloud_set("liste_noms_traders", custom_traders)
            st.session_state.trader_session = nouveau_nom
            st.rerun()

with st.sidebar.expander("🪙 Gestion des Paires Crypto", expanded=False):
    nouvelle_paire_in = st.text_input("Ajouter (ex: DOGE, SUI, NEAR) :").strip().upper()
    if st.button("➕ Ajouter au Radar"):
        if nouvelle_paire_in:
            nom_nettoye = nouvelle_paire_in.replace("/USDT", "").replace("USDT", "").strip().upper()
            p_actuelles = charger_paires_radar()
            if nom_nettoye not in p_actuelles:
                p_actuelles.append(nom_nettoye)
                sauvegarder_paires_radar(p_actuelles)
                st.rerun()

    st.markdown("---")
    p_actuelles = charger_paires_radar()
    for p_sym in p_actuelles:
        c_p1, c_p2 = st.columns([3, 1])
        c_p1.markdown(f"• **{p_sym}/USDT**")
        if c_p2.button("❌", key=f"del_{p_sym}"):
            p_actuelles.remove(p_sym)
            sauvegarder_paires_radar(p_actuelles)
            st.rerun()


# ==========================================================
# 🎛️ EN-TÊTE + BANDEAU MACRO TEMPS RÉEL (WEBSOCKET)
# ==========================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.markdown(
        f"### ⚡ Cockpit Pro <span class='user-badge'>👤 Profil : {trader_courant}</span>",
        unsafe_allow_html=True,
    )
with col_h2:
    st.caption(f"🕒 Heure de Paris : **{obtenir_date_heure_paris('%H:%M:%S')}**")

components.html(
    """
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" async>
      {
      "symbols": [
        {"proName": "FOREXCOM:SPXUSD", "title": "S&P 500"},
        {"proName": "FOREXCOM:NSXUSD", "title": "Nasdaq 100"},
        {"proName": "TVC:USOIL", "title": "US Oil (WTI)"},
        {"proName": "TVC:UKOIL", "title": "UK Oil (Brent)"},
        {"proName": "OANDA:XAUUSD", "title": "Gold (Or)"},
        {"proName": "FX:EURUSD", "title": "EUR/USD"},
        {"proName": "TVC:VIX", "title": "Indice VIX"},
        {"proName": "OANDA:FR40EUR", "title": "CAC 40"},
        {"proName": "BINANCE:BTCUSDT", "title": "Bitcoin"}
      ],
      "showSymbolLogo": true,
      "isTransparent": true,
      "displayMode": "adaptive",
      "colorTheme": "dark",
      "locale": "fr"
    }
      </script>
    </div>
    """,
    height=52,
)


# ==========================================================
# 🧠 ENCADRÉ PRIORITAIRE : AGENT GEMINI (ISOLÉ, 0 RELOAD)
# ==========================================================
@st.fragment
def section_agent_gemini_haut():
    st.markdown('<div class="gemini-box">', unsafe_allow_html=True)
    c_titre, c_select, c_btn = st.columns([2, 1.5, 1.5])
    
    bases_ia = charger_paires_radar()
    with c_titre:
        st.markdown("#### 🧠 Agent d'Analyse Gemini (Macro + Technique)")
        st.caption("Analyse à la demande : Indicateurs techniques + Contexte Macro en direct.")
    with c_select:
        crypto_cible = st.selectbox(
            "Crypto à analyser :",
            bases_ia,
            key="gemini_top_select",
            label_visibility="collapsed",
        )
        paire_cible = f"{crypto_cible}/USDT"
    with c_btn:
        lancer = st.button(f"🔍 Analyser {paire_cible} en direct", type="primary", use_container_width=True)

    if lancer:
        with st.spinner(f"Analyse de {paire_cible} en cours (Technique + Macro Web)..."):
            prix_dict = obtenir_prix_live_multi_sources([crypto_cible])
            prix_live = prix_dict.get(paire_cible, "N/A")
            _, df_15 = fetch_single_mexc_kline(crypto_cible, "15m", 30)
            _, df_1 = fetch_single_mexc_kline(crypto_cible, "1m", 30)
            
            rsi_15_str, range_15_str, rsi_1_str = "50.0", "N/A", "50.0"
            if df_15 is not None and len(df_15) >= 15:
                rsi_15_str = f"{float(calculer_rsi_series(df_15['Close'], 14).iloc[-1]):.1f}"
                range_15_str = f"[{formater_prix(df_15['Low'].min())} - {formater_prix(df_15['High'].max())}]"
            if df_1 is not None and len(df_1) >= 15:
                rsi_1_str = f"{float(calculer_rsi_series(df_1['Close'], 7).iloc[-1]):.1f}"

            st.session_state.dernier_rapport_ia = analyser_marche_avec_gemini(
                paire_cible, prix_live, rsi_1_str, rsi_15_str, range_15_str
            )
            st.session_state.derniere_paire_ia = paire_cible

    rapport = st.session_state.get("dernier_rapport_ia")
    paire_rap = st.session_state.get("derniere_paire_ia", "")
    if rapport:
        if "erreur" in rapport:
            st.error(rapport["erreur"])
        else:
            reco = rapport.get("recommandation", "ATTENTE")
            couleur_reco = "#00E676" if reco == "ACHAT" else "#FF1744" if reco == "VENTE" else "#FFB300"
            st.markdown(
                f"""
                <div style="background-color:#080B10; border-left: 4px solid {couleur_reco}; border-radius: 6px; padding: 12px; margin-top: 8px;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 6px;">
                        <span style="font-size:16px; font-weight:bold; color:{couleur_reco};">
                            🎯 [{paire_rap}] Signal IA : {reco}
                        </span>
                        <span style="background-color:#161B22; padding:3px 8px; border-radius:4px; font-size:12px;">
                            Confiance : <b>{rapport.get('confiance', 0)}%</b>
                        </span>
                    </div>
                    <div style="font-size:13px; margin-bottom:4px;"><b>📊 Technique :</b> {rapport.get('analyse_technique', '')}</div>
                    <div style="font-size:13px; margin-bottom:4px;"><b>🌍 Macro & News :</b> {rapport.get('analyse_macro', '')}</div>
                    <div style="font-size:13px; color:#FFD700;"><b>💡 Plan d'action :</b> {rapport.get('justification', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


section_agent_gemini_haut()


# ==========================================================
# 🗂️ LES 4 ONGLETS PRINCIPAUX (ÉPURÉS & STATIQUES)
# ==========================================================
tab_ict, tab_scalp, tab_macro, tab_trades = st.tabs([
    "💧 ICT (Smart Money 15m)",
    "⚡ Scanner Scalping (1m)",
    "🌍 Macro Globale (Courbes Live)",
    f"📜 Trades & Portefeuille ({trader_courant})",
])


# ==========================================================
# ONGLET 1 : 💧 ICT SMART MONEY (15M)
# ==========================================================
with tab_ict:
    col_ict_head1, col_ict_head2 = st.columns([3, 1])
    with col_ict_head1:
        st.markdown("#### 💧 Scanner ICT (15m) : 1. Sweep Liquidité ➔ 2. MSS ➔ 3. FVG")
    with col_ict_head2:
        auto_ict = st.toggle("🔄 Scan Live (15s)", value=True, key="toggle_live_ict")

    @st.fragment(run_every="15s" if auto_ict else None)
    def render_ict_scanner():
        bases = charger_paires_radar()
        donnees = charger_donnees_marche_globales(bases)
        prix_mexc = obtenir_prix_live_multi_sources(bases)
        signaux_ict, resume_ict = scanner_marche_ict(donnees, bases)
        signaux_sc, _ = scanner_scalping_1m(donnees, bases)

        # Synchronise automatiquement les trades du profil
        synchroniser_trades_du_profil(trader_courant, prix_mexc, signaux_ict, signaux_sc)

        if signaux_ict:
            for sig in signaux_ict:
                is_long = "LONG" in sig["sens"]
                couleur = "#00E676" if is_long else "#FF1744"
                classe_carte = "alert-card-long" if is_long else "alert-card-short"
                url_mexc = get_mexc_futures_url(sig["paire"])

                c_ict1, c_ict2 = st.columns([4, 1])
                with c_ict1:
                    st.markdown(
                        f"""
                        <div class="{classe_carte}">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <span style="font-size:16px; font-weight:bold; color:{couleur};">
                                    💧 {sig['paire']} — {sig['sens']} (Levier x{sig['levier']})
                                </span>
                                <span class="timer-badge">{sig['motif']}</span>
                            </div>
                            <hr style="border-color:rgba(255,255,255,0.1); margin:8px 0;">
                            🎯 <b>Entrée Limit (FVG) :</b> <span class="opt-price">{formater_prix(sig['entree'])} USDT</span> (Actuel : {formater_prix(sig['prix_actuel'])})<br>
                            🛑 <b>Stop-Loss :</b> {formater_prix(sig['sl'])} USDT | 
                            💰 <b>TP1 :</b> {formater_prix(sig['tp1'])} | 🚀 <b>TP2 :</b> <span style="color:#00E676; font-weight:bold;">{formater_prix(sig['tp2'])} USDT</span><br>
                            <a href="{url_mexc}" target="_blank" class="mexc-btn">🚀 Ouvrir sur MEXC Futures ↗️</a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_ict2:
                    if st.button(f"💧 Prendre sur {trader_courant}", key=f"take_ict_{sig['paire']}"):
                        def ouvrir_pos_ict(c):
                            c["positions"][f"ICT_{sig['paire']}"] = {
                                "strategie": "💧 ICT 15m",
                                "paire": sig["paire"],
                                "sens": sig["sens"],
                                "motif": sig["motif"],
                                "entree": sig["entree"],
                                "sl": sig["sl"],
                                "tp1": sig["tp1"],
                                "tp2": sig["tp2"],
                                "marge": sig["marge"],
                                "levier": sig["levier"],
                                "tp1_hit": False,
                                "date_open": obtenir_date_heure_paris("%d/%m %H:%M:%S"),
                                "open_timestamp": time.time(),
                            }
                        mettre_a_jour_un_compte(trader_courant, ouvrir_pos_ict)
                        st.success(f"Trade ICT {sig['paire']} enregistré sur {trader_courant} !")
        else:
            st.markdown(
                """
                <div style="background-color:#0D1117; border-radius:8px; padding:14px; text-align:center; border:1px dashed #30363D; margin-bottom:12px;">
                    <span style="color:#8B949E;">⚪ Aucun alignement complet (Sweep + MSS + FVG) sur la bougie actuelle. État des paires en direct :</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if resume_ict:
            st.dataframe(pd.DataFrame(resume_ict), hide_index=True, use_container_width=True)

    render_ict_scanner()


# ==========================================================
# ONGLET 2 : ⚡ SCANNER SCALPING (1M)
# ==========================================================
with tab_scalp:
    col_sc1, col_sc2 = st.columns([3, 1])
    with col_sc1:
        st.markdown("#### ⚡ Radar Scalping (1m) : Cassure de structure + Pic de Volume / FVG")
    with col_sc2:
        auto_scalp = st.toggle("🔄 Scan Live (12s)", value=True, key="toggle_live_scalp")

    @st.fragment(run_every="12s" if auto_scalp else None)
    def render_scalp_scanner():
        bases = charger_paires_radar()
        donnees = charger_donnees_marche_globales(bases)
        prix_mexc = obtenir_prix_live_multi_sources(bases)
        signaux_ict, _ = scanner_marche_ict(donnees, bases)
        signaux_sc, tableau_sc = scanner_scalping_1m(donnees, bases)

        synchroniser_trades_du_profil(trader_courant, prix_mexc, signaux_ict, signaux_sc)

        if signaux_sc:
            for sig in signaux_sc:
                is_long = "LONG" in sig["sens"]
                classe = "alert-card-long" if is_long else "alert-card-short"
                url_mexc = get_mexc_futures_url(sig["paire"])

                c_card, c_action = st.columns([4, 1])
                with c_card:
                    st.markdown(
                        f"""
                        <div class="{classe}">
                            <b>⚡ {sig['sens']} : {sig['paire']} ({sig['motif']}) — x{sig['levier']}</b><br>
                            🎯 <b>Entrée :</b> <span class="opt-price">{formater_prix(sig['entree'])} USDT</span> | 
                            🛑 <b>SL :</b> {formater_prix(sig['sl'])} | 
                            💰 <b>TP1 :</b> {formater_prix(sig['tp1'])} | 🚀 <b>TP2 :</b> {formater_prix(sig['tp2'])}<br>
                            <a href="{url_mexc}" target="_blank" class="mexc-btn">🚀 Ouvrir sur MEXC ↗️</a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with c_action:
                    if st.button(f"⚡ Prendre sur {trader_courant}", key=f"take_sc_{sig['paire']}"):
                        def ouvrir_pos_scalp(c):
                            c["positions"][f"Scalp_{sig['paire']}"] = {
                                "strategie": "⚡ Scalping 1m",
                                "paire": sig["paire"],
                                "sens": sig["sens"],
                                "motif": sig["motif"],
                                "entree": sig["entree"],
                                "sl": sig["sl"],
                                "tp1": sig["tp1"],
                                "tp2": sig["tp2"],
                                "marge": sig["marge"],
                                "levier": sig["levier"],
                                "tp1_hit": False,
                                "date_open": obtenir_date_heure_paris("%d/%m %H:%M:%S"),
                                "open_timestamp": time.time(),
                            }
                        mettre_a_jour_un_compte(trader_courant, ouvrir_pos_scalp)
                        st.success(f"Trade Scalp {sig['paire']} pris sur {trader_courant} !")

        if tableau_sc:
            st.dataframe(pd.DataFrame(tableau_sc), hide_index=True, use_container_width=True)

    render_scalp_scanner()


# ==========================================================
# ONGLET 3 : 🌍 MACRO GLOBALE (COURBES TRADINGVIEW EN DIRECT)
# ==========================================================
with tab_macro:
    st.markdown("#### 🌍 Courbes Macro-Économiques en Temps Réel (Flux WebSocket Direct)")
    st.caption("Visualise en un coup d'œil la tendance du Pétrole, du S&P 500, du Nasdaq, du CAC 40, de l'Or, de l'Euro et du VIX sans aucun rechargement.")

    mode_macro = st.radio(
        "Mode d'affichage :",
        ["📊 Grille Panoramique (Les 9 Courbes simultanées)", "🔍 Graphique Pro Interactif (Bougies & Indicateurs)"],
        horizontal=True,
    )

    if "Grille" in mode_macro:
        actifs_macro = [
            ("🛢️ US Oil (WTI)", "TVC:USOIL"),
            ("🛢️ UK Oil (Brent)", "TVC:UKOIL"),
            ("⚠️ Indice VIX (Volatilité)", "TVC:VIX"),
            ("🇺🇸 S&P 500", "FOREXCOM:SPXUSD"),
            ("🇺🇸 Nasdaq 100", "FOREXCOM:NSXUSD"),
            ("🇺🇸 S&P 500 Futures (US500)", "OANDA:SPX500USD"),
            ("🇫🇷 CAC 40", "OANDA:FR40EUR"),
            ("🥇 Gold (Or / USD)", "OANDA:XAUUSD"),
            ("💶 EUR / USD", "FX:EURUSD"),
        ]

        for row_idx in range(0, 9, 3):
            cols = st.columns(3)
            for col_idx in range(3):
                titre_actif, sym_tv = actifs_macro[row_idx + col_idx]
                with cols[col_idx]:
                    st.markdown(f"**{titre_actif}**")
                    components.html(
                        f"""
                        <div class="tradingview-widget-container">
                          <div class="tradingview-widget-container__widget"></div>
                          <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js" async>
                          {{
                          "symbol": "{sym_tv}",
                          "width": "100%",
                          "height": "220",
                          "locale": "fr",
                          "dateRange": "1D",
                          "colorTheme": "dark",
                          "isTransparent": false,
                          "autosize": true,
                          "largeChartUrl": ""
                        }}
                          </script>
                        </div>
                        """,
                        height=230,
                    )
    else:
        dict_actifs_pro = {
            "🛢️ US Oil (WTI)": "TVC:USOIL",
            "🛢️ UK Oil (Brent)": "TVC:UKOIL",
            "🇺🇸 S&P 500": "FOREXCOM:SPXUSD",
            "🇺🇸 Nasdaq 100": "FOREXCOM:NSXUSD",
            "🇺🇸 S&P 500 Futures": "OANDA:SPX500USD",
            "🇫🇷 CAC 40": "OANDA:FR40EUR",
            "🥇 Gold (Or)": "OANDA:XAUUSD",
            "💶 EUR / USD": "FX:EURUSD",
            "⚠️ Indice VIX": "TVC:VIX",
        }
        choix_actif_pro = st.selectbox("Choisir l'actif à inspecter :", list(dict_actifs_pro.keys()))
        sym_selectionne = dict_actifs_pro[choix_actif_pro]

        components.html(
            f"""
            <div class="tradingview-widget-container" style="height:600px;width:100%">
              <div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
              {{
              "autosize": true,
              "symbol": "{sym_selectionne}",
              "interval": "15",
              "timezone": "Europe/Paris",
              "theme": "dark",
              "style": "1",
              "locale": "fr",
              "enable_publishing": false,
              "allow_symbol_change": true,
              "support_host": "https://www.tradingview.com"
            }}
              </script>
            </div>
            """,
            height=610,
        )


# ==========================================================
# ONGLET 4 : 📜 TOUS LES TRADES & PORTEFEUILLE PAR PROFIL
# ==========================================================
with tab_trades:
    @st.fragment(run_every="12s")
    def render_portefeuille_et_journal():
        comptes_tous = charger_tous_les_comptes_rapide()
        noms_profils = list(comptes_tous.keys())

        # Sélecteur permettant d'inspecter les trades de n'importe quel profil
        col_prof, col_auto, col_reset = st.columns([2, 2, 1])
        with col_prof:
            idx_def = noms_profils.index(trader_courant) if trader_courant in noms_profils else 0
            profil_inspecte = st.selectbox(
                "👤 Voir le portefeuille et tous les trades du profil :",
                noms_profils,
                index=idx_def,
                key="select_inspect_profile",
            )

        c_prof = charger_un_compte(profil_inspecte)
        bases = charger_paires_radar()
        prix_mexc_direct = obtenir_prix_live_multi_sources(bases)

        with col_auto:
            st.write("")
            etat_auto = st.toggle(
                f"⚡ Autopilote ICT & Scalping ({profil_inspecte})",
                value=c_prof.get("auto_actif", False),
                key=f"auto_toggle_{profil_inspecte}",
            )
            if etat_auto != c_prof.get("auto_actif", False):
                def set_auto_state(c):
                    c["auto_actif"] = etat_auto
                mettre_a_jour_un_compte(profil_inspecte, set_auto_state)
                st.rerun()

        with col_reset:
            st.write("")
            if st.button("🔄 Reset 1000$", key=f"reset_{profil_inspecte}"):
                def reset_fn(c):
                    init_v = TRADERS_INITIAUX.get(
                        profil_inspecte,
                        {"solde": 1000.0, "capital_initial": 1000.0, "total_trades": 0, "total_wins": 0},
                    )
                    c["solde"] = init_v["solde"]
                    c["capital_initial"] = init_v["capital_initial"]
                    c["total_trades"] = init_v["total_trades"]
                    c["total_wins"] = init_v["total_wins"]
                    c["positions"] = {}
                    c["historique"] = []
                mettre_a_jour_un_compte(profil_inspecte, reset_fn)
                st.rerun()

        # Bandeau de statistiques du profil sélectionné
        pnl_realise = c_prof["solde"] - c_prof.get("capital_initial", 1000.0)
        nb_trades = c_prof.get("total_trades", len(c_prof.get("historique", [])))
        nb_wins = c_prof.get("total_wins", sum(1 for tr in c_prof.get("historique", []) if tr.get("win", False)))
        winrate = (nb_wins / nb_trades * 100) if nb_trades > 0 else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 Solde Réalisé", f"{c_prof['solde']:.2f} USDT")
        m2.metric("📈 PnL Net", f"{pnl_realise:+.2f} USDT")
        m3.metric("🎯 Winrate", f"{winrate:.1f}%")
        m4.metric("📊 Total Trades Exécutés", f"{nb_trades}")

        st.markdown("---")

        # 1. POSITIONS OUVERTES EN DIRECT DU PROFIL
        st.markdown(f"#### 🚀 Positions Actives en Direct ({profil_inspecte}) :")
        if c_prof.get("positions"):
            for cle, pos in list(c_prof["positions"].items()):
                strat_nom = pos.get("strategie", "⚡ Scalping 1m")
                paire_nom = pos.get("paire", "SOL/USDT")
                sens_nom = pos.get("sens", "LONG 🟢")
                levier_nom = float(pos.get("levier", 50))
                marge_nom = float(pos.get("marge", 35.0))
                notionnel = marge_nom * levier_nom
                entree_val = float(pos.get("entree", 0))
                sl_val = float(pos.get("sl", 0))
                tp1_val = float(pos.get("tp1", 0))
                tp2_val = float(pos.get("tp2", 0))
                date_ouv = pos.get("date_open", "En cours")

                p_actuel = prix_mexc_direct.get(paire_nom, entree_val)
                if entree_val > 0:
                    pnl_flottant = (
                        ((p_actuel - entree_val) / entree_val) * notionnel
                        if "LONG" in sens_nom
                        else ((entree_val - p_actuel) / entree_val) * notionnel
                    )
                    roe_flottant = (pnl_flottant / marge_nom) * 100
                else:
                    pnl_flottant, roe_flottant = 0.0, 0.0

                pnl_color = "#00E676" if pnl_flottant >= 0 else "#FF1744"
                url_mexc_pos = get_mexc_futures_url(paire_nom)

                col_p1, col_p2 = st.columns([4, 1])
                with col_p1:
                    st.markdown(
                        f"""
                        <div class="pos-card">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <b>[{strat_nom}] {paire_nom} — {sens_nom} (x{int(levier_nom)} | Marge {marge_nom:.0f}$)</b>
                                <span style="color:{pnl_color}; font-weight:bold; font-size:15px;">
                                    PnL : {pnl_flottant:+.2f} USDT ({roe_flottant:+.1f}%)
                                </span>
                            </div>
                            <hr style="border-color:#30363D; margin:6px 0;">
                            🎯 <b>Entrée :</b> {formater_prix(entree_val)} | 📍 <b>Cours Actuel :</b> {formater_prix(p_actuel)} | 
                            🛑 <b>SL :</b> {formater_prix(sl_val)} | 💰 <b>TP1 :</b> {formater_prix(tp1_val)} | 🚀 <b>TP2 :</b> {formater_prix(tp2_val)}<br>
                            <small style="color:#8B949E;">🕒 Ouvert le : {date_ouv} | Motif : {pos.get('motif', 'Signal Cockpit')}</small><br>
                            <a href="{url_mexc_pos}" target="_blank" class="mexc-btn">🚀 Gérer sur MEXC ↗️</a>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_p2:
                    if st.button("🛑 Clôturer", key=f"close_{profil_inspecte}_{cle}"):
                        def couper_pos_profil(c):
                            if cle in c.get("positions", {}):
                                c["solde"] += pnl_flottant
                                c["total_trades"] = c.get("total_trades", 0) + 1
                                if pnl_flottant >= 0:
                                    c["total_wins"] = c.get("total_wins", 0) + 1
                                c["historique"].insert(
                                    0,
                                    {
                                        "date": f"{obtenir_date_heure_paris('%d/%m %H:%M:%S')} (Manuel)",
                                        "strategie": strat_nom,
                                        "paire": paire_nom,
                                        "sens": sens_nom,
                                        "entree": formater_prix(entree_val),
                                        "sortie": formater_prix(p_actuel),
                                        "pnl": round(pnl_flottant, 2),
                                        "win": pnl_flottant >= 0,
                                    },
                                )
                                del c["positions"][cle]
                        mettre_a_jour_un_compte(profil_inspecte, couper_pos_profil)
                        st.rerun()
        else:
            st.caption(f"👀 Aucune position ouverte en ce moment pour {profil_inspecte}.")

        st.markdown("---")

        # 2. HISTORIQUE COMPLET DE TOUS LES TRADES DU PROFIL (SANS LIMITE)
        historique_complet = c_prof.get("historique", [])
        st.markdown(f"#### 📜 Historique Intégral des Trades de {profil_inspecte} ({len(historique_complet)} trades enregistrés)")

        if historique_complet:
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                filtre_strat = st.selectbox(
                    "Filtrer par Stratégie :",
                    ["Toutes les stratégies", "💧 ICT", "⚡ Scalping"],
                    key=f"filt_strat_{profil_inspecte}",
                )
            with f_col2:
                filtre_res = st.selectbox(
                    "Filtrer par Résultat :",
                    ["Tous les trades", "Gagnants uniquement ✅", "Perdants uniquement ❌"],
                    key=f"filt_res_{profil_inspecte}",
                )

            lignes_hist = []
            for tr in historique_complet:
                strat_tr = tr.get("strategie", tr.get("strat", "Auto"))
                win_tr = bool(tr.get("win", tr.get("pnl", 0) >= 0))

                if "ICT" in filtre_strat and "ICT" not in strat_tr:
                    continue
                if "Scalping" in filtre_strat and "Scalp" not in strat_tr:
                    continue
                if "Gagnants" in filtre_res and not win_tr:
                    continue
                if "Perdants" in filtre_res and win_tr:
                    continue

                lignes_hist.append({
                    "Date / Clôture": tr.get("date", "N/A"),
                    "Stratégie": strat_tr,
                    "Paire": tr.get("paire", "N/A"),
                    "Sens": tr.get("sens", "N/A"),
                    "Entrée": tr.get("entree", "-"),
                    "Sortie": tr.get("sortie", "-"),
                    "PnL (USDT)": f"{float(tr.get('pnl', 0)):+.2f} $",
                    "Statut": "✅ WIN" if win_tr else "❌ LOSS",
                })

            if lignes_hist:
                df_hist = pd.DataFrame(lignes_hist)
                st.dataframe(df_hist, hide_index=True, use_container_width=True, height=420)

                csv_bytes = df_hist.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"📥 Télécharger tous les trades de {profil_inspecte} (.CSV)",
                    data=csv_bytes,
                    file_name=f"trades_{profil_inspecte}.csv",
                    mime="text/csv",
                )
            else:
                st.info("Aucun trade ne correspond à ces filtres.")
        else:
            st.info(f"Aucun trade clôturé dans le journal de {profil_inspecte} pour le moment.")

        st.markdown("---")
        st.markdown("#### 🏆 Comparatif Multi-Profils")
        liste_classement = []
        for nom_p, cp in comptes_tous.items():
            if not isinstance(cp, dict):
                continue
            pnl_p = cp.get("solde", 1000.0) - cp.get("capital_initial", 1000.0)
            tot_t = cp.get("total_trades", len(cp.get("historique", [])))
            tot_w = cp.get("total_wins", sum(1 for tr in cp.get("historique", []) if tr.get("win", False)))
            wr_p = (tot_w / tot_t * 100) if tot_t > 0 else 0.0
            liste_classement.append({
                "Profil": f"👤 {nom_p}",
                "Positions Actives": len(cp.get("positions", {})),
                "Solde Réalisé": f"{cp.get('solde', 1000.0):.2f} $",
                "PnL Net": f"{pnl_p:+.2f} $",
                "Winrate": f"{wr_p:.0f}%",
                "Total Trades": tot_t,
            })
        st.dataframe(pd.DataFrame(liste_classement), hide_index=True, use_container_width=True)

    render_portefeuille_et_journal()
