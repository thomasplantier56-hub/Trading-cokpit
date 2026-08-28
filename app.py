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
    page_title="Cockpit Multi-Traders & IA Collective",
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
</style>
""",
    unsafe_allow_html=True,
)

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
    # Compte par défaut
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
            ia["cooldowns"][motif_famille] = (
                time.time() + 720
            )  # Cooldown collectif de 12 min
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
                }
            )
        except Exception:
            continue
    return resultats


# ==========================================================
# 👤 GESTIONNAIRE DE PROFILS TRADERS (BARRE LATÉRALE)
# ==========================================================
comptes_tous = charger_tous_les_comptes()
liste_noms = list(comptes_tous.keys()) + ["➕ Nouveau Profil Trader"]

st.sidebar.markdown("### 👤 Espace Utilisateur")
choix_utilisateur = st.sidebar.selectbox(
    "Connecté en tant que :", liste_noms, index=0
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
            st.sidebar.success(f"Compte créé pour {nouveau_pseudo} !")
            st.rerun()
    trader_courant = "Thomas"
else:
    trader_courant = choix_utilisateur

# Récupération du compte actif
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
# 🎛️ LE CURSEUR MAÎTRE DE RISQUE
# ==========================================================
col_h1, col_h2 = st.columns([3, 1])
with col_h1:
    st.title("🎛️ Cockpit Multi-Traders & IA Collective")
with col_h2:
    st.markdown(
        f'<div style="text-align:right; padding-top:15px;"><span class="user-badge">👤 {trader_courant}</span></div>',
        unsafe_allow_html=True,
    )

profil = st.select_slider(
    "👉 Réglez votre style de trading :",
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

col_ref, col_time = st.columns([1, 1])
with col_ref:
    activer_auto = st.toggle("🔄 Auto-Refresh Live", value=True)
    if activer_auto:
        sec = 5 if "1m" in unite_temps else 10
        if has_autorefresh:
            st_autorefresh(interval=sec * 1000, key="loop_collective_hive")
with col_time:
    maintenant_ts = time.time()
    st.caption(
        f"🕒 Heure : **{datetime.datetime.now().strftime('%H:%M:%S')}** | Profil : **{profil_cle} ({unite_temps} x{levier_suggere})**"
    )

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

for p_nom in LISTE_PROFILS:
    donnees_p = analyser_marche_harmonise(p_nom)
    donnees_tous_profils[p_nom] = donnees_p

    for d in donnees_p:
        paire = d["Paire"]
        if d["Signal_Detecte"] is not None:
            st.session_state.memoire_par_profil.setdefault(p_nom, {})[
                paire
            ] = {
                "signal": d["Signal_Detecte"],
                "motif": d["Motif"],
                "prix_entree": d["Opt_Price"],
                "sl": d["SL"],
                "tp1": d["TP1"],
                "tp2": d["TP2"],
                "timestamp": maintenant_ts,
            }

    exp = durees_profils.get(p_nom, 120)
    mem_p = st.session_state.memoire_par_profil.get(p_nom, {})
    a_suppr = [
        p for p, info in mem_p.items() if maintenant_ts - info["timestamp"] > exp
    ]
    for p in a_suppr:
        if p in mem_p:
            del mem_p[p]

# ==========================================================
# 🤖 AUTO-TRADING POUR LE COMPTE ACTIF
# ==========================================================
if compte_actif.get("auto_actif", False):
    for p_nom in LISTE_PROFILS:
        levier_strat = leviers_profils[p_nom]
        for d in donnees_tous_profils.get(p_nom, []):
            paire = d["Paire"]
            cle_pos = f"{p_nom}_{paire}"
            high = d["High"]
            low = d["Low"]
            motif_fam = d["Motif_Famille"]

            if cle_pos in compte_actif["positions"]:
                pos = compte_actif["positions"][cle_pos]
                sens = pos["sens"]
                p_entree = pos["entree"]
                sl = pos["sl"]
                tp1 = pos["tp1"]
                tp2 = pos["tp2"]
                notionnel = pos["marge"] * pos["levier"]

                if "SHORT" in sens:
                    if not pos["tp1_hit"] and low <= tp1:
                        pos["tp1_hit"] = True
                        pnl_50 = (
                            (p_entree - tp1) / p_entree
                        ) * (notionnel * 0.5)
                        compte_actif["solde"] += pnl_50
                        pos["sl"] = p_entree
                        sauvegarder_tous_les_comptes(comptes_tous)

                    elif pos["tp1_hit"] and low <= tp2:
                        pnl_runner = (
                            (p_entree - tp2) / p_entree
                        ) * (notionnel * 0.5)
                        pnl_tot = (
                            (p_entree - tp1) / p_entree
                        ) * (notionnel * 0.5) + pnl_runner
                        compte_actif["solde"] += pnl_runner
                        mettre_a_jour_ia_collective(
                            trader_courant, paire, motif_fam, True, pnl_tot
                        )
                        compte_actif["historique"].insert(
                            0,
                            {
                                "strategie": p_nom,
                                "paire": paire,
                                "sens": sens,
                                "pnl": round(pnl_tot, 2),
                                "win": True,
                                "date": datetime.datetime.now().strftime(
                                    "%H:%M:%S"
                                ),
                            },
                        )
                        del compte_actif["positions"][cle_pos]
                        sauvegarder_tous_les_comptes(comptes_tous)

                    elif high >= sl:
                        if pos["tp1_hit"]:
                            pnl_tot = (
                                (p_entree - tp1) / p_entree
                            ) * (notionnel * 0.5)
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, True, pnl_tot
                            )
                            compte_actif["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl_tot, 2),
                                    "win": True,
                                    "date": datetime.datetime.now().strftime(
                                        "%H:%M:%S"
                                    ),
                                },
                            )
                        else:
                            pnl = (
                                (p_entree - sl) / p_entree
                            ) * notionnel
                            compte_actif["solde"] += pnl
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, False, pnl
                            )
                            compte_actif["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl, 2),
                                    "win": False,
                                    "date": datetime.datetime.now().strftime(
                                        "%H:%M:%S"
                                    ),
                                },
                            )
                        del compte_actif["positions"][cle_pos]
                        sauvegarder_tous_les_comptes(comptes_tous)

                elif "LONG" in sens:
                    if not pos["tp1_hit"] and high >= tp1:
                        pos["tp1_hit"] = True
                        pnl_50 = (
                            (tp1 - p_entree) / p_entree
                        ) * (notionnel * 0.5)
                        compte_actif["solde"] += pnl_50
                        pos["sl"] = p_entree
                        sauvegarder_tous_les_comptes(comptes_tous)

                    elif pos["tp1_hit"] and high >= tp2:
                        pnl_runner = (
                            (tp2 - p_entree) / p_entree
                        ) * (notionnel * 0.5)
                        pnl_tot = (
                            (tp1 - p_entree) / p_entree
                        ) * (notionnel * 0.5) + pnl_runner
                        compte_actif["solde"] += pnl_runner
                        mettre_a_jour_ia_collective(
                            trader_courant, paire, motif_fam, True, pnl_tot
                        )
                        compte_actif["historique"].insert(
                            0,
                            {
                                "strategie": p_nom,
                                "paire": paire,
                                "sens": sens,
                                "pnl": round(pnl_tot, 2),
                                "win": True,
                                "date": datetime.datetime.now().strftime(
                                    "%H:%M:%S"
                                ),
                            },
                        )
                        del compte_actif["positions"][cle_pos]
                        sauvegarder_tous_les_comptes(comptes_tous)

                    elif low <= sl:
                        if pos["tp1_hit"]:
                            pnl_tot = (
                                (tp1 - p_entree) / p_entree
                            ) * (notionnel * 0.5)
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, True, pnl_tot
                            )
                            compte_actif["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl_tot, 2),
                                    "win": True,
                                    "date": datetime.datetime.now().strftime(
                                        "%H:%M:%S"
                                    ),
                                },
                            )
                        else:
                            pnl = ((sl - p_entree) / p_entree) * notionnel
                            compte_actif["solde"] += pnl
                            mettre_a_jour_ia_collective(
                                trader_courant, paire, motif_fam, False, pnl
                            )
                            compte_actif["historique"].insert(
                                0,
                                {
                                    "strategie": p_nom,
                                    "paire": paire,
                                    "sens": sens,
                                    "pnl": round(pnl, 2),
                                    "win": False,
                                    "date": datetime.datetime.now().strftime(
                                        "%H:%M:%S"
                                    ),
                                },
                            )
                        del compte_actif["positions"][cle_pos]
                        sauvegarder_tous_les_comptes(comptes_tous)

            elif len(compte_actif["positions"]) < 4 and d["Signal_Detecte"]:
                compte_actif["positions"][cle_pos] = {
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
                    "date_open": datetime.datetime.now().strftime("%H:%M:%S"),
                }
                sauvegarder_tous_les_comptes(comptes_tous)

# ==========================================================
# 👀 VUE PANORAMIQUE DES 4 STYLES
# ==========================================================
st.markdown("### 👀 Vue Panoramique (Opportunités sur les 4 Styles) :")

col_c, col_i, col_s, col_u = st.columns(4)
with col_c:
    st.markdown(
        """<div class="mini-card-conservateur"><b>🛡️ Conservateur (15m x20)</b><hr style="margin:4px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_c = st.session_state.memoire_par_profil.get("Conservateur", {})
    if sigs_c:
        for p, info in sigs_c.items():
            st.markdown(
                f"**{info['signal']}** `{p}`<br>🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_i:
    st.markdown(
        """<div class="mini-card-intraday"><b>⚖️ Intraday (5m x50)</b><hr style="margin:4px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_i = st.session_state.memoire_par_profil.get("Intraday", {})
    if sigs_i:
        for p, info in sigs_i.items():
            st.markdown(
                f"**{info['signal']}** `{p}`<br>🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_s:
    st.markdown(
        """<div class="mini-card-scalping"><b>⚡ Scalping (1m x100)</b><hr style="margin:4px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_s = st.session_state.memoire_par_profil.get("Scalping 1m", {})
    if sigs_s:
        for p, info in sigs_s.items():
            st.markdown(
                f"**{info['signal']}** `{p}`<br>🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col_u:
    st.markdown(
        """<div class="mini-card-ultrascalp"><b>🔥 Ultra-Scalp (1m x150)</b><hr style="margin:4px 0;">""",
        unsafe_allow_html=True,
    )
    sigs_u = st.session_state.memoire_par_profil.get("Ultra-Scalp", {})
    if sigs_u:
        for p, info in sigs_u.items():
            st.markdown(
                f"**{info['signal']}** `{p}`<br>🎯 {formater_prix(info['prix_entree'])}",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            "<span style='color:#757575;'>⚪ Veille</span>",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# ==========================================================
# 📱 ONGLETS PRINCIPAUX
# ==========================================================
tab_auto, tab_radar, tab_ia, tab_classement, tab_calc, tab_marche = st.tabs(
    [
        f"🤖 Mon Auto-Trader ({trader_courant})",
        f"⚡ Radar ({profil_cle})",
        "🧠 Cerveau Collectif IA",
        "🏆 Classement Amis",
        f"🧮 Calculateur (x{levier_suggere})",
        "🌍 Marché & News",
    ]
)

# 1. MON AUTO-TRADER
with tab_auto:
    col_t1, col_t2 = st.columns([2, 1])
    pnl_auto = compte_actif["solde"] - compte_actif["capital_initial"]

    with col_t1:
        st.subheader(f"💼 Portefeuille Virtuel de {trader_courant}")
        st.markdown(
            f"💰 **Solde :** `{compte_actif['solde']:.2f} USDT`  |  **PnL :** <span style='color:{'#00E676' if pnl_auto >= 0 else '#FF5252'}; font-weight:bold;'>{pnl_auto:+.2f} USDT ({pnl_auto/10:+.2f}%)</span>",
            unsafe_allow_html=True,
        )

    with col_t2:
        nouvel_etat = st.toggle(
            "⚡ ACTIVER MON AUTO-TRADING",
            value=compte_actif.get("auto_actif", False),
        )
        if nouvel_etat != compte_actif.get("auto_actif", False):
            compte_actif["auto_actif"] = nouvel_etat
            sauvegarder_tous_les_comptes(comptes_tous)
            st.rerun()

    if compte_actif.get("auto_actif", False):
        st.success(
            f"🟢 **Auto-Trader de {trader_courant} EN LIGNE** : Vos 4 stratégies tournent en continu !"
        )
    else:
        st.info("⚪ **Auto-Trader en Pause** pour ce profil.")

    st.markdown(f"#### 🚀 Positions Ouvertes pour {trader_courant} :")
    if compte_actif["positions"]:
        for cle, pos in list(compte_actif["positions"].items()):
            st.markdown(
                f"""
            <div class="pos-card">
                <b>[{pos['strategie']}] {cle.split('_')[1]} ({pos['sens']} x{pos['levier']})</b> | Ouvert à {pos.get('date_open', '')}<br>
                🎯 <b>Entrée :</b> {formater_prix(pos['entree'])} USDT | 🛑 <b>Stop :</b> {formater_prix(pos['sl'])} USDT<br>
                💰 <b>TP1 (50%) :</b> {formater_prix(pos['tp1'])} USDT [{'✅ Breakeven Actif' if pos['tp1_hit'] else '⏳ En attente'}]<br>
                🚀 <b>TP2 Runner :</b> {formater_prix(pos['tp2'])} USDT
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("👀 Aucune position ouverte.")

    st.markdown("#### 📜 Mon Historique Personnel de Trades :")
    if compte_actif["historique"]:
        df_hist = pd.DataFrame(compte_actif["historique"])
        st.dataframe(df_hist, hide_index=True)
    else:
        st.caption("Aucun trade clôturé pour le moment.")

    st.markdown("---")
    if st.button(f"🔄 Réinitialiser le compte de {trader_courant} à 1000 USDT"):
        compte_actif["solde"] = 1000.0
        compte_actif["capital_initial"] = 1000.0
        compte_actif["auto_actif"] = False
        compte_actif["positions"] = {}
        compte_actif["historique"] = []
        sauvegarder_tous_les_comptes(comptes_tous)
        st.success(f"Compte de {trader_courant} réinitialisé !")
        st.rerun()

# 2. RADAR
with tab_radar:
    memoire_active = st.session_state.memoire_par_profil.get(profil_cle, {})
    if memoire_active:
        st.subheader(f"🎯 Opportunités ({profil_cle}) :")
        for p, info in list(memoire_active.items()):
            temps_restant = int(
                durees_profils.get(profil_cle, 120)
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
                    <h3>⚡ {p} : {info['signal']} ({info['motif']})</h3>
                    <span class="timer-badge">⏱️ Valide : {minutes_rest}m {secondes_rest:02d}s</span>
                </div>
                🎯 <span class="opt-price">ENTRÉE OPTIMALE : {formater_prix(info['prix_entree'])} USDT</span><br>
                🛑 <b>Stop-Loss :</b> {formater_prix(info['sl'])} USDT<br>
                💰 <b>TP1 (50% + Breakeven) :</b> {formater_prix(info['tp1'])} USDT<br>
                🚀 <span class="tp-runner">TP2 RUNNER : {formater_prix(info['tp2'])} USDT</span>
            </div>
            """,
                unsafe_allow_html=True,
            )
        st.markdown("---")

    donnees_affichees = donnees_tous_profils.get(profil_cle, [])
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

# 3. CERVEAU COLLECTIF IA
with tab_ia:
    st.subheader("🧠 Cerveau Collectif Unique (Alimenté par tous les traders)")
    ia_stats = charger_experience_ia_collective()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            f"""
        <div class="xp-card">
            <h4>🏆 Niveau Collectif : <span style="color:#00E676;">{ia_stats['niveau']}</span></h4>
            <h2>⭐ {ia_stats['xp_total']} XP Partagés</h2>
            <small>Chaque trade gagné par n'importe quel ami fait progresser cette IA !</small>
        </div>
        """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("#### 📊 Confiance Collective par Paire :")
        df_confiance = pd.DataFrame(
            [
                {
                    "Paire": k,
                    "Score Confiance": f"{v:.2f}x",
                    "Statut": (
                        "🟢 Boosté"
                        if v > 1.05
                        else ("🔴 Attention" if v < 0.80 else "⚪ Neutre")
                    ),
                }
                for k, v in ia_stats["scores_paires"].items()
            ]
        )
        st.dataframe(df_confiance, hide_index=True)

    st.markdown("#### 📝 Dernières Leçons Apprises par la Ruche IA :")
    for lecon in ia_stats["lecons_apprises"]:
        st.markdown(f"• {lecon}")

# 4. CLASSEMENT DES AMIS
with tab_classement:
    st.subheader("🏆 Classement en Direct des Traders")
    liste_classement = []
    for nom, c in comptes_tous.items():
        pnl = c["solde"] - c["capital_initial"]
        trades_nb = len(c["historique"])
        wins = sum(1 for t in c["historique"] if t.get("win", False))
        wr = (wins / trades_nb * 100) if trades_nb > 0 else 0.0
        liste_classement.append(
            {
                "Trader": f"👤 {nom}",
                "Solde (USDT)": f"{c['solde']:.2f} $",
                "PnL Net": f"{pnl:+.2f} $",
                "Performance": f"{pnl/10:+.2f} %",
                "Winrate": f"{wr:.1f} %",
                "Trades": trades_nb,
            }
        )

    df_rank = pd.DataFrame(liste_classement).sort_values(
        by="PnL Net", ascending=False
    )
    st.dataframe(df_rank, hide_index=True)

# 5. CALCULATEUR
with tab_calc:
    st.subheader(f"🧮 Calculateur de Risque ({profil})")
    col_p, col_s = st.columns(2)
    liste_options = [f"{p.split('-')[0]}/USDT" for p in PAIRES_RADAR]
    paire_sel = col_p.selectbox("Contrat Futures", liste_options)
    sens_sel = col_s.radio("Sens", ["LONG 🟢", "SHORT 🔴"], horizontal=True)
    is_long = "LONG" in sens_sel

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
            <h3>📋 Ordre Recommandé (x{levier_choisi}) :</h3>
            <b>💵 Marge Engagée :</b> <b>{marge_fixe:.2f} USDT</b> (Notionnel : {notionnel:,.2f} USDT)<br>
            <b>🛑 Perte au Stop-Loss :</b> <span style="color:#FF5252;"><b>-{perte_sl:.2f} USDT</b> ({pct_dist:.2%})</span><br>
            <b>🎯 Gain TP1 (50%) :</b> <span style="color:#00E676;"><b>+{gain_tp1:.2f} USDT</b></span> ({formater_prix(tp1)} USDT)<br>
            <b>🚀 Gain TP2 RUNNER :</b> <span style="font-size:20px; color:#00E676;"><b>+{gain_tp2:.2f} USDT</b></span> ({formater_prix(tp2)} USDT)<br>
            <b>💀 PRIX DE LIQUIDATION :</b> <b>{formater_prix(p_liq)} USDT</b> (Distance : {formater_prix(distance_liq_dollars)} USDT)
        </div>
        """,
            unsafe_allow_html=True,
        )

# 6. MARCHÉ
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