# MACD Bot — GitHub Actions Kurulum (5 Adım)

## Adım 1 — GitHub hesabı aç
https://github.com → ücretsiz hesap oluştur

## Adım 2 — Yeni repo oluştur
- "New repository" → isim: `macd-bot` → Public → Create

## Adım 3 — Dosyaları yükle
Bu klasördeki 3 dosyayı repo'ya yükle:
- `macd_bot.py`
- `.github/workflows/macd_bot.yml`  
- `pozisyonlar.csv`

## Adım 4 — Telegram bilgilerini gizlice ekle
Repo → Settings → Secrets and variables → Actions → New repository secret

| Name | Value |
|------|-------|
| TELEGRAM_TOKEN | 8688567060:AAETdJbeE6TkMg3JDQEr8F9q_WjEGSw6jnc |
| TELEGRAM_CHAT_ID | 5722886581 |

## Adım 5 — İlk testi yap
Actions → MACD AL/SAT Bot → Run workflow → Run

✅ Bundan sonra her gün 18:10'da otomatik çalışır.
Colab'a gerek yok, bilgisayar kapalı olsa bile çalışır.
