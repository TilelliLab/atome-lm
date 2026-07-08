[English](README.md) · **Français** · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [Deutsch](README.de.md) · [日本語](README.ja.md) <!-- i18n-switcher -->

# Squelette de firmware SuperESP (ESP32 / ESP-IDF)

> **Statut : squelette DE COMPILATION SEULE — NON FLASHÉ, NON MESURÉ sur silicium.**
> Cette machine n'a pas d'ESP32 physique ni de chaîne d'outils ESP-IDF. Le firmware ci-dessous
> est la vraie structure (il réutilise le moteur `atome.c`/`atome.h` vendorisé et
> les blobs de tête ATOMECL01 entraînés), mais les tok/s sur carte, le point haut de RAM et
> la capture ADC/I2S en direct **ne sont pas mesurés ici**. Le dispatcher C côté hôte
> `c_engine/superesp/superesp_os.c` *est* compilé et testé (voir les tests superesp).

## Ce qu'il fait (l'idée « OS »)
Au démarrage, le firmware :
1. Lit la propre télémétrie de l'ESP32 — `esp_get_free_heap_size()`, capteur de température
   interne, RSSI Wi-Fi, canaux ADC, hall, touch — dans la **trame OS fusionnée**.
2. Quantifie cette trame en octets (en utilisant les `vmin/vmax` par caractéristique cuits depuis
   `os_telem.tok.json`) et exécute `atome_classify` avec la **tête OS** pour obtenir un
   état d'appareil (normal / low_memory / overheating / wifi_degraded / power_fault).
3. Applique la politique de délestage (par ex. désactive les têtes audio en cas de
   surchauffe), puis lit le capteur actif (ADC pour agri, micro I2S pour voice)
   et route cette trame vers sa tête — en s'abstenant en cas d'incertitude.

Ainsi Atome tourne comme le superviseur de l'appareil, pas comme un générateur de texte. Les 7 têtes partagent
une seule compilation de moteur (même config partagée) ; chaque tête est un blob embarqué différent.

## Pour compiler (sur une machine avec ESP-IDF + une carte)
```
idf.py set-target esp32
idf.py build            # compile-time config in main/CMakeLists.txt
idf.py -p /dev/ttyUSB0 flash monitor
```
Les defines à la compilation (d_model=32, n_layers=2, ...) DOIVENT correspondre à la config
partagée de SuperESP (superesp/framework/config.py) avec laquelle les blobs ont été exportés.
