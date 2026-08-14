# Śrī Venkateśvara — Srinivasa Govinda

A cinematic 9:16 (1080×1920) devotional video: original Mohanam-raga bhajan
with Ken Burns stills of Lord Venkateshwara, the Tirumala hills, and the
illuminated gopuram.

## Watch

`output/venkateshwara-swami.mp4`

## Song

**Title:** Srinivasa Govinda (original bhajan)  
**Raga:** Mohanam  
**Tala feel:** 4-beat, ~70 BPM  

Traditional public-domain mantras are used. No copyrighted film or commercial
recording is included.

```
ॐ नमो वेङ्कटेशाय
Om Namo Venkatesaya

గోవిందా గోవిందా
Govinda Govinda

శ్రీనివాస గోవిందా
Srinivasa Govinda

Tirumala giri vaasa
Jyothi swaroopa

Shankha chakra dhara
Bhakta vatsala

गोविन्द गोविन्द
Hari Om
```

## Rebuild

```bash
python3 scripts/compose_bhajan.py
python3 scripts/make_video.py
```

Requires Python 3 with `numpy`, `pillow`, `scipy`, and `ffmpeg`.

## Enhanced gopuram stills

High-resolution night finishes of the Tirumala gopuram (2304×3456):

- `assets/enhanced/tirumala-gopuram-night-enhanced.png`
- `assets/enhanced/tirumala-gopuram-lowangle-enhanced.png`

```bash
python3 scripts/enhance_gopuram.py
```

## Original photos + natural edits

Faithful recreations of the original night shots, plus a clean photo finish
(denoise, richer gold, sharper carvings) without changing the scene:

- Shrine in the pond: `assets/originals/my-shrine-original.jpg` → `my-shrine-edited.png`
- Gopuram: `assets/originals/my-gopuram-original.jpg` → `my-gopuram-edited.png`
- Courtyard: `assets/originals/my-courtyard-original.jpg` → `my-courtyard-edited.png`

```bash
python3 scripts/enhance_originals.py
```
