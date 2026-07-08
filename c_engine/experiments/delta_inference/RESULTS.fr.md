[English](RESULTS.md) · **Français** · [Español](RESULTS.es.md) · [简体中文](RESULTS.zh-CN.md) · [Deutsch](RESULTS.de.md) · [日本語](RESULTS.ja.md) <!-- i18n-switcher -->

# Expérience d'inférence delta — Résultats

**Date :** 2026-05-19
**Question :** Atome peut-il éviter le recalcul comme l'œil ne re-rend pas un mur
statique ? Mesurer le recalcul complet vs le matvec ternaire à delta temporel.

## Montage

- Matrice ternaire 256×256 (reflète le `d_model` du modèle Atome 944K), ~1/3 de zéros
- Flux d'entrée de 256 pas, trois régimes d'entrée
- `out_new = out_old + W @ (x_new - x_prev)` — exact au seuil 0
- Mise à jour sélective de `x_prev` : seuls les canaux propagés se mettent à jour, de sorte que
  l'erreur en attente de chaque canal est bornée par `threshold` à tout instant — c'est l'intègre-et-tire
- Proxy d'énergie : `iters` = passages dans la boucle interne (chaque passage dépaquette un trit + branche,
  ~1 cycle sur un MCU, qu'il fasse un MAC ou non). Déterministe et exact.

## Résultats (hôte, cycles par chemin mesurés séparément)

| Régime | seuil | accél. iter | accél. cycles | erreur max |
|---|---|---|---|---|
| **Flux de capteur** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (entrée corrélée) | 0.005 | **17.52×** | 15.66× | 0.00715 |
| | 0.020 | **51.24×** | 42.96× | 0.01845 |
| | 0.050 | **59.67×** | 49.07× | 0.03455 |
| **Plongements de jetons** | 0.000 | 1.00× | 1.04× | 0.00001 |
| (non corrélé / génération LM) | 0.005 | 1.01× | 1.05× | 0.00072 |
| **Proxy d'état caché** | 0.000 | 3.30× | 3.25× | 0.00001 |
| (~30 % des canaux bougent) | 0.005 | 3.39× | 3.34× | 0.00171 |
| | 0.020 | 3.68× | 3.59× | 0.01163 |

QEMU Cortex-M3 (`mps2-an385`) : les `iters` sont **bit-identiques** à l'hôte
(16 711 680 / 954 112 / 326 144 / …) — le proxy d'énergie se reproduit exactement sur
l'ISA cible. Le compteur de cycles DWT sur cible lit 0 parce que le `mps2-an385` de QEMU
ne modélise pas `DWT->CYCCNT` ; les nombres de cycles sur silicium réel nécessitent une carte
de développement Cortex-M3 ou un modèle exact au cycle près. L'horloge murale de l'hôte confirme déjà
que les `iters` suivent les vrais cycles (15,66× cycle vs 17,52× iter — l'écart, c'est le surcoût
de boucle/appel).

## Conclusions

1. **Le gain est réel et grand — mais seulement pour une entrée corrélée.** Un flux
   de style capteur au seuil 0,005 exécute **17,5× moins d'opérations** pour une erreur de
   sortie pire cas de 0,007 (les poids ont une échelle de 0,05, donc c'est ~0,7 % d'un
   logit typique). Au seuil 0,02 c'est **51×**. Pour un appareil MCU qui est un
   thermostat, un détecteur de gestes par accéléromètre, ou un repéreur de mots-clés
   audio, c'est une coupe directe de 17-51× dans l'énergie d'inférence.

2. **Pas de repas gratuit pour la génération LM par jetons — confirmé.** Le scénario B tient à
   1,0×. Les plongements d'octets consécutifs sont non corrélés ; il n'y a pas de « mur
   statique » à sauter. C'est le résultat honnête et il correspond à la prédiction. L'inférence
   delta est une optimisation *de modalité d'entrée*, pas universelle.

3. **Les états cachés du milieu de réseau se situent entre les deux (~3,3×).** Même sans seuil,
   un flux résiduel où ~30 % des canaux bougent par pas donne 3,3× gratuitement
   (exact, erreur 1e-5) parce que 70 % du matvec est réellement redondant. C'est
   le nombre le plus intéressant : il suggère que l'inférence delta aide *à l'intérieur* du
   réseau même quand l'entrée par jetons n'aide pas, en particulier pour la voie SSM
   dont l'état évolue lentement.

