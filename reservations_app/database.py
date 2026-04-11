import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'reservations.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reservations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT,
            nom_client      TEXT NOT NULL,
            propriete       TEXT NOT NULL,
            source          TEXT NOT NULL,
            arrivee         DATE NOT NULL,
            depart          DATE NOT NULL,
            duree           INTEGER,
            adultes         INTEGER DEFAULT 0,
            enfants         INTEGER DEFAULT 0,
            bebes           INTEGER DEFAULT 0,
            animaux         INTEGER DEFAULT 0,
            animaux_details TEXT,
            provenance      TEXT,
            commentaire     TEXT,
            prive           BOOLEAN DEFAULT 0,
            statut          TEXT DEFAULT 'Confirmée',
            numero_resa     TEXT,
            montant         REAL
        )
    ''')
    conn.commit()

    # Insérer les données de test seulement si la table est vide
    count = conn.execute('SELECT COUNT(*) FROM reservations').fetchone()[0]
    if count == 0:
        test_data = [
            {
                'nom_client': 'JORGE - MADRID',
                'propriete': 'VP-BB',
                'source': 'Booking',
                'arrivee': '2026-02-21',
                'depart': '2026-03-08',
                'adultes': 2, 'enfants': 0, 'bebes': 0, 'animaux': 2,
                'provenance': 'Madrid · Espagne',
                'commentaire': '', 'statut': 'Confirmée'
            },
            {
                'nom_client': 'DUPONT - PARIS',
                'propriete': 'AV-ANN',
                'source': 'Airbnb',
                'arrivee': '2026-04-10',
                'depart': '2026-04-16',
                'adultes': 2, 'enfants': 0, 'bebes': 0, 'animaux': 1,
                'provenance': 'Paris · France',
                'commentaire': '', 'statut': 'Confirmée'
            },
            {
                'nom_client': 'MARTIN - LYON',
                'propriete': 'VP-ETE',
                'source': 'Direct',
                'arrivee': '2026-07-01',
                'depart': '2026-07-24',
                'adultes': 4, 'enfants': 2, 'bebes': 0, 'animaux': 0,
                'provenance': 'Lyon · France',
                'commentaire': 'Acompte reçu', 'statut': 'Confirmée'
            },
        ]
        for r in test_data:
            code = generate_code(r['adultes'], r['enfants'], r['bebes'], r['animaux'], r['propriete'])
            duree = calculer_duree(r['arrivee'], r['depart'])
            conn.execute('''
                INSERT INTO reservations
                    (code, nom_client, propriete, source, arrivee, depart, duree,
                     adultes, enfants, bebes, animaux, provenance, commentaire, statut)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (code, r['nom_client'], r['propriete'], r['source'],
                  r['arrivee'], r['depart'], duree,
                  r['adultes'], r['enfants'], r['bebes'], r['animaux'],
                  r['provenance'], r['commentaire'], r['statut']))
        conn.commit()
    conn.close()


def encode_val(n):
    """Encode une valeur numérique : 0-9 → chiffre, 10=A, 11=B, ..."""
    if n < 10:
        return str(n)
    return chr(ord('A') + n - 10)


def generate_code(adultes, enfants, bebes, animaux, propriete):
    a = encode_val(int(adultes or 0))
    e = encode_val(int(enfants or 0))
    b = encode_val(int(bebes or 0))
    an = encode_val(int(animaux or 0))
    return f"{a}{e}{b}{an}-{propriete}"


def calculer_duree(arrivee, depart):
    from datetime import date
    try:
        d1 = date.fromisoformat(arrivee)
        d2 = date.fromisoformat(depart)
        return (d2 - d1).days
    except Exception:
        return 0


def get_all_reservations(propriete=None, source=None, statut=None, mois=None, search=None):
    conn = get_db()
    query = 'SELECT * FROM reservations WHERE 1=1'
    params = []
    if propriete:
        query += ' AND propriete = ?'
        params.append(propriete)
    if source:
        query += ' AND source = ?'
        params.append(source)
    if statut:
        query += ' AND statut = ?'
        params.append(statut)
    if mois:
        query += " AND strftime('%Y-%m', arrivee) = ?"
        params.append(mois)
    if search:
        query += ' AND nom_client LIKE ?'
        params.append(f'%{search}%')
    query += ' ORDER BY arrivee'
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_reservation(id):
    conn = get_db()
    row = conn.execute('SELECT * FROM reservations WHERE id = ?', (id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_reservation(data):
    conn = get_db()
    code = generate_code(data.get('adultes', 0), data.get('enfants', 0),
                         data.get('bebes', 0), data.get('animaux', 0),
                         data.get('propriete', ''))
    duree = calculer_duree(data.get('arrivee', ''), data.get('depart', ''))
    conn.execute('''
        INSERT INTO reservations
            (code, nom_client, propriete, source, arrivee, depart, duree,
             adultes, enfants, bebes, animaux, animaux_details,
             provenance, commentaire, prive, statut, numero_resa, montant)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (code, data['nom_client'], data['propriete'], data['source'],
          data['arrivee'], data['depart'], duree,
          data.get('adultes', 0), data.get('enfants', 0),
          data.get('bebes', 0), data.get('animaux', 0),
          data.get('animaux_details', ''),
          data.get('provenance', ''), data.get('commentaire', ''),
          1 if data.get('prive') else 0,
          data.get('statut', 'Confirmée'),
          data.get('numero_resa', ''), data.get('montant') or None))
    conn.commit()
    conn.close()


def update_reservation(id, data):
    conn = get_db()
    code = generate_code(data.get('adultes', 0), data.get('enfants', 0),
                         data.get('bebes', 0), data.get('animaux', 0),
                         data.get('propriete', ''))
    duree = calculer_duree(data.get('arrivee', ''), data.get('depart', ''))
    conn.execute('''
        UPDATE reservations SET
            code=?, nom_client=?, propriete=?, source=?, arrivee=?, depart=?, duree=?,
            adultes=?, enfants=?, bebes=?, animaux=?, animaux_details=?,
            provenance=?, commentaire=?, prive=?, statut=?, numero_resa=?, montant=?
        WHERE id=?
    ''', (code, data['nom_client'], data['propriete'], data['source'],
          data['arrivee'], data['depart'], duree,
          data.get('adultes', 0), data.get('enfants', 0),
          data.get('bebes', 0), data.get('animaux', 0),
          data.get('animaux_details', ''),
          data.get('provenance', ''), data.get('commentaire', ''),
          1 if data.get('prive') else 0,
          data.get('statut', 'Confirmée'),
          data.get('numero_resa', ''), data.get('montant') or None,
          id))
    conn.commit()
    conn.close()


def delete_reservation(id):
    conn = get_db()
    conn.execute('DELETE FROM reservations WHERE id = ?', (id,))
    conn.commit()
    conn.close()


def get_reservations_for_month(year, month):
    """Retourne toutes les réservations qui chevauchent le mois donné."""
    from datetime import date
    import calendar
    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])
    conn = get_db()
    rows = conn.execute('''
        SELECT * FROM reservations
        WHERE arrivee <= ? AND depart > ?
        ORDER BY arrivee
    ''', (last_day.isoformat(), first_day.isoformat())).fetchall()
    conn.close()
    return [dict(r) for r in rows]
