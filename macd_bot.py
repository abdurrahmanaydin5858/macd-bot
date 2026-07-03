# -*- coding: utf-8 -*-
"""
MACD AL/SAT Telegram Botu — Döngülü Versiyon
GitHub Actions: sabah 10:00'da başlar, 18:15'e kadar 15 dk'da bir çalışır.
Hiçbir şeye gerek yok — bir kez başlar, gün boyunca kendi kendine döner.
"""

import os, time, warnings
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from datetime import date, datetime
import pytz

warnings.filterwarnings('ignore')

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
        print(f'⚠️ Telegram: {e}')
        return False

# ── VERİ ─────────────────────────────────────────────────────
def anlik_fiyat_al(ticker):
    try:
        raw = yf.download(ticker + '.IS', period='1d', interval='5m',
                          auto_adjust=True, progress=False)
        if raw is None or raw.empty: return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [c[0].lower() for c in raw.columns]
        else:
            raw.columns = [c.lower() for c in raw.columns]
        return float(raw['close'].iloc[-1])
    except:
        return None

def gunluk_veri_indir(ticker):
    try:
        raw = yf.download(ticker + '.IS', period='4mo', interval='1d',
                          auto_adjust=True, progress=False)
        if raw is None or raw.empty or len(raw) < 60: return None
        df = raw.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0].lower() for c in df.columns]
        else:
            df.columns = [c.lower() for c in df.columns]
        return df.dropna(subset=['close'])
    except:
        return None

def macd_hesapla(df):
    c = df['close']
    macd   = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    sinyal = macd.ewm(span=9, adjust=False).mean()
    df = df.copy()
    df['hist'] = macd - sinyal
    df['ema50'] = c.ewm(span=50, adjust=False).mean()
    return df

def al_sinyali_var(df):
    if len(df) < 30: return False
    h1, h0 = df['hist'].iloc[-2], df['hist'].iloc[-1]
    if any(pd.isna(x) for x in [h1, h0]): return False
    if not (h1 < 0 and h0 > 0): return False
    if EMA_AKTIF:
        e50 = df['ema50'].iloc[-1]
        if pd.isna(e50) or df['close'].iloc[-1] < e50: return False
    return True

# ── POZİSYON ─────────────────────────────────────────────────
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
    if ticker in poz['ticker'].values: return
    yeni = pd.DataFrame([{'ticker': ticker, 'giris_tarihi': date.today().isoformat(),
                           'alis_fiyat': round(fiyat, 4), 'gun_sayisi': 0}])
    pozisyon_kaydet(pd.concat([poz, yeni], ignore_index=True))

def pozisyon_sil(ticker):
    poz = pozisyon_yukle()
    pozisyon_kaydet(poz[poz['ticker'] != ticker])

