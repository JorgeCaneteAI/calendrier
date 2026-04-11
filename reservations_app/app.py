from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file, session, flash
import calendar
import locale
from datetime import date, datetime, timedelta
import os
import secrets

from database import (init_db, get_all_reservations, get_reservation,
                      create_reservation, update_reservation, delete_reservation,
                      get_reservations_for_month, generate_code)
from export_pdf import export_month_pdf, export_year_pdf
from auth import check_password, check_pin, login_required, get_auth
from sync_ical import sync_all


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
app.permanent_session_lifetime = timedelta(days=30)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


def generate_csrf():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf():
    token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    return token and token == session.get('csrf_token')


app.jinja_env.globals['csrf_token'] = generate_csrf

# Essayer de définir la locale française pour les noms de mois
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except Exception:
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except Exception:
        pass

MOIS_FR = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
           'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

COULEURS = {
    'Airbnb':   {'bg': '#FF5A5F', 'text': '#ffffff'},
    'Booking':  {'bg': '#003580', 'text': '#ffffff'},
    'Direct':   {'bg': '#639922', 'text': '#ffffff'},
    'Privée':   {'bg': '#888780', 'text': '#ffffff'},
    'Absence':  {'bg': '#2C2C2A', 'text': '#ffffff'},
}


def build_calendar_data(year, month):
    """Construit la grille du calendrier avec les réservations."""
    reservations = get_reservations_for_month(year, month)
    cal = calendar.Calendar(firstweekday=0)  # Lundi en premier
    weeks = cal.monthdatescalendar(year, month)

    # Pré-traitement : pour chaque réservation, calculer les jours couverts dans le mois
    import calendar as cal_module
    first_day = date(year, month, 1)
    last_day_num = cal_module.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    resa_by_day = {}  # date -> list of resa
    for r in reservations:
        arr = date.fromisoformat(r['arrivee'])
        dep = date.fromisoformat(r['depart'])
        # La réservation couvre : arrivée incluse, départ EXCLU (dernier jour = nuit avant départ)
        start = max(arr, first_day)
        end = min(dep - __import__('datetime').timedelta(days=1), last_day)
        d = start
        while d <= end:
            if d not in resa_by_day:
                resa_by_day[d] = []
            resa_by_day[d].append({
                'id': r['id'],
                'code': r['code'],
                'nom_client': r['nom_client'],
                'source': r['source'],
                'provenance': r['provenance'] or '',
                'commentaire': r['commentaire'] or '',
                'couleur': COULEURS.get(r['source'], {'bg': '#888780', 'text': '#ffffff'}),
                'arrivee': arr,
                'depart': dep,
                'is_start': d == arr or d == first_day,
                'is_end': (d == dep - __import__('datetime').timedelta(days=1)) or d == last_day,
                'first_day_of_resa_in_month': d == start,
            })
            d += __import__('datetime').timedelta(days=1)

    return weeks, resa_by_day


LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 10
LOCKOUT_MINUTES = 15


def is_locked_out(ip):
    entry = LOGIN_ATTEMPTS.get(ip)
    if not entry:
        return False
    if entry['count'] >= MAX_ATTEMPTS:
        elapsed = (datetime.now() - entry['last']).total_seconds() / 60
        if elapsed < LOCKOUT_MINUTES:
            return True
        LOGIN_ATTEMPTS.pop(ip, None)
    return False


def record_attempt(ip, success):
    if success:
        LOGIN_ATTEMPTS.pop(ip, None)
        return
    entry = LOGIN_ATTEMPTS.get(ip, {'count': 0})
    entry['count'] = entry.get('count', 0) + 1
    entry['last'] = datetime.now()
    LOGIN_ATTEMPTS[ip] = entry


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    error = None
    ip = request.remote_addr
    if request.method == 'POST':
        if is_locked_out(ip):
            error = f'Trop de tentatives. Réessaie dans {LOCKOUT_MINUTES} minutes.'
        else:
            username = request.form.get('username', '')
            password = request.form.get('password', '')
            next_url = request.form.get('next', '')
            if check_password(username, password):
                record_attempt(ip, True)
                session['password_ok'] = True
                session['next_after_pin'] = next_url
                return redirect(url_for('pin'))
            record_attempt(ip, False)
            error = 'Identifiant ou mot de passe incorrect.'
    return render_template('login.html', error=error,
                           next=request.args.get('next', ''))


