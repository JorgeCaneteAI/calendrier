import sys
import os

# Force l'interpréteur du venv o2switch pour éviter la récursion du wrapper Passenger
INTERP = '/home/efkz3012/virtualenv/cal.villaplaisance.fr/3.9/bin/python'
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

# Chemin absolu vers le dossier de l'app
APP_DIR = '/home/efkz3012/cal.villaplaisance.fr'
sys.path.insert(0, APP_DIR)

# Charger la variable d'environnement SECRET_KEY depuis .env
env_file = os.path.join(APP_DIR, '.env')
if os.path.exists(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key.strip()] = val.strip()

from app import app as application
