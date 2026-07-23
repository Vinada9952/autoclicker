# Auto Clicker

Un utilitaire Python simple pour automatiser des clics de souris en rafale depuis une interface graphique.

## Fonctionnalités

- Activation/désactivation manuelle depuis l'interface
- Lancement de rafales de clics lors d'un clic gauche ou droit
- Nombre de clics configurable
- Délai entre chaque clic configurable (en millisecondes)
- Raccourci clavier personnalisable pour activer/désactiver
- Interface sombre moderne avec état de l'autoclicker

## Prérequis

- Python 3.8+
- Modules Python :
  - `pyautogui`
  - `keyboard`
  - `pynput`
- `tkinter` est généralement fourni avec Python sur Windows

## Installation

1. Ouvrez un terminal dans le dossier du projet
2. Installez les dépendances :

```powershell
pip install pyautogui keyboard pynput
```

## Utilisation

1. Lancez le script :

```powershell
python autoclicker.py
```

2. Configurez :
   - Nombre de clics par déclenchement
   - Délai entre chaque clic
   - Raccourci d'activation

3. Cliquez n'importe où avec le bouton gauche ou droit pour démarrer une rafale.
4. Utilisez le bouton ou le raccourci clavier pour activer/désactiver l'autoclicker.
5. Fermez la fenêtre pour quitter l'application.

## Attention

- Cette application contrôle la souris de façon automatique.
- Vérifiez que les clics sont bien ciblés avant de lancer une rafale.

## Notes

- Les clics gauche et droit sont gérés indépendamment, ce qui évite les chevauchements de rafales sur le même bouton.
- Le raccourci clavier par défaut est `Caps Lock`.
