import os
import calendar
from datetime import date, timedelta
from database import get_reservations_for_month

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, Color
from reportlab.pdfgen import canvas as rl_canvas

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), 'exports')

COULEURS_HEX = {
    'Airbnb':  '#FF5A5F',
    'Booking': '#003580',
    'Direct':  '#639922',
    'Privée':  '#888780',
    'Absence': '#2C2C2A',
}

JOURS = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM']

MOIS_FR = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
           'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']


def hex_to_color(h):
    h = h.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return Color(r/255, g/255, b/255)


def truncate_text(c, text, max_width, fontname, fontsize):
    c.setFont(fontname, fontsize)
    while text and c.stringWidth(text, fontname, fontsize) > max_width:
        text = text[:-1]
    return text


def draw_month(c, year, month):
    """Dessine un mois complet sur la page courante du canvas."""
    W, H = landscape(A4)
    MARGIN = 12 * mm
    usable_w = W - 2 * MARGIN
    usable_h = H - 2 * MARGIN

    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)
    reservations = get_reservations_for_month(year, month)

    resa_by_day = {}
    for r in reservations:
        arr = date.fromisoformat(r['arrivee'])
        dep = date.fromisoformat(r['depart'])
        start = max(arr, first_day)
        end = min(dep - timedelta(days=1), last_day)
        d = start
        while d <= end:
            resa_by_day.setdefault(d, []).append(r)
            d += timedelta(days=1)

    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)
    n_weeks = len(weeks)

    TITLE_H  = 20 * mm
    HEADER_H = 7 * mm
    LEGEND_H = 8 * mm
    CELL_H   = (usable_h - TITLE_H - HEADER_H - LEGEND_H) / n_weeks
    CELL_W   = usable_w / 7

    # ── TITRE ──────────────────────────────────────────────
    c.setFillColor(HexColor('#2C2C2A'))
    c.rect(MARGIN, H - MARGIN - TITLE_H, usable_w, TITLE_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(MARGIN + 6*mm, H - MARGIN - TITLE_H + 7*mm,
                 f'RÉSERVATIONS — {MOIS_FR[month].upper()} {year}')
    c.setFont('Helvetica', 8)
    c.drawRightString(W - MARGIN - 4*mm, H - MARGIN - TITLE_H + 7*mm,
                      'Villa Plaisance & Studio Avignon')

    # ── EN-TÊTES JOURS ──────────────────────────────────────
    header_y = H - MARGIN - TITLE_H - HEADER_H
    for i, jour in enumerate(JOURS):
        x = MARGIN + i * CELL_W
        c.setFillColor(HexColor('#3d3d3a') if i >= 5 else HexColor('#2C2C2A'))
        c.rect(x, header_y, CELL_W, HEADER_H, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 8)
        c.drawCentredString(x + CELL_W/2, header_y + 2*mm, jour)

    # ── CELLULES ────────────────────────────────────────────
    for week_idx, week in enumerate(weeks):
        cell_y = H - MARGIN - TITLE_H - HEADER_H - (week_idx + 1) * CELL_H

        for day_idx, day in enumerate(week):
            cell_x = MARGIN + day_idx * CELL_W
            is_current = day.month == month

            if not is_current:
                c.setFillColor(HexColor('#f5f5f5'))
            elif day_idx >= 5:
                c.setFillColor(HexColor('#fafaf8'))
            else:
                c.setFillColor(white)
            c.rect(cell_x, cell_y, CELL_W, CELL_H, fill=1, stroke=0)

            c.setStrokeColor(HexColor('#dddddd'))
            c.setLineWidth(0.3)
            c.rect(cell_x, cell_y, CELL_W, CELL_H, fill=0, stroke=1)

            c.setFillColor(HexColor('#222222') if is_current else HexColor('#bbbbbb'))
            c.setFont('Helvetica-Bold', 8)
            c.drawString(cell_x + 2*mm, cell_y + CELL_H - 4.5*mm, str(day.day))

            if is_current and day in resa_by_day:
                band_h  = min(11, (CELL_H - 6*mm) / max(1, len(resa_by_day[day])))
                band_h  = max(8, band_h)
                padding = 1.5
                text_w  = CELL_W - 4*mm
                band_y  = cell_y + CELL_H - 6*mm

                for r in resa_by_day[day]:
                    if band_y < cell_y + 1:
                        break
                    actual_h = min(band_h, band_y - cell_y)
                    c.setFillColor(hex_to_color(COULEURS_HEX.get(r['source'], '#888780')))
                    c.roundRect(cell_x + padding, band_y - actual_h + 1,
                                CELL_W - 2*padding, actual_h - 1, 1.5, fill=1, stroke=0)
                    c.setFillColor(white)
                    c.setFont('Helvetica-Bold', 6.5)
                    l1 = truncate_text(c, f"{r['code']} · {r['nom_client']}", text_w, 'Helvetica-Bold', 6.5)
                    c.drawString(cell_x + padding + 1, band_y - 4.5, l1)
                    if actual_h > 10:
                        parts = [x for x in [r.get('provenance'), r.get('commentaire')] if x]
                        if parts:
                            c.setFont('Helvetica', 5.5)
                            l2 = truncate_text(c, ' · '.join(parts), text_w, 'Helvetica', 5.5)
                            c.drawString(cell_x + padding + 1, band_y - 9.5, l2)
                    band_y -= band_h

    # ── LÉGENDE ─────────────────────────────────────────────
    leg_y = MARGIN + 1.5*mm
    leg_x = MARGIN
    for src, hexcol in COULEURS_HEX.items():
        c.setFillColor(hex_to_color(hexcol))
        c.roundRect(leg_x, leg_y, 22*mm, 5*mm, 2, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawCentredString(leg_x + 11*mm, leg_y + 1.5*mm, f'● {src}')
        leg_x += 24*mm


def export_month_pdf(year, month, mois_fr=None, couleurs=None):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    pdf_path = os.path.join(EXPORTS_DIR, f'reservations_{year}_{month:02d}.pdf')
    c = rl_canvas.Canvas(pdf_path, pagesize=landscape(A4))
    c.setTitle(f'Réservations — {MOIS_FR[month]} {year}')
    draw_month(c, year, month)
    c.save()
    return pdf_path


def export_year_pdf(year):
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    pdf_path = os.path.join(EXPORTS_DIR, f'reservations_{year}.pdf')
    c = rl_canvas.Canvas(pdf_path, pagesize=landscape(A4))
    c.setTitle(f'Réservations {year} — Villa Plaisance & Studio Avignon')
    for month in range(1, 13):
        draw_month(c, year, month)
        if month < 12:
            c.showPage()
    c.save()
    return pdf_path