4. **Le seuil est littéralement un seuil de déclenchement.** Parce que `x_prev` ne se met à jour
   que pour les canaux propagés, un canal avec une dérive sous le seuil intègre
   silencieusement jusqu'à ce qu'il franchisse la barre, se déclenche une fois, et se réinitialise. L'erreur est bornée par
   `threshold` sans accumulation et sans rafraîchissement « saccade » périodique
   requis. Le compromis énergie/précision est un unique bouton.

## Limites honnêtes

- La matrice synthétique 256×256 est représentative mais pas un jeu de poids Atome
  entraîné réel — la structure de parcimonie réelle des poids peut décaler les constantes (pas
  la tendance).
- Seul le matvec est « delta-isé ». LayerNorm/SSM/attention sont non linéaires ; une
  intégration complète nécessite des variantes delta-conscientes (ou périodiquement rafraîchies) de ceux-ci.
- « iters » est un proxy d'énergie fidèle pour la boucle interne du matvec mais ignore
  l'énergie du trafic mémoire, qui sur un vrai MCU peut dominer — l'accélération *réelle* sur
  silicium pourrait être plus élevée (moins de mouvement de données) ou plus faible (pire comportement de cache
  dû au motif d'accès delta en colonne-major). Nécessite une mesure sur carte de développement.
- Le résultat en régime jeton (1,0×) est le plafond honnête : ne pas présenter l'inférence delta
  comme une accélération de génération LM. Présentez-la pour les classifieurs de flux de capteurs.

## Recommandation

Câblez l'inférence delta comme un **mode opt-in pour les déploiements de classifieurs de flux**
(le chemin `atome_classify` d'Atome sur entrée capteur), pas le chemin génératif. La
voie SSM est l'endroit naturel pour l'étendre ensuite — son état est le signal le plus lent
du réseau. Associez le seuil au moniteur de norme d'état L11
(de la pile de sécurité) comme chien de garde de dérive. Enveloppe attendue : **15-50×
de réduction d'énergie d'inférence** pour les appareils de classe thermostat/audio/geste, à un
coût de précision borné et ajustable.

## Reproduire

```bash
cd c_engine/experiments/delta_inference
make run        # host (synthetic)
make run-qemu   # cortex-m3 under QEMU (iters bit-identical to host)
make real       # validation on the real 944K weights (see below)
```

---

# Extension : validation sur le vrai modèle Atome 944K

L'expérience synthétique ci-dessus utilisait une matrice aléatoire. Cette section exécute le
chemin delta contre `checkpoints/atome_1m_v1.pt` (le vrai modèle 944K entraîné,
val_loss 1,0545) sur un vrai passage TinyStories de 196 octets.

`capture_real.py` accroche chaque bloc, capture la vraie entrée post-norm et
chaque sortie de voie, et mesure la redondance delta par signal. `bench_real.c`
exécute ensuite le `dm_matvec_delta` **C** sur les vrais flux capturés en utilisant le
**vrai Wv d'attention ternarisé** du modèle, et confirme que la primitive C
reproduit la prédiction numpy.

## Accélération delta-matvec par voie (poids réels, moyenne sur 8 blocs)

| Signal consommé par un matvec | seuil 0.0 | seuil 0.02 | seuil 0.05 | seuil 0.10 |
|---|---|---|---|---|
| entrée post-norm `h` | 1.00× | 1.05× | 1.11× | 1.17× |
| sortie de la voie conv | 1.01× | 1.06× | 1.12× | 1.22× |
| **sortie de la voie SSM** | 1.00× | **4.06×** | **12.27×** | **45.16×** |
| sortie de la voie attention | 1.02× | 1.07× | 1.15× | 1.27× |

## Contre-vérification de la primitive C (bloc 0, vrai Wv 256×256, échelle 0.0412)

| matvec | seuil 0.0 | seuil 0.02 | seuil 0.05 | seuil 0.10 |
|---|---|---|---|---|
| `Wv @ h` (prédiction numpy) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ h` (**C mesuré**) | 1.03× | 1.26× | 1.53× | 1.61× |
| `Wv @ ssm_out` (prédiction numpy) | 1.00× | 3.12× | 8.60× | 33.64× |
| `Wv @ ssm_out` (**C mesuré**) | 1.00× | 3.12× | 8.60× | 33.64× |

La primitive delta C et la référence numpy s'accordent **exactement** sur de vrais
poids entraînés et de vraies activations. L'erreur max par canal reste ≤ seuil
(mesuré 0,10000 au seuil 0,10) — la borne intègre-et-tire tient sur données réelles.

## Conclusions — et un honnête négatif

1. **La sortie de la voie SSM est le point idéal du delta, et de loin.** Sur
   des poids réels, elle est 4-45× delta-compressible ; tout autre signal du
   bloc est de 1,0-1,3×. Un matvec alimenté par la sortie SSM fait 12× moins de travail au
   seuil 0,05 pour ~5 % d'erreur par canal.

2. **Le SSM lui-même ne peut pas être delta-compressé — et c'est très bien.** C'est une
   récurrence par canal `h_t = a·h_{t-1} + b·x_t` ; chaque pas dépend du
   dernier, donc aucun pas ne peut être sauté. Mais il est déjà O(canaux), pas le
   goulot d'étranglement. Son rôle dans l'inférence delta est celui de *générateur de signal lent* :
   c'est un filtre passe-bas par canal, donc sa sortie est le signal le plus
   corrélé en position du réseau — ce qui est exactement ce qui rend le
   matvec en aval delta-friendly. La recommandation précédente de RESULTS
   (« étendre le delta au SSM ») était à moitié juste : étendez-le au matvec qui
   *consomme* le SSM, pas à la récurrence SSM elle-même.

3. **Honnête négatif : `h` post-norm, sortie conv et sortie attention ne sont PAS
   delta-friendly (~1,0-1,3×).** LayerNorm renormalise chaque position si bien que `h`
   se décale sur presque chaque canal ; les sorties conv et attention changent réellement
   de position en position. L'inférence delta sur les projections Wq/Wk/Wv d'attention
   (qui consomment `h`) n'apporte presque rien. Ne la déployez pas là.

4. **Les blocs plus profonds sont plus delta-friendly que le bloc 0** (45× en moyenne sur 8 blocs
   vs 33× au bloc 0, seuil 0,10) — l'état SSM se réchauffe avec la profondeur, si bien que la
   propriété de signal lent se renforce plus profond dans le réseau.

## Recommandation affinée

Déployez l'inférence delta sur **les couches matvec qui consomment la sortie de la voie
SSM**, pas sur les projections d'attention et pas sur la récurrence SSM
elle-même. Sur le vrai modèle 944K, c'est une **réduction de calcul mesurée de 8-12×**
au seuil 0,05 (≈5 % d'erreur par canal, bornée), montant à 33-45× au
seuil 0,10. Associez le seuil au moniteur de norme d'état L11 comme chien de garde de
dérive.

## Coût en qualité — mesuré (2026-05-20, `quality_real.py`)

Le brouillon précédent retenait le chiffre d'énergie parce que le coût en *qualité* de
l'erreur de seuillage n'était pas mesuré. Il l'est maintenant. L'inférence delta sur un
matvec consommant un signal S équivaut à alimenter le matvec exact avec un
S seuillé par intègre-et-tire ; donc nous seuillons la sortie SSM de chaque bloc,
exécutons le reste du vrai modèle 944K exactement, et mesurons l'entropie croisée.

| seuil | accél. voie SSM | Δ perplexité |
|---|---|---|
| 0.00 | 1.0× | +0.00% (exact — contrôle de cohérence) |
| 0.02 | 4.1× | −0.46% (dans le bruit) |
| **0.05** | **12.6×** | **+0.57%** |
| 0.10 | 49× | +5.6% |
| 0.20 | 320× | +11.5% (casse) |

**L'affirmation survit.** Au seuil 0,05, la voie SSM donne une vraie
**réduction de 12,6× du nombre d'itérations pour +0,57 % de perplexité** sur le modèle
entraîné — un compromis livrable. À 0,10 c'est agressif (49× / +5,6 %) ; à 0,20
ça casse. Cela réfute aussi la crainte que la sortie SSM soit « quasi constante
et ne contribue à rien » : si elle ne contribuait à rien, la rendre périmée serait gratuit
à chaque seuil — au lieu de cela, 0,20 coûte +11,5 %, donc la sortie SSM compte réellement
et le modèle tolère réellement une péremption *bornée*.

## Réserve honnête restante

Le chiffre de qualité ci-dessus est l'**entropie croisée en position de préremplissage (prefill)**, pas
la génération autorégressive. La propriété passe-bas du SSM devrait se transmettre à la
génération (c'est un filtre récurrent), mais une mesure en pas de génération n'a
pas été exécutée. Énoncez le chiffre 12,6×/+0,57 % avec cette réserve attachée.

## Reproduire (extension poids réels)

```bash
cd c_engine/experiments/delta_inference
python3 capture_real.py   # loads the real 944K ckpt, writes traces/
make real                 # C primitive cross-check on the real traces
```
