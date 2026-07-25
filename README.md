# Auto Clicker

Un utilitaire Python complet pour automatiser des clics de souris et des macros complexes depuis une interface graphique moderne.

## Fonctionnalités

- **4 modes de fonctionnement** : Auto Clicker classique, Salve au clic, Maintien enfoncé, Macros personnalisées
- **Interface graphique moderne** avec thème sombre
- **Raccourci clavier personnalisable** pour activer/désactiver (Caps Lock par défaut)
- **Raccourci pour changer de mode** (Alt+Caps Lock par défaut)
- **Système de macros avancé** :
  - Enregistrement et édition de macros personnalisées
  - Support des boucles (For et While)
  - Actions : appui clavier, clic souris, déplacement souris, délais
  - Exécution au clic souris ou au raccourci clavier
  - Arrêt manuel des boucles en cours
- **Persistance des données** : les macros sont automatiquement sauvegardées dans `%APPDATA%/AutoClicker/macros.json`
- **Gestion des clics** : clics gauche et droit gérés indépendamment pour éviter les chevauchements

## Prérequis

- Python 3.8+
- Modules Python :
  - `pyautogui` - simulation des clics et mouvements de souris
  - `keyboard` - gestion des raccourcis clavier
  - `pynput` - écoute des clics souris
- `tkinter` est généralement fourni avec Python sur Windows

## Installation

1. Ouvrez un terminal dans le dossier du projet
2. Installez les dépendances :

```powershell
pip install pyautogui keyboard pynput
```

#### OU

Éxécuter le fichier `.exe`

## Utilisation

### Démarrage

```powershell
python autoclicker.py
```

### Modes disponibles

#### 1. Auto Clicker classique
Clique en continu tant que l'auto clicker est activé, indépendamment de vos actions.
- **Configuration** : choisir le bouton (gauche/droit), délai entre les clics
- **Activation** : appuyer sur le raccourci clavier ou cliquer le bouton "Activer"

#### 2. Salve au clic
Envoie une salve de N clics à chaque clic souris (gauche ou droit).
- **Configuration** : nombre de clics par salve, délai entre les clics
- **Activation** : appuyer sur le raccourci clavier, puis cliquer gauche ou droit pour déclencher une salve
- **Note** : les clics gauche et droit sont indépendants (pas de chevauchement)

#### 3. Maintien enfoncé
Spam continu de clics tant que vous maintenez un bouton souris enfoncé.
- **Configuration** : délai entre les clics
- **Activation** : appuyer sur le raccourci clavier, puis maintenir le clic gauche ou droit

#### 4. Macros personnalisées
Exécute des séquences d'actions complexes (clavier, souris, délais, boucles).
- **Configuration** : éditer la liste des blocs de la macro
- **Activation** : appuyer sur le raccourci clavier ou cliquer souris pour démarrer/arrêter la macro

### Gestion des macros

#### Créer une macro
1. Sélectionner "Macros personnalisées" dans le mode
2. Cliquer "Nouvelle" pour créer une nouvelle macro
3. Donner un nom à la macro
4. Cliquer "+ Ajouter bloc" pour ajouter des actions
5. Cliquer "Enregistrer" pour sauvegarder

#### Types de blocs disponibles
- **Appuyer sur touche du clavier** : appuyer sur une touche (ex: `i`, `esc`, `ctrl+c`)
  - Utiliser "Capturer" pour enregistrer une touche à partir de votre clavier
- **Appuyer sur touche de la souris** : clic gauche ou droit
- **Déplacer la souris** : déplacer le curseur à des coordonnées X, Y
  - Utiliser "Capturer position" pour pointer à la souris (délai de 3 secondes)
- **Attendre** : pause en millisecondes
- **Boucle Pour** : répéter des blocs N fois
- **Boucle Tant que** : répéter les blocs jusqu'à arrêt ou tant qu'une touche est maintenue

#### Éditer une macro
- Double-cliquer sur un bloc dans la liste pour le modifier
- Cliquer "Supprimer" pour retirer le bloc sélectionné
- Utiliser "▲" et "▼" pour réorganiser les blocs

#### Boucles imbriquées
1. Sélectionner une boucle (For ou While)
2. Cliquer "+ Dans la boucle" pour ajouter des blocs à l'intérieur
3. Les blocs imbriqués s'affichent sous la boucle (indentés)

#### Arrêter une macro
- Cliquer "Arrêter" pendant qu'une macro est en cours
- Ou appuyer à nouveau sur le raccourci clavier d'activation

### Raccourcis clavier

- **Raccourci d'activation** (par défaut : `Caps Lock`) : active/désactive l'auto clicker
  - Cliquer "Changer" pour personnaliser ce raccourci
- **Raccourci de changement de mode** (par défaut : `Alt+Caps Lock`) : bascule au mode suivant

## Attention

- Cette application contrôle automatiquement votre souris et votre clavier.
- **Testez vos macros d'abord** avec le bouton "Tester" avant utilisation intensive.
- Vérifiez que les clics/actions sont bien ciblés avant de lancer.
- La failsafe de pyautogui est désactivée ; utilisez Alt+F4 dans la fenêtre de l'application pour arrêter rapidement si nécessaire.

## Persistance des macros

Les macros sont automatiquement sauvegardées dans :
```
%APPDATA%/SmartAutoClicker/macros.json
```

Sur Windows, ce chemin correspond généralement à :
```
C:\Users\[VotreNom]\AppData\Roaming\SmartAutoClicker\macros.json
```

Vous pouvez supprimer ce fichier pour réinitialiser toutes les macros.

## Licence

Voir [LICENCE.md](LICENCE.md)

## Crédits

- L'icône utilisée vient de icon8 : https://icons8.com/icon/koq8wWPPhKjP/autoclicker