@app.route('/pin', methods=['GET', 'POST'])
def pin():
    if session.get('logged_in'):
        return redirect(url_for('index'))
    if not session.get('password_ok'):
        return redirect(url_for('login'))
    error = None
    if request.method == 'POST':
        pin_value = request.form.get('pin', '')
        if check_pin(pin_value):
            session.permanent = True
            session['logged_in'] = True
            session.pop('password_ok', None)
            next_url = session.pop('next_after_pin', '') or url_for('index')
            return redirect(next_url)
        error = 'PIN incorrect.'
    return render_template('pin.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    today = date.today()
    year = int(request.args.get('year', today.year))
    month = int(request.args.get('month', today.month))

    # Navigation
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    weeks, resa_by_day = build_calendar_data(year, month)

    return render_template('index.html',
                           year=year, month=month,
                           mois_nom=MOIS_FR[month],
                           weeks=weeks,
                           num_weeks=len(weeks),
                           resa_by_day=resa_by_day,
                           today=today,
                           couleurs=COULEURS,
                           prev_year=prev_year, prev_month=prev_month,
                           next_year=next_year, next_month=next_month,
                           current_year=today.year, current_month=today.month)


@app.route('/saisie', methods=['GET', 'POST'])
@app.route('/saisie/<int:id>', methods=['GET', 'POST'])
@login_required
def saisie(id=None):
    resa = get_reservation(id) if id else None

    if request.method == 'POST':
        data = {
            'nom_client':      request.form.get('nom_client', '').strip().upper(),
            'propriete':       request.form.get('propriete', ''),
            'source':          request.form.get('source', ''),
            'arrivee':         request.form.get('arrivee', ''),
            'depart':          request.form.get('depart', ''),
            'adultes':         int(request.form.get('adultes', 0) or 0),
            'enfants':         int(request.form.get('enfants', 0) or 0),
            'bebes':           int(request.form.get('bebes', 0) or 0),
            'animaux':         int(request.form.get('animaux', 0) or 0),
            'animaux_details': request.form.get('animaux_details', ''),
            'provenance':      request.form.get('provenance', ''),
            'commentaire':     request.form.get('commentaire', ''),
            'prive':           request.form.get('prive') == 'on',
            'statut':          request.form.get('statut', 'Confirmée'),
            'numero_resa':     request.form.get('numero_resa', ''),
            'montant':         request.form.get('montant', '') or None,
        }
        if id:
            update_reservation(id, data)
        else:
            create_reservation(data)

        # Rediriger vers le mois d'arrivée
        arr = data['arrivee']
        if arr:
            y, m, _ = arr.split('-')
            return redirect(url_for('index', year=y, month=int(m)))
        return redirect(url_for('index'))

    return render_template('saisie.html', resa=resa, id=id)


@app.route('/api/code')
@login_required
def api_code():
    adultes = int(request.args.get('adultes', 0) or 0)
    enfants = int(request.args.get('enfants', 0) or 0)
    bebes   = int(request.args.get('bebes', 0) or 0)
    animaux = int(request.args.get('animaux', 0) or 0)
    propriete = request.args.get('propriete', '')
    code = generate_code(adultes, enfants, bebes, animaux, propriete) if propriete else '—'
    return jsonify({'code': code})


@app.route('/liste')
@login_required
def liste():
    propriete = request.args.get('propriete', '')
    source    = request.args.get('source', '')
    statut    = request.args.get('statut', '')
    mois      = request.args.get('mois', '')
    search    = request.args.get('search', '')
    reservations = get_all_reservations(
        propriete=propriete or None,
        source=source or None,
        statut=statut or None,
        mois=mois or None,
        search=search or None
    )
    return render_template('liste.html',
                           reservations=reservations,
                           couleurs=COULEURS,
                           propriete=propriete,
                           source=source,
                           statut=statut,
                           mois=mois,
                           search=search)


@app.route('/api/quick_update/<int:id>', methods=['POST'])
@login_required
def quick_update(id):
    data = request.get_json()
    from database import get_db, generate_code
    conn = get_db()
    row = conn.execute('SELECT * FROM reservations WHERE id=?', (id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'ok': False}), 404
    nom_client = data.get('nom_client', row['nom_client']).strip().upper()
    adultes    = int(data.get('adultes', row['adultes']) or 0)
    enfants    = int(data.get('enfants', row['enfants']) or 0)
    bebes      = int(data.get('bebes',   row['bebes'])   or 0)
    animaux    = int(data.get('animaux', row['animaux']) or 0)
    ville      = data.get('ville', '').strip()
    pays       = data.get('pays', '').strip()
    provenance = f"{ville} · {pays}" if ville and pays else (ville or pays or row['provenance'] or '')
    code = generate_code(adultes, enfants, bebes, animaux, row['propriete'])
    conn.execute('''
        UPDATE reservations SET nom_client=?, adultes=?, enfants=?, bebes=?, animaux=?, code=?, provenance=?
        WHERE id=?
    ''', (nom_client, adultes, enfants, bebes, animaux, code, provenance, id))
    conn.commit()
    conn.close()
    parts = provenance.split(' · ', 1)
    return jsonify({'ok': True, 'nom_client': nom_client, 'code': code,
                    'adultes': adultes, 'enfants': enfants, 'bebes': bebes, 'animaux': animaux,
                    'ville': parts[0] if len(parts) > 0 else '',
                    'pays': parts[1] if len(parts) > 1 else ''})


@app.route('/sync', methods=['POST'])
@login_required
def sync():
    if not validate_csrf():
        return 'Requête invalide', 403
    result = sync_all()
    msg = f"Sync iCal — {result['created']} créée(s), {result['updated']} mise(s) à jour, {result['deleted']} supprimée(s)"
    if result['errors']:
        msg += ' | Erreurs : ' + ' / '.join(result['errors'])
    flash(msg)
    return redirect(request.referrer or url_for('index'))


@app.route('/supprimer/<int:id>', methods=['POST'])
@login_required
def supprimer(id):
    if not validate_csrf():
        return 'Requête invalide', 403
    delete_reservation(id)
    return redirect(request.referrer or url_for('liste'))


@app.route('/export/pdf/<int:annee>/<int:mois>')
@login_required
def export_pdf(annee, mois):
    pdf_path = export_month_pdf(annee, mois)
    return send_file(pdf_path, as_attachment=True,
                     download_name=f'reservations_{annee}_{mois:02d}.pdf',
                     mimetype='application/pdf')


@app.route('/export/pdf/annee/<int:annee>')
@login_required
def export_pdf_annee(annee):
    pdf_path = export_year_pdf(annee)
    return send_file(pdf_path, as_attachment=True,
                     download_name=f'reservations_{annee}.pdf',
                     mimetype='application/pdf')


@app.route('/print/<int:annee>/<int:mois>')
@login_required
def print_mois(annee, mois):
    """Page optimisée impression — Cmd+P pour sauvegarder en PDF."""
    weeks, resa_by_day = build_calendar_data(annee, mois)
    return render_template('print.html',
                           year=annee, month=mois,
                           mois_nom=MOIS_FR[mois],
                           weeks=weeks,
                           resa_by_day=resa_by_day,
                           couleurs=COULEURS,
                           today=date.today)


@app.route('/annee')
@app.route('/annee/<int:year>')
@login_required
def vue_annuelle(year=None):
    """Vue de tous les mois de l'année."""
    today = date.today()
    if year is None:
        year = today.year
    mois_data = []
    for m in range(1, 13):
        weeks, resa_by_day = build_calendar_data(year, m)
        mois_data.append({
            'month': m,
            'nom': MOIS_FR[m],
            'weeks': weeks,
            'resa_by_day': resa_by_day,
        })
    return render_template('annee.html',
                           year=year,
                           mois_data=mois_data,
                           today=today,
                           couleurs=COULEURS,
                           prev_year=year - 1,
                           next_year=year + 1)


if __name__ == '__main__':
    init_db()
    import webbrowser, threading
    def open_browser():
        import time
        time.sleep(1)
        webbrowser.open('http://localhost:5001')
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(debug=False, host='0.0.0.0', port=5001)
