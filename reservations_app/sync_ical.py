"""
Synchronisation des calendriers iCal (Airbnb + Booking).
Appelé manuellement via la route /sync ou en ligne de commande.
"""

import re
import urllib.request
from datetime import date
from database import get_db, generate_code, calculer_duree

# ─── Configuration des flux iCal ───────────────────────────────────────────────

ICAL_FEEDS = [
    {
        'url': 'https://www.airbnb.fr/calendar/ical/3520144.ics?t=5947398f53f7446bbb769c58f8ef322f',
        'propriete': 'AV-ANN',
        'source': 'Airbnb',
    },
    {
        'url': 'https://www.airbnb.fr/calendar/ical/597660428689098985.ics?t=64ded1ce0b024ff5b6b62f7fdcbb3e01',
        'propriete': 'VP-BB',
        'source': 'Airbnb',
    },
    {
        'url': 'https://www.airbnb.fr/calendar/ical/625764424244747021.ics?t=a1efb4b6dcb64e69a56939227503466e',
        'propriete': 'VP-ETE',
        'source': 'Airbnb',
    },
    {
        'url': 'https://ical.booking.com/v1/export?t=0c2ec4cc-4968-4753-9227-0c18b3094247',
        'propriete': 'VP-BB',
        'source': 'Booking',
    },
]


# ─── Parser iCal ───────────────────────────────────────────────────────────────

def parse_ical(text):
    """Parse un texte iCal et retourne une liste d'événements (dict)."""
    events = []
    current = {}
    in_event = False
    pending_key = None

    for raw_line in text.splitlines():
        # Les lignes iCal qui commencent par un espace/tab sont des continuations
        if raw_line and raw_line[0] in (' ', '\t') and pending_key and in_event:
            current[pending_key] = current.get(pending_key, '') + raw_line[1:]
            continue

        line = raw_line.strip()
        pending_key = None

        if line == 'BEGIN:VEVENT':
            in_event = True
            current = {}
        elif line == 'END:VEVENT':
            if in_event and current.get('uid') and current.get('dtstart') and current.get('dtend'):
                events.append(current)
            in_event = False
            current = {}
        elif in_event and ':' in line:
            key, _, val = line.partition(':')
            key_base = key.split(';')[0].upper()
            mapping = {
                'UID': 'uid',
                'DTSTART': 'dtstart',
                'DTEND': 'dtend',
                'SUMMARY': 'summary',
                'DESCRIPTION': 'description',
            }
            if key_base in mapping:
                field = mapping[key_base]
                current[field] = val.strip()
                pending_key = field

    return events


def parse_date(s):
    """Convertit une date iCal (YYYYMMDD ou YYYYMMDDTHHMMSSZ) en date Python."""
    s = s.replace('Z', '').split('T')[0]
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))


def is_real_reservation(event, source):
    """
    Airbnb : seuls les événements SUMMARY=Reserved sont de vraies réservations.
             Les 'Airbnb (Not available)' sont des blocages automatiques (tampon).
    Booking : tout 'CLOSED - Not available' est une réservation ou un blocage → on importe tout.
    """
    summary = event.get('summary', '')
    if source == 'Airbnb':
        return summary == 'Reserved'
    return True  # Booking


# ─── Migration DB ───────────────────────────────────────────────────────────────

def ensure_ical_uid_column():
    """Ajoute la colonne ical_uid si elle n'existe pas encore."""
    conn = get_db()
    try:
        conn.execute('ALTER TABLE reservations ADD COLUMN ical_uid TEXT')
        conn.commit()
    except Exception:
        pass  # Colonne déjà présente
    conn.close()


# ─── Sync ──────────────────────────────────────────────────────────────────────

def sync_feed(feed):
    """
    Synchronise un flux iCal.
    Retourne (nb_créés, nb_mis_à_jour, nb_supprimés).
    """
    url = feed['url']
    propriete = feed['propriete']
    source = feed['source']

    with urllib.request.urlopen(url, timeout=15) as resp:
        text = resp.read().decode('utf-8')

    events = parse_ical(text)
    created = 0
    updated = 0
    deleted = 0

    conn = get_db()
    active_uids = set()

    for event in events:
        if not is_real_reservation(event, source):
            continue

        uid = event['uid']
        active_uids.add(uid)
        arrivee = parse_date(event['dtstart']).isoformat()
        depart = parse_date(event['dtend']).isoformat()

        # Extraire le code de réservation Airbnb depuis la description
        numero_resa = ''
        description = event.get('description', '')
        if source == 'Airbnb' and description:
            m = re.search(r'/reservations/details/([A-Z0-9]+)', description)
            if m:
                numero_resa = m.group(1)

        row = conn.execute(
            'SELECT id, arrivee, depart, nom_client FROM reservations WHERE ical_uid = ?',
            (uid,)
        ).fetchone()

        if row:
            if row['arrivee'] != arrivee or row['depart'] != depart:
                duree = calculer_duree(arrivee, depart)
                conn.execute(
                    'UPDATE reservations SET arrivee=?, depart=?, duree=? WHERE id=?',
                    (arrivee, depart, duree, row['id'])
                )
                conn.commit()
                updated += 1
        else:
            code = generate_code(0, 0, 0, 0, propriete)
            duree = calculer_duree(arrivee, depart)
            conn.execute('''
                INSERT INTO reservations
                    (code, nom_client, propriete, source, arrivee, depart, duree,
                     adultes, enfants, bebes, animaux, statut, numero_resa, ical_uid)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'Confirmée', ?, ?)
            ''', (code, source, propriete, source, arrivee, depart, duree, numero_resa, uid))
            conn.commit()
            created += 1

    # Supprimer les réservations iCal de ce flux qui ne sont plus dans le feed
    db_rows = conn.execute(
        'SELECT id, ical_uid FROM reservations WHERE source=? AND propriete=? AND ical_uid IS NOT NULL AND ical_uid != ""',
        (source, propriete)
    ).fetchall()
    for row in db_rows:
        if row['ical_uid'] not in active_uids:
            conn.execute('DELETE FROM reservations WHERE id=?', (row['id'],))
            deleted += 1
    if deleted:
        conn.commit()

    conn.close()
    return created, updated, deleted


def sync_all():
    """Synchronise tous les flux iCal. Retourne un dict résumé."""
    ensure_ical_uid_column()

    total_created = 0
    total_updated = 0
    total_deleted = 0
    errors = []

    for feed in ICAL_FEEDS:
        try:
            created, updated, deleted = sync_feed(feed)
            total_created += created
            total_updated += updated
            total_deleted += deleted
        except Exception as e:
            errors.append(f"{feed['propriete']} ({feed['source']}) : {e}")

    return {
        'created': total_created,
        'updated': total_updated,
        'deleted': total_deleted,
        'errors': errors,
    }


if __name__ == '__main__':
    result = sync_all()
    print(f"✅ Créées : {result['created']}  |  Mises à jour : {result['updated']}")
    for err in result['errors']:
        print(f"❌ {err}")
