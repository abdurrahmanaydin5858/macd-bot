# -*- coding: utf-8 -*-
"""
MACD AL/SAT Telegram Botu — Gün İçi Versiyon
GitHub Actions: her 15 dakikada bir çalışır (10:00–18:00 BIST)

- Açık pozisyonlar → ANLIK fiyatla her 15 dk kontrol edilir
- AL sinyalleri    → sadece 17:45 sonrası (günlük mum kapanınca) aranır
"""

import os, time, warnings
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from datetime import date, datetime
import pytz

warnings.filterwarnings('ignore')

# ── AYARLAR ─────────────────────────────────────────────────
TOKEN   = os.environ['TELEGRAM_TOKEN']
CHAT_ID = os.environ['TELEGRAM_CHAT_ID']

KAR_PCT   = 3.2
STOP_PCT  = 0.9
MAX_GUN   = 5
EMA_AKTIF = True

POZISYON_DOSYA = 'pozisyonlar.csv'
TZ = pytz.timezone('Europe/Istanbul')

HISSELER = [
    'ASELS', 'TUPRS', 'BIMAS', 'KTLEV', 'EREGL', 'ISDMR', 'GUBRF', 'SELEC',
    'OZATD', 'ENJSA', 'MAGEN', 'EKGYO', 'MPARK', 'GUNDG', 'RALYH', 'RGYAS',
    'BSOKE', 'PASEU', 'CVKMD', 'GLRMK', 'EUPWR', 'KRDMD', 'TKFEN', 'PETKM',
    'CIMSA', 'CWENE', 'GENIL', 'ALKLC', 'YEOTK', 'GESAN', 'EFOR', 'CEMZY',
    'GRSEL', 'MAVI',  'GRTHO', 'DOFRB', 'KCAER', 'SARKY', 'AKFYE', 'DAPGM',
    'NETCD', 'ALBRK', 'MEGMT', 'BINBN', 'ARDYZ', 'ALFAS', 'FZLGY', 'ALTNY',
    'OBAMS', 'KBORU', 'SDTTR', 'POLHO', 'SNGYO', 'GEREL', 'LMKDC', 'BINHO',
    'CANTE', 'LOGO',  'SUNTK', 'HRKET', 'IZFAS', 'SURGY', 'MEYSU', 'KARSN',
    'BMSTL', 'JANTS', 'TARKM', 'BERA',  'QUAGR', 'EGGUB', 'TUKAS', 'KZBGY',
    'SRVGY', 'MOPAS', 'ORGE',  'BIENY', 'KOPOL', 'GOKNR', 'TEZOL', 'TUREX',
    'NTGAZ', 'YIGIT', 'ZERGY', 'KATMR', 'ATATP', 'DCTTR', 'CEMTS', 'FONET',
    'MERCN', 'GENTS', 'SAFKR', 'ALVES', 'TKNSA', 'SAYAS', 'USAK',  'IHLAS',
    'BEGYO', 'IMASM', 'FORMT', 'IHLGM'
]

# ── TELEGRAM ─────────────────────────────────────────────────
def telegram_gonder(mesaj):
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            json={'chat_id': CHAT_ID, 'text': mesaj, 'parse_mode': 'HTML'},
            timeout=10
        )
        return r.ok
    except Exception as e:
        print(f'⚠️ Telegram hatası: {e}')
        return False

# ── ANLİK FİYAT (gün içi kontrol için) ──────────────────────
def anlik_fiyat_al(ticker):
    """5 dakikalık mum → en son kapanış = anlık fiyat"""
    try:
        raw = yf.download(
            ticker + '.IS',
            period='1d',
            interval='5m',
            auto_adjust=True,
            progress=False
        )
        if raw is None or raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0].lower() for c in raw.columns]
        else:
            raw.columns = [c.lower() for c in raw.columns]
        return float(raw['close'].iloc[-1])
    except:
        return None

# ── GÜNLÜK VERİ & MACD (AL sinyali için) ────────────────────
def gunluk_veri_indir(ticker):
    try:
        raw = yf.download(ticker + '.IS', period='4mo', interval='1d',
                          auto_adjust=True, progress=False)
        if raw is None or raw.empty or len(raw) < 60:
            return None
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        return df.dropna(subset=['close'])
    except:
        return None

def macd_hesapla(df):
    c      = df['close']
    ema12  = c.ewm(span=12, adjust=False).mean()
    ema26  = c.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    sinyal = macd.ewm(span=9, adjust=False).mean()
    hist   = macd - sinyal
    ema50  = c.ewm(span=50, adjust=False).mean()
    df = df.copy()
    df['hist']  = hist
    df['ema50'] = ema50
    return df

def al_sinyali_var(df):
    if len(df) < 30: return False
    h_son  = df['hist'].iloc[-1]
    h_once = df['hist'].iloc[-2]
    if any(pd.isna(x) for x in [h_son, h_once]): return False
    if not (h_once < 0 and h_son > 0): return False
    if EMA_AKTIF:
        e50 = df['ema50'].iloc[-1]
        if pd.isna(e50) or df['close'].iloc[-1] < e50: return False
    return True

# ── POZİSYON YÖNETİMİ ────────────────────────────────────────
def pozisyon_yukle():
    if not os.path.exists(POZISYON_DOSYA):
        return pd.DataFrame(columns=['ticker','giris_tarihi','alis_fiyat','gun_sayisi'])
    try:
        df = pd.read_csv(POZISYON_DOSYA)
        df['giris_tarihi'] = pd.to_datetime(df['giris_tarihi'])
        return df
    except:
        return pd.DataFrame(columns=['ticker','giris_tarihi','alis_fiyat','gun_sayisi'])