# ── TEK TUR TARAMA ───────────────────────────────────────────
def bir_tur_tara(kapanista=False):
    simdi    = datetime.now(TZ)
    tarih_str = simdi.strftime('%d.%m.%Y %H:%M')

    sat_sinyaller = []
    al_sinyaller  = []
    poz = pozisyon_yukle()

    print(f'  🔄 {tarih_str} | açık: {len(poz)} | kapanış: {kapanista}')

    # SAT — anlık fiyatla kontrol
    for _, row in poz.iterrows():
        ticker     = row['ticker']
        alis_fiyat = float(row['alis_fiyat'])
        gun_sayisi = int(row['gun_sayisi'])

        fiyat = anlik_fiyat_al(ticker)
        if fiyat is None: continue

        degisim = (fiyat - alis_fiyat) / alis_fiyat * 100
        neden   = None

        if degisim >= KAR_PCT:
            neden = f'✅ KAR +{degisim:.2f}%'
        elif degisim <= -STOP_PCT:
            neden = f'🛑 STOP {degisim:.2f}%'
        elif gun_sayisi >= MAX_GUN and kapanista:
            neden = f'⏱️ {MAX_GUN} GÜN ({degisim:+.2f}%)'

        if neden:
            sat_sinyaller.append((ticker, alis_fiyat, fiyat, degisim, neden))
            pozisyon_sil(ticker)
            poz = pozisyon_yukle()
        elif kapanista:
            poz.loc[poz['ticker'] == ticker, 'gun_sayisi'] += 1
            pozisyon_kaydet(poz)
            poz = pozisyon_yukle()

        time.sleep(0.3)

    # AL — sadece kapanışta
    if kapanista:
        poz = pozisyon_yukle()
        for ticker in HISSELER:
            if ticker in poz['ticker'].values: continue
            df = gunluk_veri_indir(ticker)
            if df is None: continue
            df = macd_hesapla(df)
            if al_sinyali_var(df):
                fiyat = float(df['close'].iloc[-1])
                al_sinyaller.append((ticker, fiyat, float(df['hist'].iloc[-1])))
                pozisyon_ekle(ticker, fiyat)
            time.sleep(0.15)

    # Telegram — SAT
    for ticker, alis, simdiki, degisim, neden in sat_sinyaller:
        kl = '🟢' if degisim >= 0 else '🔴'
        telegram_gonder(
            f'🔴 <b>SAT — {ticker}</b>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'Neden   : {neden}\n'
            f'Alış    : ₺{alis:.3f}\n'
            f'Şimdiki : ₺{simdiki:.3f}\n'
            f'{kl} Değişim : %{degisim:+.2f}\n'
            f'━━━━━━━━━━━━━━━\n'
            f'🕐 {tarih_str}'
        )
        print(f'    🔴 SAT gönderildi: {ticker} — {neden}')

    # Telegram — AL
    if al_sinyaller:
        liste = ''.join(f'  • <b>{t}</b>  ₺{f:.3f}\n' for t, f, _ in al_sinyaller)
        telegram_gonder(
            f'🟢 <b>AL SİNYALLERİ</b>\n'
            f'━━━━━━━━━━━━━━━\n'
            f'{liste}'
            f'━━━━━━━━━━━━━━━\n'
            f'Hedef: +{KAR_PCT}% | Stop: -{STOP_PCT}% | Max: {MAX_GUN}g\n'
            f'⚡ YARIN SABAH AÇILIŞTA GİR\n'
            f'🕐 {tarih_str}'
        )
        print(f'    🟢 AL gönderildi: {len(al_sinyaller)} hisse')

# ── ANA DÖNGÜ ────────────────────────────────────────────────
def main():
    simdi = datetime.now(TZ)
    print(f'🚀 Bot başladı: {simdi.strftime("%d.%m.%Y %H:%M")}')
    telegram_gonder(f'🤖 MACD Botu başladı — {simdi.strftime("%d.%m.%Y %H:%M")}\n'
                    f'Piyasa kapanışına (18:15) kadar 15 dk\'da bir tarayacak.')

    gun_sayisi_arttirildi = False   # gün içinde bir kez artır

    while True:
        simdi = datetime.now(TZ)
        saat  = simdi.hour + simdi.minute / 60

        # Piyasa bitti mi? (18:15 sonrası)
        if saat > 18.25:
            print(f'🏁 Piyasa kapandı ({simdi.strftime("%H:%M")}). Bot duruyor.')
            telegram_gonder(f'🏁 Günlük tarama bitti — {simdi.strftime("%d.%m.%Y %H:%M")}')
            break

        # Piyasa açık mı? (10:00 öncesi bekleme)
        if saat < 10.0:
            bekleme = int((10.0 - saat) * 60)
            print(f'⏳ Piyasa açılışı bekleniyor... ({bekleme} dk)')
            time.sleep(min(bekleme * 60, 900))
            continue

        # Kapanış taraması mı? (17:45+)
        kapanista = saat >= 17.75

        bir_tur_tara(kapanista=kapanista)

        # 15 dakika bekle
        print(f'  ⏱️  15 dk bekleniyor...')
        time.sleep(900)

if __name__ == '__main__':
    main()