def pozisyon_kaydet(df):
    df.to_csv(POZISYON_DOSYA, index=False)

def pozisyon_ekle(ticker, fiyat):
    poz = pozisyon_yukle()
    if ticker in poz['ticker'].values:
        return
    yeni = pd.DataFrame([{
        'ticker'      : ticker,
        'giris_tarihi': date.today().isoformat(),
        'alis_fiyat'  : round(fiyat, 4),
        'gun_sayisi'  : 0
    }])
    poz = pd.concat([poz, yeni], ignore_index=True)
    pozisyon_kaydet(poz)

def pozisyon_sil(ticker):
    poz = pozisyon_yukle()
    poz = poz[poz['ticker'] != ticker]
    pozisyon_kaydet(poz)

def gun_sayisi_artir(ticker):
    poz = pozisyon_yukle()
    if ticker in poz['ticker'].values:
        poz.loc[poz['ticker'] == ticker, 'gun_sayisi'] += 1
        pozisyon_kaydet(poz)

# ── ANA FONKSİYON ────────────────────────────────────────────
def main():
    simdi     = datetime.now(TZ)
    saat      = simdi.hour + simdi.minute / 60
    saat_str  = simdi.strftime('%H:%M')
    tarih_str = simdi.strftime('%d.%m.%Y %H:%M')

    # Kapanış zamanında gün sayısını artır (18:00–18:30 arası)
    kapanista = 18.0 <= saat <= 18.5

    print(f'⏱️  {tarih_str} | Piyasa saati: {saat_str}')
    print(f'   Kapanış kontrolü: {"EVET" if kapanista else "hayır"}')

    sat_sinyaller = []
    al_sinyaller  = []

    poz = pozisyon_yukle()
    print(f'   Açık pozisyon: {len(poz)}')

    # ── 1) AÇIK POZİSYONLARI ANLİK FİYATLA KONTROL ET ──────
    for _, row in poz.iterrows():
        ticker     = row['ticker']
        alis_fiyat = float(row['alis_fiyat'])
        gun_sayisi = int(row['gun_sayisi'])

        fiyat = anlik_fiyat_al(ticker)
        if fiyat is None:
            print(f'   ⚠️ {ticker} fiyat alınamadı, atlandı')
            continue

        degisim = (fiyat - alis_fiyat) / alis_fiyat * 100

        neden = None
        if degisim >= KAR_PCT:
            neden = f'✅ KAR HEDEFİ +{degisim:.2f}%'
        elif degisim <= -STOP_PCT:
            neden = f'🛑 STOP-LOSS {degisim:.2f}%'
        elif gun_sayisi >= MAX_GUN and kapanista:
            neden = f'⏱️ {MAX_GUN} GÜN DOLDU ({degisim:+.2f}%)'

        if neden:
            sat_sinyaller.append((ticker, alis_fiyat, fiyat, degisim, neden))
            pozisyon_sil(ticker)
            poz = pozisyon_yukle()
        elif kapanista:
            gun_sayisi_artir(ticker)
            print(f'   📅 {ticker} gün sayısı → {gun_sayisi + 1}')

        time.sleep(0.3)

    # ── 2) AL SİNYALİ → SADECE KAPANIŞTA (17:45+) ──────────
    if saat >= 17.75:  # 17:45 ve sonrası
        print(f'   🔍 AL sinyali taraması başlıyor...')
        poz = pozisyon_yukle()  # SAT'lardan sonra yenile
        for ticker in HISSELER:
            if ticker in poz['ticker'].values:
                continue  # Zaten pozisyon var
            df = gunluk_veri_indir(ticker)
            if df is None:
                continue
            df = macd_hesapla(df)
            if al_sinyali_var(df):
                fiyat = float(df['close'].iloc[-1])
                al_sinyaller.append((ticker, fiyat, float(df['hist'].iloc[-1])))
                pozisyon_ekle(ticker, fiyat)
            time.sleep(0.15)

    # ── TELEGRAM MESAJLARI ──────────────────────────────────

    # SAT mesajları (önce)
    for ticker, alis, simdiki, degisim, neden in sat_sinyaller:
        kl = '🟢' if degisim >= 0 else '🔴'
        mesaj = (
            f'🔴 <b>SAT — {ticker}</b>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'Neden   : {neden}\n'
            f'Alış    : ₺{alis:.3f}\n'
            f'Şimdiki : ₺{simdiki:.3f}\n'
            f'{kl} Değişim : %{degisim:+.2f}\n'
            f'━━━━━━━━━━━━━━━\n'
            f'🕐 {tarih_str}'
        )
        ok = telegram_gonder(mesaj)
        print(f'  🔴 SAT: {ticker} — {neden} → {"✅" if ok else "❌"}')

    # AL mesajları
    if al_sinyaller:
        liste = ''
        for ticker, fiyat, hist in al_sinyaller:
            liste += f'  • <b>{ticker}</b>  ₺{fiyat:.3f}\n'
        mesaj = (
            f'🟢 <b>AL SİNYALLERİ</b>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'{liste}'
            f'━━━━━━━━━━━━━━━\n'
            f'Hedef: +{KAR_PCT}% | Stop: -{STOP_PCT}% | Max: {MAX_GUN}g\n'
            f'⚡ YARIN SABAH AÇILIŞTA GİR\n'
            f'🕐 {tarih_str}'
        )
        ok = telegram_gonder(mesaj)
        print(f'  🟢 AL: {len(al_sinyaller)} sinyal → {"✅" if ok else "❌"}')

    poz_son = pozisyon_yukle()
    print(f'\n✅ Bitti | Açık: {len(poz_son)} | SAT: {len(sat_sinyaller)} | AL: {len(al_sinyaller)}')

if __name__ == '__main__':
    main()
