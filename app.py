import datetime
import hashlib
import html
import mimetypes
import os
import re
import secrets
import sqlite3
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse

from database import BASE_DIR, get_connection, init_db

TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

SESSIONS = {}
FLASH_MESSAGES = {}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_DIGITS_RE = re.compile(r"\d")
UNREPLACED_TOKEN_RE = re.compile(r"\{\{[a-zA-Z0-9_]+\}\}")

AVAILABLE_DATES = [
    "26 Nov 2026",
    "27 Nov 2026",
    "30 Nov 2026",
    "01 Dic 2026",
    "02 Dic 2026",
    "04 Dic 2026",
]

AVAILABLE_SLOTS = [
    "09:00 hrs",
    "10:30 hrs",
    "12:00 hrs",
    "15:30 hrs",
    "17:00 hrs",
]


def load_template(name):
    with open(os.path.join(TEMPLATES_DIR, name), "r", encoding="utf-8") as fh:
        return fh.read()


def asset_hash(rel_path):
    full = os.path.join(STATIC_DIR, rel_path)
    try:
        with open(full, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:10]
    except OSError:
        return "0"


def render_template(name, context):
    tpl = load_template(name)
    for key, value in context.items():
        tpl = tpl.replace(f"{{{{{key}}}}}", str(value))
    leftovers = UNREPLACED_TOKEN_RE.findall(tpl)
    if leftovers:
        raise RuntimeError(f"Plantilla '{name}' tiene variables sin resolver: {leftovers}")
    return tpl


def format_clp(amount):
    return "$" + f"{int(amount):,}".replace(",", ".")


def split_date_badge(date_str):
    parts = date_str.split()
    if len(parts) >= 2:
        return parts[0], parts[1].upper()
    return date_str, ""


def record_access_event(patient_id, action, detail, origin):
    conn = get_connection()
    now_str = datetime.datetime.now().strftime("%d %b %Y · %H:%M")
    conn.execute(
        "INSERT INTO access_logs (patient_id, event_time, action, detail, origin) VALUES (?, ?, ?, ?, ?)",
        (patient_id, now_str, action, detail, origin),
    )
    conn.commit()
    conn.close()


def build_doctor_card(doc, delay_idx=0):
    delay_attr = f' data-reveal-delay="{(delay_idx % 4) + 1}"' if delay_idx >= 0 else ""
    if doc["telemedicine"]:
        modality_badge = (
            '<span class="inline-flex items-center gap-1.5 rounded-full bg-pine-950/70 px-3 py-1 '
            'text-[11px] font-semibold tracking-wide text-white backdrop-blur-md border border-white/20">'
            '<span class="h-1.5 w-1.5 rounded-full bg-teal-300"></span>Presencial y Telemedicina</span>'
        )
    else:
        modality_badge = (
            '<span class="inline-flex items-center gap-1.5 rounded-full bg-pine-950/70 px-3 py-1 '
            'text-[11px] font-semibold tracking-wide text-white backdrop-blur-md border border-white/20">'
            '<span class="h-1.5 w-1.5 rounded-full bg-amber-300"></span>Solo Presencial</span>'
        )

    return f"""
    <article data-reveal{delay_attr} class="card-elevated card-interactive group flex flex-col overflow-hidden rounded-2xl">
      <div class="relative aspect-[4/4] overflow-hidden bg-sand-100">
        <img
          src="{html.escape(doc['photo'])}"
          alt="{html.escape(doc['name'])}, especialista en {html.escape(doc['specialty'])}"
          class="h-full w-full object-cover object-top transition duration-500 ease-out group-hover:scale-[1.04]"
          loading="lazy"
        />
        <div class="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-pine-950/45 to-transparent"></div>
        <div class="absolute top-3 left-3">{modality_badge}</div>
        <div class="absolute bottom-3 right-3 inline-flex items-center gap-1 rounded-full bg-white/90 px-2.5 py-1 text-xs font-bold text-slate-900 backdrop-blur-md shadow-xs tabular-nums">
          <svg class="h-3.5 w-3.5 text-amber-500" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
          </svg>
          {html.escape(doc['rating'])}
        </div>
      </div>

      <div class="flex flex-1 flex-col p-5">
        <p class="text-[11px] font-bold uppercase tracking-widest text-teal-700">{html.escape(doc['specialty'])}</p>
        <h3 class="mt-1 font-display text-lg font-bold tracking-tight text-slate-900">{html.escape(doc['name'])}</h3>
        <p class="mt-0.5 text-xs font-medium text-slate-500">{html.escape(doc['subspecialty'])}</p>
        <p class="mt-3 flex-1 text-sm leading-relaxed text-slate-600">{html.escape(doc['bio'])}</p>

        <dl class="mt-4 space-y-2 border-t border-slate-100 pt-3.5 text-xs text-slate-600 tabular-nums">
          <div class="flex items-start gap-2">
            <dt class="sr-only">Horario</dt>
            <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
            <dd>{html.escape(doc['schedule'])}</dd>
          </div>
          <div class="flex items-start gap-2">
            <dt class="sr-only">Ubicación</dt>
            <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
            <dd>{html.escape(doc['location'])}</dd>
          </div>
          <div class="flex items-start gap-2">
            <dt class="sr-only">Experiencia</dt>
            <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-teal-700" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>
            <dd>{doc['experience_years']} años de trayectoria clínica</dd>
          </div>
        </dl>

        <div class="mt-5">
          <a
            href="/agendar?specialist_id={doc['id']}"
            class="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-pine-950 px-4 py-2.5 text-sm font-semibold text-white shadow-xs transition duration-200 hover:bg-teal-800 active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700"
          >
            Agendar hora
            <svg class="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
          </a>
        </div>
      </div>
    </article>
    """


def build_flash_html(flash):
    if not flash:
        return ""
    kind, message = flash
    if kind == "success":
        return (
            '<div data-alert-box role="status" class="animate-toast mb-6 flex items-start justify-between gap-3 rounded-2xl border border-emerald-200/90 '
            'bg-emerald-50 px-4 py-3.5 text-sm text-emerald-950 shadow-xs">'
            '<div class="flex items-start gap-3">'
            '<svg class="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">'
            '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/></svg>'
            f"<span>{html.escape(message)}</span></div>"
            '<button type="button" data-dismiss-alert aria-label="Cerrar notificación" class="rounded-lg p-1 text-emerald-700 hover:bg-emerald-100 cursor-pointer">&times;</button>'
            "</div>"
        )
    return (
        '<div data-alert-box role="alert" class="animate-toast mb-6 flex items-start justify-between gap-3 rounded-2xl border border-red-200/90 '
        'bg-red-50 px-4 py-3.5 text-sm text-red-950 shadow-xs">'
        '<div class="flex items-start gap-3">'
        '<svg class="mt-0.5 h-5 w-5 shrink-0 text-red-600" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">'
        '<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/></svg>'
        f"<span>{html.escape(message)}</span></div>"
        '<button type="button" data-dismiss-alert aria-label="Cerrar alerta" class="rounded-lg p-1 text-red-700 hover:bg-red-100 cursor-pointer">&times;</button>'
        "</div>"
    )


def build_record_row_html(rec, abnormal_count=0):
    rtype = rec["record_type"]
    if rtype == "Imagenología":
        icon_bg = "bg-indigo-50 text-indigo-800"
        icon_svg = '<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="12" cy="12" r="4"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3"/></svg>'
    elif rtype == "Cardiología":
        icon_bg = "bg-rose-50 text-rose-700"
        icon_svg = '<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>'
    else:
        icon_bg = "bg-teal-50 text-teal-800"
        icon_svg = '<svg class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M9 3h6M10 3v6.5L5.2 18.2A2 2 0 006.9 21h10.2a2 2 0 001.7-2.8L14 9.5V3"/></svg>'

    if rec["status"] == "Disponible":
        status_badge = (
            '<span class="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">'
            '<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>Disponible</span>'
        )
    else:
        status_badge = (
            '<span class="inline-flex items-center gap-1.5 rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-[11px] font-semibold text-sky-800">'
            '<span class="h-1.5 w-1.5 rounded-full bg-sky-500"></span>Revisado</span>'
        )

    extra_badges = ""
    if rec["attachment_image"]:
        extra_badges += (
            '<span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">'
            'Imagen adjunta</span>'
        )
    if abnormal_count > 0:
        lbl = f"{abnormal_count} fuera de rango" if abnormal_count > 1 else "1 fuera de rango"
        extra_badges += (
            f'<span class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900">'
            f"{lbl}</span>"
        )

    search_blob = html.escape(f"{rec['title']} {rec['category']} {rec['record_type']} {rec['doctor_name']} {rec['id']}".lower())
    return f"""
    <div class="exam-row flex flex-col gap-3 p-5 transition hover:bg-sand-50/90 sm:flex-row sm:items-center sm:justify-between" data-type="{html.escape(rtype.lower())}" data-search="{search_blob}">
      <div class="flex items-start gap-3.5 min-w-0">
        <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl {icon_bg}">
          {icon_svg}
        </div>
        <div class="min-w-0">
          <div class="flex flex-wrap items-center gap-2">
            <h3 class="text-sm font-bold text-slate-900 leading-snug">{html.escape(rec['title'])}</h3>
            {status_badge}
            {extra_badges}
          </div>
          <div class="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500 tabular-nums">
            <span class="font-medium text-slate-700">{html.escape(rec['doctor_name'])}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{html.escape(rec['category'])}</span>
            <span aria-hidden="true">&middot;</span>
            <span>{html.escape(rec['exam_date'])}</span>
            <span aria-hidden="true">&middot;</span>
            <span>Folio #{rec['id']}</span>
          </div>
        </div>
      </div>
      <div class="shrink-0 sm:pl-4">
        <a href="/paciente/ficha?id={rec['id']}" class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 shadow-2xs transition hover:border-teal-700 hover:bg-teal-50 hover:text-teal-900">
          Ver informe
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
        </a>
      </div>
    </div>
    """


def build_lab_table_html(observations):
    if not observations:
        return ""

    rows_html = ""
    for obs in observations:
        rmin = float(obs["ref_min"])
        rmax = float(obs["ref_max"])
        val = float(obs["value_num"])
        span = max(rmax - rmin, 0.001)
        # Escala visual: la banda normal ocupa entre 22% y 78% de la barra total
        if val < rmin:
            pct = max(5.0, 22.0 - ((rmin - val) / span) * 20.0)
        elif val > rmax:
            pct = min(95.0, 78.0 + ((val - rmax) / span) * 20.0)
        else:
            pct = 22.0 + ((val - rmin) / span) * 56.0

        flag = obs["flag"]
        if flag == "alto":
            flag_badge = '<span class="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-900">&uarr; Sobre rango</span>'
            dot_cls = "bg-amber-600 ring-amber-200"
            val_cls = "text-amber-900 font-bold"
        elif flag == "bajo":
            flag_badge = '<span class="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-900">&darr; Bajo rango</span>'
            dot_cls = "bg-rose-600 ring-rose-200"
            val_cls = "text-rose-900 font-bold"
        else:
            flag_badge = '<span class="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">Normal</span>'
            dot_cls = "bg-teal-700 ring-teal-200"
            val_cls = "text-slate-900 font-bold"

        rows_html += f"""
        <tr class="border-b border-slate-100 last:border-b-0">
          <td class="px-4 py-3.5 text-sm font-medium text-slate-900">{html.escape(obs['analyte'])}</td>
          <td class="whitespace-nowrap px-4 py-3.5 text-sm tabular-nums {val_cls}">
            {html.escape(obs['value_display'])} <span class="text-xs font-normal text-slate-500">{html.escape(obs['unit'])}</span>
          </td>
          <td class="px-4 py-3.5">
            <div class="flex items-center gap-3">
              <div class="relative h-2 w-28 shrink-0 rounded-full bg-slate-200/80 overflow-visible">
                <div class="absolute top-0 bottom-0 left-[22%] right-[22%] rounded-full bg-emerald-200/90"></div>
                <span class="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-3 w-3 rounded-full ring-2 {dot_cls}" style="left:{pct:.1f}%"></span>
              </div>
              <span class="whitespace-nowrap text-xs text-slate-500 tabular-nums">{html.escape(obs['ref_text'])}</span>
            </div>
          </td>
          <td class="whitespace-nowrap px-4 py-3.5 text-right">{flag_badge}</td>
        </tr>
        """

    return f"""
    <section class="mt-7">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 class="text-xs font-bold uppercase tracking-wider text-teal-800">Panel Cuantitativo de Laboratorio</h2>
        <span class="text-xs text-slate-500">Franja verde indica rango de referencia clínico</span>
      </div>
      <div class="overflow-x-auto rounded-xl border border-slate-200">
        <table class="w-full text-left border-collapse">
          <thead>
            <tr class="border-b border-slate-200 bg-sand-50 text-[11px] font-bold uppercase tracking-wider text-slate-500">
              <th class="px-4 py-3">Parámetro</th>
              <th class="px-4 py-3">Resultado</th>
              <th class="px-4 py-3">Rango de Referencia</th>
              <th class="px-4 py-3 text-right">Interpretación</th>
            </tr>
          </thead>
          <tbody class="bg-white">
            {rows_html}
          </tbody>
        </table>
      </div>
    </section>
    """


def build_imaging_viewer_html(row):
    if not row["attachment_image"]:
        return ""
    is_ecg = "exam-ecg" in row["attachment_image"]
    frame_bg = "bg-white p-3" if is_ecg else "bg-black p-4"
    img_cls = "w-full max-h-[380px] object-contain mx-auto rounded-lg"
    viewer_label = "Trazado Electrocardiográfico Adjunto" if is_ecg else "Visor de Imagenología Diagnóstica (DICOM)"
    return f"""
    <section class="mt-7">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 class="text-xs font-bold uppercase tracking-wider text-teal-800">{viewer_label}</h2>
        <button
          type="button"
          data-open-lightbox
          data-lightbox-src="{html.escape(row['attachment_image'])}"
          data-lightbox-title="{html.escape(row['title'])}"
          data-lightbox-meta="{html.escape(row['dicom_meta'])}"
          class="no-print inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-800 transition hover:border-teal-700 hover:bg-teal-50 hover:text-teal-900 cursor-pointer"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
          Ampliar imagen
        </button>
      </div>
      <div class="overflow-hidden rounded-2xl border border-slate-900/15 bg-[#071114] shadow-sm">
        <div class="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 bg-[#0b191d] px-4 py-2.5 text-[11px] font-medium text-teal-200/90 tabular-nums">
          <span>{html.escape(row['dicom_meta'] or 'Estudio Clínico Digital')}</span>
          <span class="text-slate-400">Folio #{row['id']} · {html.escape(row['exam_date'])}</span>
        </div>
        <div class="{frame_bg}">
          <img
            src="{html.escape(row['attachment_image'])}"
            alt="Imagen diagnóstica correspondiente a {html.escape(row['title'])}"
            class="{img_cls} cursor-zoom-in"
            data-open-lightbox
            data-lightbox-src="{html.escape(row['attachment_image'])}"
            data-lightbox-title="{html.escape(row['title'])}"
            data-lightbox-meta="{html.escape(row['dicom_meta'])}"
          />
        </div>
      </div>
    </section>
    """


def build_portal_shell_header(patient, active_tab, counts):
    parts = patient["full_name"].split()
    initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()

    allergies_text = (patient["allergies"] or "").strip()
    allergy_banner = ""
    if allergies_text and not allergies_text.lower().startswith("sin alergias"):
        allergy_banner = (
            '<div class="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-rose-200/90 bg-rose-50 px-3.5 py-2.5 text-xs text-rose-950">'
            '<span class="inline-flex items-center gap-1.5 font-bold text-rose-800">'
            '<svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">'
            '<path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>'
            'Alerta clínica · Alergias:</span>'
            f'<span>{html.escape(allergies_text)}</span>'
            '</div>'
        )

    tabs = [
        ("resumen", "/paciente/panel", "Resumen", None),
        ("resultados", "/paciente/resultados", "Resultados e Imagenología", counts["records"]),
        ("recetas", "/paciente/recetas", "Recetas y Órdenes", counts["active_rx"] + counts["orders"]),
        ("pagos", "/paciente/pagos", "Bonos y Boletas", counts["bills"]),
        ("perfil", "/paciente/perfil", "Mi Perfil y Actividad", None),
    ]

    nav_items = []
    for key, href, label, badge_num in tabs:
        is_act = active_tab == key
        cls = (
            "bg-pine-950 text-white shadow-xs"
            if is_act
            else "text-slate-600 hover:bg-sand-100 hover:text-slate-950"
        )
        badge_html = ""
        if badge_num is not None:
            bcls = "bg-white/20 text-white" if is_act else "bg-sand-200/80 text-slate-700"
            badge_html = f'<span class="ml-1.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold tabular-nums {bcls}">{badge_num}</span>'
        nav_items.append(
            f'<a href="{href}" class="inline-flex items-center rounded-xl px-3.5 py-2 text-xs font-semibold transition {cls}">{label}{badge_html}</a>'
        )

    return f"""
    <section class="border-b border-slate-900/[0.06] bg-white">
      <div class="mx-auto max-w-6xl px-6 py-7">
        <div class="flex flex-wrap items-center justify-between gap-5">
          <div class="flex items-center gap-4">
            <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-pine-950 font-display text-lg font-bold text-white shadow-sm">
              {initials}
            </div>
            <div>
              <p class="text-[11px] font-bold uppercase tracking-widest text-teal-700">Portal de Pacientes</p>
              <h1 class="mt-0.5 font-display text-2xl font-extrabold tracking-tight text-slate-950 sm:text-3xl">{html.escape(patient['full_name'])}</h1>
              <div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs font-medium text-slate-600 tabular-nums">
                <span class="rounded-md bg-sand-100 px-2 py-0.5 text-slate-800">RUT {html.escape(patient['rut'])}</span>
                <span class="rounded-md bg-sand-100 px-2 py-0.5 text-slate-800">{html.escape(patient['insurance'])}</span>
                <span class="rounded-md bg-teal-50 px-2 py-0.5 font-semibold text-teal-900">Grupo {html.escape(patient['blood_type'])}</span>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-2.5">
            <a href="/agendar" class="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-teal-900/15 transition hover:bg-teal-800">
              <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              Agendar nueva hora
            </a>
            <a href="/especialistas" class="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50">
              Directorio médico
            </a>
          </div>
        </div>

        {allergy_banner}

        <nav class="mt-5 flex flex-wrap gap-1.5 border-t border-slate-100 pt-4" aria-label="Navegación del portal privado">
          {''.join(nav_items)}
        </nav>
      </div>
    </section>
    """


class ClinicaHandler(BaseHTTPRequestHandler):
    server_version = "ClinicaMiramar-Web/2.4.1"

    def log_message(self, format_str, *args):
        print(f"[{self.log_date_time_string()}] {self.address_string()} - {format_str % args}")

    def get_session_token(self):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        cookie.load(cookie_header)
        morsel = cookie.get("miramar_session")
        return morsel.value if morsel else None

    def get_current_patient(self):
        token = self.get_session_token()
        if not token:
            return None
        patient_id = SESSIONS.get(token)
        if not patient_id:
            return None
        conn = get_connection()
        patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        conn.close()
        return patient

    def get_portal_counts(self, patient_id):
        conn = get_connection()
        counts = {
            "records": conn.execute("SELECT COUNT(*) FROM medical_records WHERE patient_id = ?", (patient_id,)).fetchone()[0],
            "active_rx": conn.execute("SELECT COUNT(*) FROM prescriptions WHERE patient_id = ? AND status = 'Vigente'", (patient_id,)).fetchone()[0],
            "orders": conn.execute("SELECT COUNT(*) FROM clinical_orders WHERE patient_id = ?", (patient_id,)).fetchone()[0],
            "bills": conn.execute("SELECT COUNT(*) FROM billing_documents WHERE patient_id = ?", (patient_id,)).fetchone()[0],
            "appts": conn.execute("SELECT COUNT(*) FROM appointments WHERE patient_id = ?", (patient_id,)).fetchone()[0],
        }
        conn.close()
        return counts

    def set_flash(self, kind, message):
        token = self.get_session_token()
        if token:
            FLASH_MESSAGES[token] = (kind, message)

    def pop_flash(self):
        token = self.get_session_token()
        if token and token in FLASH_MESSAGES:
            return FLASH_MESSAGES.pop(token)
        return None

    def client_origin_label(self):
        return f"{self.address_string()} · Navegador Web"

    def build_nav_auth(self, patient, active_nav=""):
        if patient:
            parts = patient["full_name"].split()
            initials = (parts[0][0] + (parts[1][0] if len(parts) > 1 else "")).upper()
            first_name = html.escape(parts[0])
            panel_cls = (
                "border-teal-700 bg-teal-50 text-teal-900 ring-2 ring-teal-700/15"
                if active_nav == "portal"
                else "border-slate-200 bg-white text-slate-800 hover:border-teal-700 hover:text-teal-900"
            )
            return (
                f'<a href="/paciente/panel" class="inline-flex items-center gap-2 rounded-full border pl-1.5 pr-3.5 py-1 text-sm font-semibold shadow-2xs transition {panel_cls}">'
                f'<span class="inline-flex h-7 w-7 items-center justify-center rounded-full bg-pine-950 text-xs font-bold text-white">{initials}</span>'
                f"<span>{first_name}</span></a>"
                '<form action="/logout" method="post" class="inline">'
                '<button type="submit" class="inline-flex items-center rounded-xl px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-900/5 hover:text-slate-950 cursor-pointer">'
                "Salir</button></form>"
            )
        return (
            '<a href="/login" class="inline-flex items-center gap-2 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-teal-900/15 transition duration-200 hover:bg-teal-800 active:scale-[0.99] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal-700">'
            '<svg class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>'
            "Portal de Pacientes</a>"
        )

    def build_mobile_auth(self, patient):
        if patient:
            name = html.escape(patient["full_name"])
            return (
                f'<a href="/paciente/panel" class="block rounded-xl bg-teal-50 px-4 py-3 text-sm font-semibold text-teal-900">Mi Panel ({name})</a>'
                '<form action="/logout" method="post" class="mt-2">'
                '<button type="submit" class="w-full rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 cursor-pointer">Cerrar sesión</button></form>'
            )
        return '<a href="/login" class="block rounded-xl bg-teal-700 px-4 py-3 text-center text-sm font-semibold text-white">Ingresar al Portal de Pacientes</a>'

    def render_page(self, page_title, body_html, active_nav="", status=200, extra_headers=None):
        patient = self.get_current_patient()
        nav_base = "text-sm font-medium transition px-3 py-1.5 rounded-lg"
        nav_active = f"{nav_base} bg-teal-50 text-teal-900 font-semibold"
        nav_idle = f"{nav_base} text-slate-600 hover:bg-slate-900/[0.04] hover:text-slate-950"

        full_html = render_template(
            "base.html",
            {
                "page_title": html.escape(page_title),
                "css_ver": asset_hash("css/tailwind.css"),
                "js_ver": asset_hash("js/ui.js"),
                "nav_home": nav_active if active_nav == "home" else nav_idle,
                "nav_specialists": nav_active if active_nav == "specialists" else nav_idle,
                "nav_booking": nav_active if active_nav == "booking" else nav_idle,
                "nav_auth_buttons": self.build_nav_auth(patient, active_nav),
                "mobile_auth_buttons": self.build_mobile_auth(patient),
                "content": body_html,
            },
        )
        encoded = full_html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()

    def serve_static(self, url_path):
        rel_path = url_path[len("/static/"):].lstrip("/")
        safe_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
        if not safe_path.startswith(os.path.abspath(STATIC_DIR)) or not os.path.isfile(safe_path):
            self.send_error(404, "Recurso no encontrado")
            return
        mime_type, _ = mimetypes.guess_type(safe_path)
        if safe_path.endswith(".woff2"):
            mime_type = "font/woff2"
        elif safe_path.endswith(".js"):
            mime_type = "application/javascript; charset=utf-8"
        with open(safe_path, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        if safe_path.endswith((".css", ".js")):
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path.startswith("/static/"):
            self.serve_static(path)
            return

        if path == "/":
            self.handle_home()
        elif path == "/especialistas":
            self.handle_specialists(params)
        elif path == "/agendar":
            self.handle_booking_get(params)
        elif path == "/login":
            self.handle_login_get(next_url=params.get("next", [""])[0])
        elif path == "/logout":
            self.redirect("/paciente/panel" if self.get_current_patient() else "/")
        elif path == "/paciente/panel":
            self.handle_dashboard()
        elif path == "/paciente/resultados":
            self.handle_results_list(params)
        elif path == "/paciente/ficha":
            self.handle_record(params)
        elif path == "/paciente/recetas":
            self.handle_prescriptions_list()
        elif path == "/paciente/receta":
            self.handle_prescription_detail(params)
        elif path == "/paciente/pagos":
            self.handle_billing()
        elif path == "/paciente/perfil":
            self.handle_profile_get()
        elif path == "/robots.txt":
            self.handle_robots()
        elif path == "/internal/status":
            self.handle_status()
        else:
            body = """
            <section class="py-20">
              <div class="mx-auto max-w-lg px-6 text-center">
                <div class="card-elevated rounded-3xl p-10">
                  <p class="text-xs font-bold uppercase tracking-widest text-teal-700">Error 404</p>
                  <h1 class="mt-2 font-display text-2xl font-bold text-slate-900">No encontramos esta página</h1>
                  <p class="mt-3 text-sm leading-relaxed text-slate-600">
                    La dirección solicitada no existe o fue movida dentro del portal de Clínica Miramar.
                  </p>
                  <div class="mt-7 flex flex-wrap justify-center gap-3">
                    <a href="/" class="rounded-xl bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800">Ir al inicio</a>
                    <a href="/especialistas" class="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Buscar especialista</a>
                    <a href="/login" class="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Portal de Pacientes</a>
                  </div>
                </div>
              </div>
            </section>
            """
            self.render_page("Página no encontrada", body, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8", errors="replace")
        form = parse_qs(raw_body)

        if path == "/login":
            self.handle_login_post(form)
        elif path == "/logout":
            self.handle_logout_post()
        elif path == "/paciente/perfil":
            self.handle_profile_update(form)
        elif path == "/agendar":
            self.handle_booking_post(form)
        elif path == "/paciente/citas/cancelar":
            self.handle_cancel_appointment(form)
        else:
            self.send_error(404, "Endpoint no encontrado")

    def handle_home(self):
        conn = get_connection()
        doctors = conn.execute("SELECT * FROM specialists ORDER BY id ASC").fetchall()
        specialties = [
            row["specialty"]
            for row in conn.execute("SELECT DISTINCT specialty FROM specialists ORDER BY specialty").fetchall()
        ]
        conn.close()

        cards_html = "".join(build_doctor_card(d, idx) for idx, d in enumerate(doctors))
        quick_chips = "".join(
            f'<a href="/especialistas?esp={quote(esp)}" '
            f'class="rounded-full border border-slate-900/10 bg-white/85 px-3.5 py-1.5 text-xs font-semibold text-slate-700 backdrop-blur-md shadow-2xs transition hover:-translate-y-0.5 hover:border-teal-700/40 hover:bg-teal-50 hover:text-teal-900">'
            f"{html.escape(esp)}</a>"
            for esp in specialties
        )
        datalist_opts = "".join(
            f'<option value="{html.escape(esp)}"></option>' for esp in specialties
        ) + "".join(
            f'<option value="{html.escape(d["name"])}"></option>' for d in doctors
        )

        body = render_template(
            "index.html",
            {
                "featured_doctors": cards_html,
                "quick_specialty_chips": quick_chips,
                "search_datalist_options": datalist_opts,
            },
        )
        self.render_page("Inicio", body, active_nav="home")

    def handle_specialists(self, params):
        query = params.get("q", [""])[0].strip()
        selected_esp = params.get("esp", [""])[0].strip()
        modality = params.get("modalidad", ["todas"])[0].strip().lower()
        if modality not in ("todas", "telemedicina", "presencial"):
            modality = "todas"

        conn = get_connection()
        total_doctors = conn.execute("SELECT COUNT(*) FROM specialists").fetchone()[0]
        all_esps = [
            row["specialty"]
            for row in conn.execute("SELECT DISTINCT specialty FROM specialists ORDER BY specialty").fetchall()
        ]

        clauses = []
        args = []
        if selected_esp:
            clauses.append("specialty = ?")
            args.append(selected_esp)
        if query:
            like_q = f"%{query}%"
            clauses.append("(name LIKE ? OR specialty LIKE ? OR subspecialty LIKE ? OR bio LIKE ?)")
            args.extend([like_q, like_q, like_q, like_q])
        if modality == "telemedicina":
            clauses.append("telemedicine = 1")
        elif modality == "presencial":
            clauses.append("telemedicine = 0")

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        doctors = conn.execute(
            f"SELECT * FROM specialists {where_sql} ORDER BY id ASC",
            tuple(args),
        ).fetchall()
        conn.close()

        def filter_url(new_q=query, new_esp=selected_esp, new_mod=modality):
            p = {}
            if new_q:
                p["q"] = new_q
            if new_esp:
                p["esp"] = new_esp
            if new_mod and new_mod != "todas":
                p["modalidad"] = new_mod
            return "/especialistas" + (f"?{urlencode(p)}" if p else "")

        chips = [
            f'<a href="{filter_url(new_esp="")}" class="rounded-full px-3.5 py-1.5 text-xs font-semibold transition '
            f'{"bg-pine-950 text-white shadow-xs" if not selected_esp else "bg-sand-100 text-slate-700 hover:bg-sand-200"}">'
            f"Todas las especialidades</a>"
        ]
        for esp in all_esps:
            is_act = selected_esp == esp
            cls = "bg-pine-950 text-white shadow-xs" if is_act else "bg-sand-100 text-slate-700 hover:bg-sand-200"
            chips.append(
                f'<a href="{filter_url(new_esp=esp)}" class="rounded-full px-3.5 py-1.5 text-xs font-semibold transition {cls}">'
                f"{html.escape(esp)}</a>"
            )

        mod_options = [
            ("todas", "Todas las modalidades"),
            ("telemedicina", "Con Telemedicina"),
            ("presencial", "Solo Presencial"),
        ]
        mod_chips = []
        for mod_key, mod_label in mod_options:
            is_act = modality == mod_key
            cls = (
                "border-teal-700 bg-teal-50 text-teal-900"
                if is_act
                else "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
            )
            mod_chips.append(
                f'<a href="{filter_url(new_mod=mod_key)}" class="rounded-xl border px-3 py-1.5 text-xs font-semibold transition {cls}">'
                f"{mod_label}</a>"
            )

        active_pills = []
        if query:
            active_pills.append(
                f'<a href="{filter_url(new_q="")}" class="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-semibold text-teal-900 hover:bg-teal-100">'
                f'Búsqueda: "{html.escape(query)}" <span aria-hidden="true">&times;</span></a>'
            )
        if selected_esp:
            active_pills.append(
                f'<a href="{filter_url(new_esp="")}" class="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-semibold text-teal-900 hover:bg-teal-100">'
                f'Especialidad: {html.escape(selected_esp)} <span aria-hidden="true">&times;</span></a>'
            )
        if modality != "todas":
            lbl = "Con Telemedicina" if modality == "telemedicina" else "Solo Presencial"
            active_pills.append(
                f'<a href="{filter_url(new_mod="todas")}" class="inline-flex items-center gap-1.5 rounded-full bg-teal-50 border border-teal-200 px-3 py-1 text-xs font-semibold text-teal-900 hover:bg-teal-100">'
                f'Modalidad: {lbl} <span aria-hidden="true">&times;</span></a>'
            )

        active_filters_html = ""
        if active_pills:
            active_filters_html = (
                '<div class="mb-6 flex flex-wrap items-center gap-2">'
                '<span class="text-xs font-semibold text-slate-500">Filtros activos:</span>'
                + "".join(active_pills)
                + '<a href="/especialistas" class="ml-2 text-xs font-semibold text-slate-500 underline hover:text-slate-900">Limpiar todo</a>'
                + "</div>"
            )

        if doctors:
            cards_html = "".join(build_doctor_card(d, idx) for idx, d in enumerate(doctors))
        else:
            cards_html = (
                '<div class="col-span-full card-elevated rounded-2xl p-12 text-center">'
                '<h3 class="font-display text-lg font-bold text-slate-900">Sin resultados para esta combinación de filtros</h3>'
                '<p class="mt-2 text-sm text-slate-600">Prueba quitando un filtro o buscando por Cardiología, Pediatría, Medicina Interna o Neurología.</p>'
                '<a href="/especialistas" class="mt-5 inline-flex items-center rounded-xl bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800">Mostrar todos los especialistas</a>'
                "</div>"
            )

        body = render_template(
            "specialists.html",
            {
                "query_value": html.escape(query),
                "hidden_esp": f'<input type="hidden" name="esp" value="{html.escape(selected_esp)}" />' if selected_esp else "",
                "hidden_mod": f'<input type="hidden" name="modalidad" value="{html.escape(modality)}" />' if modality != "todas" else "",
                "specialty_chips": "".join(chips),
                "modality_chips": "".join(mod_chips),
                "active_filters": active_filters_html,
                "results_count": f"Mostrando {len(doctors)} de {total_doctors} especialistas acreditados",
                "doctors_cards": cards_html,
            },
        )
        self.render_page("Directorio de Especialistas", body, active_nav="specialists")

    def handle_booking_get(self, params):
        patient = self.get_current_patient()
        spec_id_raw = params.get("specialist_id", [""])[0].strip()

        if not patient:
            next_target = "/agendar" + (f"?specialist_id={spec_id_raw}" if spec_id_raw.isdigit() else "")
            self.redirect(f"/login?next={quote(next_target)}")
            return

        conn = get_connection()
        all_specs = conn.execute("SELECT * FROM specialists ORDER BY id ASC").fetchall()
        selected = None
        if spec_id_raw.isdigit():
            selected = conn.execute("SELECT * FROM specialists WHERE id = ?", (int(spec_id_raw),)).fetchone()
        if not selected and all_specs:
            selected = all_specs[0]
        conn.close()

        spec_options = "".join(
            f'<option value="{s["id"]}" {"selected" if s["id"] == selected["id"] else ""}>'
            f'{html.escape(s["name"])} — {html.escape(s["specialty"])}</option>'
            for s in all_specs
        )
        date_options = "".join(f'<option value="{d}">{d}</option>' for d in AVAILABLE_DATES)
        slot_radios = "".join(
            f'<label class="cursor-pointer">'
            f'<input type="radio" name="appt_time" value="{slot}" {"checked" if idx == 0 else ""} class="peer sr-only" />'
            f'<span class="block rounded-xl border border-slate-300 bg-white px-3 py-2.5 text-center text-sm font-semibold text-slate-700 tabular-nums transition peer-checked:border-teal-700 peer-checked:bg-teal-50 peer-checked:text-teal-900 peer-checked:ring-2 peer-checked:ring-teal-700/15 hover:border-teal-600">'
            f"{slot}</span></label>"
            for idx, slot in enumerate(AVAILABLE_SLOTS)
        )

        if selected["telemedicine"]:
            modality_radios = (
                '<label class="cursor-pointer flex-1">'
                '<input type="radio" name="modality" value="Presencial" checked class="peer sr-only" />'
                '<span class="block rounded-xl border border-slate-300 bg-white p-4 text-sm transition peer-checked:border-teal-700 peer-checked:bg-teal-50 peer-checked:ring-2 peer-checked:ring-teal-700/15">'
                '<strong class="block text-slate-900">Presencial</strong>'
                f'<span class="mt-0.5 block text-xs text-slate-500">{html.escape(selected["location"])}</span></span></label>'
                '<label class="cursor-pointer flex-1">'
                '<input type="radio" name="modality" value="Telemedicina" class="peer sr-only" />'
                '<span class="block rounded-xl border border-slate-300 bg-white p-4 text-sm transition peer-checked:border-teal-700 peer-checked:bg-teal-50 peer-checked:ring-2 peer-checked:ring-teal-700/15">'
                '<strong class="block text-slate-900">Telemedicina HD</strong>'
                '<span class="mt-0.5 block text-xs text-slate-500">Videoconsulta desde tu Portal</span></span></label>'
            )
        else:
            modality_radios = (
                '<label class="cursor-pointer flex-1">'
                '<input type="radio" name="modality" value="Presencial" checked class="peer sr-only" />'
                '<span class="block rounded-xl border border-teal-700 bg-teal-50 p-4 text-sm ring-2 ring-teal-700/15">'
                '<strong class="block text-slate-900">Presencial (única modalidad)</strong>'
                f'<span class="mt-0.5 block text-xs text-slate-600">{html.escape(selected["location"])} · Requiere examen físico neurológico</span></span></label>'
            )

        body = render_template(
            "booking.html",
            {
                "flash_banner": build_flash_html(self.pop_flash()),
                "patient_name": html.escape(patient["full_name"]),
                "spec_photo": html.escape(selected["photo"]),
                "spec_name": html.escape(selected["name"]),
                "spec_specialty": html.escape(selected["specialty"]),
                "spec_subspecialty": html.escape(selected["subspecialty"]),
                "spec_schedule": html.escape(selected["schedule"]),
                "spec_location": html.escape(selected["location"]),
                "specialist_options": spec_options,
                "date_options": date_options,
                "slot_radios": slot_radios,
                "modality_radios": modality_radios,
            },
        )
        self.render_page("Agendar Hora Médica", body, active_nav="booking")

    def handle_booking_post(self, form):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        spec_id = form.get("specialist_id", [""])[0].strip()
        appt_date = form.get("appt_date", [""])[0].strip()
        appt_time = form.get("appt_time", [""])[0].strip()
        modality = form.get("modality", ["Presencial"])[0].strip()

        if not spec_id.isdigit() or appt_date not in AVAILABLE_DATES or appt_time not in AVAILABLE_SLOTS:
            self.set_flash("error", "Selecciona un especialista, fecha y horario válidos antes de confirmar.")
            self.redirect("/agendar")
            return

        conn = get_connection()
        spec = conn.execute("SELECT * FROM specialists WHERE id = ?", (int(spec_id),)).fetchone()
        if not spec:
            conn.close()
            self.set_flash("error", "El especialista seleccionado no existe.")
            self.redirect("/agendar")
            return

        if modality == "Telemedicina" and not spec["telemedicine"]:
            modality = "Presencial"

        location = "Sala Virtual · Portal de Pacientes" if modality == "Telemedicina" else spec["location"]
        prep_note = (
            "Conéctate 5 minutos antes desde un lugar tranquilo con cámara y micrófono activos."
            if modality == "Telemedicina"
            else "Presentarse 15 minutos antes con cédula de identidad y exámenes previos."
        )

        conn.execute(
            """
            INSERT INTO appointments (
                patient_id, specialist_name, specialty, appt_date, appt_time,
                modality, location, prep_note, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                patient["id"],
                spec["name"],
                spec["specialty"],
                appt_date,
                appt_time,
                modality,
                location,
                prep_note,
                "Confirmada",
            ),
        )
        conn.commit()
        conn.close()

        record_access_event(
            patient["id"],
            "Reserva de hora",
            f"Cita agendada con {spec['name']} ({appt_date} · {appt_time})",
            self.client_origin_label(),
        )
        self.set_flash(
            "success",
            f"Hora confirmada con {spec['name']} ({spec['specialty']}) para el {appt_date} a las {appt_time} ({modality}).",
        )
        self.redirect("/paciente/panel#citas")

    def handle_cancel_appointment(self, form):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        appt_id = form.get("appointment_id", [""])[0].strip()
        if not appt_id.isdigit():
            self.set_flash("error", "No se pudo identificar la cita a cancelar.")
            self.redirect("/paciente/panel#citas")
            return

        conn = get_connection()
        appt = conn.execute(
            "SELECT * FROM appointments WHERE id = ? AND patient_id = ?",
            (int(appt_id), patient["id"]),
        ).fetchone()
        if not appt:
            conn.close()
            self.set_flash("error", "La cita indicada no existe o no pertenece a tu cuenta.")
            self.redirect("/paciente/panel#citas")
            return

        conn.execute("DELETE FROM appointments WHERE id = ? AND patient_id = ?", (int(appt_id), patient["id"]))
        conn.commit()
        conn.close()

        record_access_event(
            patient["id"],
            "Cancelación de cita",
            f"Cita cancelada con {appt['specialist_name']} ({appt['appt_date']})",
            self.client_origin_label(),
        )
        self.set_flash(
            "success",
            f"Se canceló tu cita con {appt['specialist_name']} del {appt['appt_date']} ({appt['appt_time']}).",
        )
        self.redirect("/paciente/panel#citas")

    def handle_login_get(self, error_msg="", email_val="", next_url=""):
        if self.get_current_patient():
            self.redirect("/paciente/panel")
            return
        safe_next = next_url if next_url.startswith("/") and not next_url.startswith("//") else ""
        error_banner = build_flash_html(("error", error_msg)) if error_msg else ""
        input_err_cls = (
            "border-red-400 focus:border-red-500 focus:ring-red-500/20"
            if error_msg
            else "border-slate-300 focus:border-teal-700 focus:ring-teal-700/15"
        )
        aria_inv = 'aria-invalid="true"' if error_msg else ""

        body = render_template(
            "login.html",
            {
                "error_banner": error_banner,
                "email_value": html.escape(email_val),
                "next_value": html.escape(safe_next),
                "input_state_class": input_err_cls,
                "aria_invalid": aria_inv,
            },
        )
        self.render_page("Portal de Pacientes", body)

    def handle_login_post(self, form):
        email = form.get("email", [""])[0].strip().lower()
        password = form.get("password", [""])[0]
        next_url = form.get("next", [""])[0].strip()

        if not EMAIL_RE.match(email) or not password:
            self.handle_login_get(
                error_msg="Ingresa un correo electrónico válido y tu contraseña para continuar.",
                email_val=email,
                next_url=next_url,
            )
            return

        conn = get_connection()
        patient = conn.execute(
            "SELECT * FROM patients WHERE lower(email) = ? AND password = ?",
            (email, password),
        ).fetchone()
        conn.close()

        if not patient:
            self.handle_login_get(
                error_msg="Las credenciales no coinciden con ninguna cuenta registrada. Verifica tu correo y contraseña.",
                email_val=email,
                next_url=next_url,
            )
            return

        token = secrets.token_hex(24)
        SESSIONS[token] = patient["id"]
        record_access_event(
            patient["id"],
            "Inicio de sesión",
            "Acceso exitoso al Portal de Pacientes",
            self.client_origin_label(),
        )
        target = next_url if next_url.startswith("/") and not next_url.startswith("//") else "/paciente/panel"
        self.redirect(
            target,
            extra_headers=[("Set-Cookie", f"miramar_session={token}; Path=/")],
        )

    def handle_logout_post(self):
        token = self.get_session_token()
        if token:
            SESSIONS.pop(token, None)
            FLASH_MESSAGES.pop(token, None)
        self.redirect(
            "/",
            extra_headers=[("Set-Cookie", "miramar_session=; Path=/; Max-Age=0")],
        )

    def _get_abnormal_map(self, conn, record_ids):
        if not record_ids:
            return {}
        placeholders = ",".join("?" for _ in record_ids)
        rows = conn.execute(
            f"SELECT record_id, COUNT(*) AS cnt FROM lab_observations WHERE record_id IN ({placeholders}) AND flag != 'normal' GROUP BY record_id",
            tuple(record_ids),
        ).fetchall()
        return {r["record_id"]: r["cnt"] for r in rows}

    def handle_dashboard(self):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        counts = self.get_portal_counts(patient["id"])
        conn = get_connection()
        records = conn.execute(
            "SELECT * FROM medical_records WHERE patient_id = ? ORDER BY id DESC LIMIT 3",
            (patient["id"],),
        ).fetchall()
        abnormal_map = self._get_abnormal_map(conn, [r["id"] for r in records])
        appointments = conn.execute(
            "SELECT * FROM appointments WHERE patient_id = ? ORDER BY id DESC",
            (patient["id"],),
        ).fetchall()
        active_rx = conn.execute(
            "SELECT * FROM prescriptions WHERE patient_id = ? AND status = 'Vigente' ORDER BY id ASC LIMIT 3",
            (patient["id"],),
        ).fetchall()
        copay_sum = conn.execute(
            "SELECT COALESCE(SUM(copay_amount), 0) FROM billing_documents WHERE patient_id = ?",
            (patient["id"],),
        ).fetchone()[0]
        conn.close()

        next_appt_summary = (
            f"{appointments[0]['appt_date']} · {appointments[0]['appt_time']}"
            if appointments
            else "Sin citas activas"
        )
        next_appt_doctor = (
            f"{appointments[0]['specialist_name']} ({appointments[0]['specialty']})"
            if appointments
            else "Puedes reservar en 1 clic"
        )

        records_rows = "".join(build_record_row_html(r, abnormal_map.get(r["id"], 0)) for r in records)
        if not records_rows:
            records_rows = '<div class="px-5 py-10 text-center text-sm text-slate-500">Aún no registras resultados de exámenes.</div>'

        rx_preview = ""
        for rx in active_rx:
            rx_preview += f"""
            <div class="flex items-start justify-between gap-3 rounded-xl border border-slate-200/80 bg-sand-50/70 p-3.5">
              <div class="min-w-0">
                <div class="text-sm font-bold text-slate-900">{html.escape(rx['medication'])}</div>
                <div class="mt-0.5 text-xs text-slate-600">{html.escape(rx['dosage'])} · {html.escape(rx['schedule'])}</div>
                <div class="mt-1 text-[11px] text-slate-500">{html.escape(rx['doctor_name'])} · Vigente hasta {html.escape(rx['valid_until'])}</div>
              </div>
              <a href="/paciente/receta?id={rx['id']}" class="shrink-0 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:border-teal-700 hover:text-teal-900">
                Receta
              </a>
            </div>
            """
        if not rx_preview:
            rx_preview = '<p class="text-sm text-slate-500">No registras medicación activa.</p>'

        appt_html = ""
        for ap in appointments:
            is_tele = "Telemedicina" in ap["modality"]
            day_num, month_abbr = split_date_badge(ap["appt_date"])
            mod_badge = (
                '<span class="inline-flex items-center rounded-full bg-teal-50 border border-teal-200 px-2.5 py-0.5 text-[11px] font-semibold text-teal-800">Telemedicina</span>'
                if is_tele
                else '<span class="inline-flex items-center rounded-full bg-sand-100 border border-sand-200 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">Presencial</span>'
            )
            appt_html += f"""
            <div class="rounded-2xl border border-slate-200/80 bg-sand-50/70 p-4 transition hover:border-teal-700/30 hover:bg-white">
              <div class="flex items-start gap-3.5">
                <div class="flex h-13 w-13 shrink-0 flex-col items-center justify-center rounded-xl bg-pine-950 text-white tabular-nums">
                  <span class="font-display text-lg font-bold leading-none">{html.escape(day_num)}</span>
                  <span class="mt-0.5 text-[10px] font-semibold tracking-wider text-teal-300">{html.escape(month_abbr)}</span>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="flex items-start justify-between gap-2">
                    <div>
                      <div class="text-sm font-bold text-slate-900">{html.escape(ap['specialist_name'])}</div>
                      <div class="text-xs font-medium text-teal-700">{html.escape(ap['specialty'])}</div>
                    </div>
                    {mod_badge}
                  </div>
                  <div class="mt-2 space-y-1 text-xs text-slate-600 tabular-nums">
                    <div><strong>Hora:</strong> {html.escape(ap['appt_time'])} · {html.escape(ap['location'])}</div>
                    <p class="text-slate-500 leading-relaxed">{html.escape(ap['prep_note'])}</p>
                  </div>
                </div>
              </div>
              <div class="mt-3.5 flex items-center justify-between border-t border-slate-200/70 pt-3">
                <span class="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700">
                  <span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>{html.escape(ap['status'])}
                </span>
                <button
                  type="button"
                  data-open-cancel
                  data-appt-id="{ap['id']}"
                  data-appt-doctor="{html.escape(ap['specialist_name'])} ({html.escape(ap['specialty'])})"
                  data-appt-slot="{html.escape(ap['appt_date'])} · {html.escape(ap['appt_time'])}"
                  class="rounded-lg px-2.5 py-1 text-xs font-semibold text-red-700 transition hover:bg-red-50 hover:text-red-900 cursor-pointer"
                >
                  Cancelar cita
                </button>
              </div>
            </div>
            """
        if not appt_html:
            appt_html = (
                '<div class="rounded-2xl border border-dashed border-slate-300 bg-sand-50/60 p-7 text-center">'
                '<p class="text-sm font-medium text-slate-600">No tienes citas próximas agendadas.</p>'
                '<a href="/agendar" class="mt-3.5 inline-flex items-center rounded-xl bg-teal-700 px-4 py-2 text-xs font-semibold text-white hover:bg-teal-800">Agendar una hora</a>'
                "</div>"
            )

        body = render_template(
            "dashboard.html",
            {
                "portal_header": build_portal_shell_header(patient, "resumen", counts),
                "flash_banner": build_flash_html(self.pop_flash()),
                "records_count": counts["records"],
                "active_rx_count": counts["active_rx"],
                "appointments_count": counts["appts"],
                "next_appt_summary": html.escape(next_appt_summary),
                "next_appt_doctor": html.escape(next_appt_doctor),
                "copay_total": format_clp(copay_sum),
                "bills_count": counts["bills"],
                "chronic_conditions": html.escape(patient["chronic_conditions"]),
                "records_rows": records_rows,
                "rx_preview_list": rx_preview,
                "appointments_list": appt_html,
            },
        )
        self.render_page("Resumen Clínico", body, active_nav="portal")

    def handle_results_list(self, params):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        counts = self.get_portal_counts(patient["id"])
        conn = get_connection()
        records = conn.execute(
            "SELECT * FROM medical_records WHERE patient_id = ? ORDER BY id DESC",
            (patient["id"],),
        ).fetchall()
        abnormal_map = self._get_abnormal_map(conn, [r["id"] for r in records])
        conn.close()

        rows_html = "".join(build_record_row_html(r, abnormal_map.get(r["id"], 0)) for r in records)
        if not rows_html:
            rows_html = '<div class="px-5 py-12 text-center text-sm text-slate-500">No existen resultados registrados para esta cuenta.</div>'

        body = render_template(
            "results.html",
            {
                "portal_header": build_portal_shell_header(patient, "resultados", counts),
                "records_count": len(records),
                "records_rows": rows_html,
            },
        )
        self.render_page("Resultados e Imagenología", body, active_nav="portal")

    def handle_record(self, params):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        rec_id_str = params.get("id", [""])[0].strip()
        if not rec_id_str.isdigit():
            self.redirect("/paciente/resultados")
            return

        conn = get_connection()
        row = conn.execute(
            """
            SELECT r.*, p.full_name, p.rut, p.birth_date, p.insurance, p.blood_type, p.allergies
            FROM medical_records r
            JOIN patients p ON p.id = r.patient_id
            WHERE r.id = ? AND r.patient_id = ?
            """,
            (int(rec_id_str), patient["id"]),
        ).fetchone()

        if not row:
            conn.close()
            active_user = html.escape(patient["email"])
            body = f"""
            <section class="py-16">
              <div class="mx-auto max-w-lg px-6 text-center">
                <div class="card-elevated rounded-3xl p-10">
                  <p class="text-xs font-bold uppercase tracking-widest text-red-700">Acceso restringido (403)</p>
                  <h1 class="mt-2 font-display text-2xl font-bold text-slate-900">Resultado no disponible</h1>
                  <p class="mt-3 text-sm leading-relaxed text-slate-600">
                    El folio solicitado no existe o no pertenece a la sesión activa (<strong>{active_user}</strong>).
                  </p>
                  <div class="mt-7 flex justify-center gap-3">
                    <a href="/paciente/resultados" class="rounded-xl bg-teal-700 px-5 py-2.5 text-sm font-semibold text-white hover:bg-teal-800">Ver mis resultados</a>
                    <a href="/paciente/panel" class="rounded-xl border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50">Volver al resumen</a>
                  </div>
                </div>
              </div>
            </section>
            """
            self.render_page("Acceso restringido", body, active_nav="portal", status=403)
            return

        observations = conn.execute(
            "SELECT * FROM lab_observations WHERE record_id = ? ORDER BY id ASC",
            (row["id"],),
        ).fetchall()
        conn.close()

        body = render_template(
            "record.html",
            {
                "record_id": row["id"],
                "record_title": html.escape(row["title"]),
                "record_category": html.escape(row["category"]),
                "record_status": html.escape(row["status"]),
                "record_date": html.escape(row["exam_date"]),
                "record_doctor": html.escape(row["doctor_name"]),
                "record_findings": html.escape(row["findings"]),
                "record_recommendations": html.escape(row["recommendations"]),
                "owner_name": html.escape(row["full_name"]),
                "owner_rut": html.escape(row["rut"]),
                "owner_birth": html.escape(row["birth_date"]),
                "owner_insurance": html.escape(row["insurance"]),
                "owner_blood": html.escape(row["blood_type"]),
                "owner_allergies": html.escape(row["allergies"]),
                "lab_observations_section": build_lab_table_html(observations),
                "imaging_viewer_section": build_imaging_viewer_html(row),
            },
        )
        self.render_page(f"Resultado #{row['id']}", body, active_nav="portal")

    def handle_prescriptions_list(self):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        counts = self.get_portal_counts(patient["id"])
        conn = get_connection()
        prescriptions = conn.execute(
            "SELECT * FROM prescriptions WHERE patient_id = ? ORDER BY CASE WHEN status='Vigente' THEN 0 ELSE 1 END, id DESC",
            (patient["id"],),
        ).fetchall()
        orders = conn.execute(
            "SELECT * FROM clinical_orders WHERE patient_id = ? ORDER BY id ASC",
            (patient["id"],),
        ).fetchall()
        conn.close()

        rx_cards = ""
        for rx in prescriptions:
            is_active = rx["status"] == "Vigente"
            st_badge = (
                '<span class="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800"><span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>Vigente</span>'
                if is_active
                else '<span class="inline-flex items-center rounded-full border border-slate-200 bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-600">Finalizada</span>'
            )
            rx_cards += f"""
            <article class="card-elevated rounded-2xl p-5 flex flex-col justify-between">
              <div>
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-[11px] font-bold uppercase tracking-widest text-teal-700 tabular-nums">{html.escape(rx['folio'])}</p>
                    <h3 class="mt-1 font-display text-base font-bold text-slate-950">{html.escape(rx['medication'])}</h3>
                    <p class="text-xs text-slate-500">{html.escape(rx['active_ingredient'])}</p>
                  </div>
                  {st_badge}
                </div>
                <dl class="mt-4 space-y-1.5 border-t border-slate-100 pt-3.5 text-xs text-slate-600">
                  <div><strong class="text-slate-800">Dosis:</strong> {html.escape(rx['dosage'])}</div>
                  <div><strong class="text-slate-800">Posología:</strong> {html.escape(rx['schedule'])}</div>
                  <div><strong class="text-slate-800">Duración:</strong> {html.escape(rx['duration'])}</div>
                  <div><strong class="text-slate-800">Prescribe:</strong> {html.escape(rx['doctor_name'])} ({html.escape(rx['specialty'])})</div>
                </dl>
                <p class="mt-3 rounded-xl bg-sand-50 p-3 text-xs leading-relaxed text-slate-600">{html.escape(rx['notes'])}</p>
              </div>
              <div class="mt-4 flex items-center justify-between border-t border-slate-100 pt-3.5 text-xs tabular-nums">
                <span class="text-slate-500">Válida hasta {html.escape(rx['valid_until'])}</span>
                <a href="/paciente/receta?id={rx['id']}" class="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-1.5 font-semibold text-slate-800 hover:border-teal-700 hover:bg-teal-50 hover:text-teal-900">
                  Ver receta imprimible &rarr;
                </a>
              </div>
            </article>
            """
        if not rx_cards:
            rx_cards = '<div class="col-span-full card-elevated rounded-2xl p-10 text-center text-sm text-slate-500">No existen recetas electrónicas registradas.</div>'

        order_cards = ""
        for o in orders:
            order_cards += f"""
            <div class="rounded-2xl border border-slate-200 bg-white p-5 shadow-2xs">
              <div class="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <span class="text-[11px] font-bold uppercase tracking-widest text-teal-700 tabular-nums">{html.escape(o['folio'])}</span>
                  <h3 class="mt-1 font-display text-base font-bold text-slate-950">{html.escape(o['exam_name'])}</h3>
                  <p class="mt-0.5 text-xs text-slate-500">{html.escape(o['department'])} · Solicitado por {html.escape(o['doctor_name'])} ({html.escape(o['issued_date'])})</p>
                </div>
                <span class="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-0.5 text-xs font-semibold text-amber-900">{html.escape(o['status'])}</span>
              </div>
              <div class="mt-3 rounded-xl border border-sky-200/70 bg-sky-50/70 px-3.5 py-2.5 text-xs text-sky-950">
                <strong>Preparación requerida:</strong> {html.escape(o['preparation'])}
              </div>
              <div class="mt-3.5 flex justify-end">
                <a href="/agendar" class="inline-flex items-center gap-1.5 rounded-xl bg-pine-950 px-3.5 py-2 text-xs font-semibold text-white hover:bg-teal-800">
                  Agendar toma / estudio
                </a>
              </div>
            </div>
            """
        if not order_cards:
            order_cards = '<div class="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">No tienes órdenes de exámenes pendientes.</div>'

        body = render_template(
            "prescriptions.html",
            {
                "portal_header": build_portal_shell_header(patient, "recetas", counts),
                "rx_cards": rx_cards,
                "order_cards": order_cards,
            },
        )
        self.render_page("Recetas y Órdenes Médicas", body, active_nav="portal")

    def handle_prescription_detail(self, params):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        rx_id_str = params.get("id", [""])[0].strip()
        if not rx_id_str.isdigit():
            self.redirect("/paciente/recetas")
            return

        conn = get_connection()
        rx = conn.execute(
            """
            SELECT p.*, pt.full_name, pt.rut, pt.birth_date, pt.address, pt.allergies
            FROM prescriptions p
            JOIN patients pt ON pt.id = p.patient_id
            WHERE p.id = ? AND p.patient_id = ?
            """,
            (int(rx_id_str), patient["id"]),
        ).fetchone()
        conn.close()

        if not rx:
            self.redirect("/paciente/recetas")
            return

        body = render_template(
            "prescription_detail.html",
            {
                "rx_folio": html.escape(rx["folio"]),
                "rx_status": html.escape(rx["status"]),
                "rx_medication": html.escape(rx["medication"]),
                "rx_active_ingredient": html.escape(rx["active_ingredient"]),
                "rx_dosage": html.escape(rx["dosage"]),
                "rx_schedule": html.escape(rx["schedule"]),
                "rx_duration": html.escape(rx["duration"]),
                "rx_doctor": html.escape(rx["doctor_name"]),
                "rx_specialty": html.escape(rx["specialty"]),
                "rx_issued": html.escape(rx["issued_date"]),
                "rx_valid": html.escape(rx["valid_until"]),
                "rx_notes": html.escape(rx["notes"]),
                "owner_name": html.escape(rx["full_name"]),
                "owner_rut": html.escape(rx["rut"]),
                "owner_birth": html.escape(rx["birth_date"]),
                "owner_address": html.escape(rx["address"]),
                "owner_allergies": html.escape(rx["allergies"]),
            },
        )
        self.render_page(f"Receta {rx['folio']}", body, active_nav="portal")

    def handle_billing(self):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        counts = self.get_portal_counts(patient["id"])
        conn = get_connection()
        bills = conn.execute(
            "SELECT * FROM billing_documents WHERE patient_id = ? ORDER BY id ASC",
            (patient["id"],),
        ).fetchall()
        conn.close()

        total_sum = sum(b["total_amount"] for b in bills)
        ins_sum = sum(b["insurance_covered"] for b in bills)
        copay_sum = sum(b["copay_amount"] for b in bills)

        bill_rows = ""
        for b in bills:
            st_cls = (
                "border-emerald-200 bg-emerald-50 text-emerald-800"
                if b["status"] == "Pagado"
                else "border-sky-200 bg-sky-50 text-sky-800"
            )
            bill_rows += f"""
            <div class="flex flex-col gap-3 p-5 transition hover:bg-sand-50/90 md:flex-row md:items-center md:justify-between">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="text-xs font-bold uppercase tracking-wider text-teal-700 tabular-nums">{html.escape(b['folio'])}</span>
                  <span class="inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-semibold {st_cls}">{html.escape(b['status'])}</span>
                </div>
                <h3 class="mt-1 text-sm font-bold text-slate-900">{html.escape(b['description'])}</h3>
                <div class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-500 tabular-nums">
                  <span>{html.escape(b['service_date'])}</span>
                  <span aria-hidden="true">&middot;</span>
                  <span>{html.escape(b['provider_unit'])}</span>
                  <span aria-hidden="true">&middot;</span>
                  <span>{html.escape(b['payment_method'])}</span>
                </div>
              </div>
              <div class="flex flex-wrap items-center gap-5 shrink-0 tabular-nums">
                <div class="text-right">
                  <div class="text-[11px] text-slate-500">Arancel {format_clp(b['total_amount'])} · Previsión -{format_clp(b['insurance_covered'])}</div>
                  <div class="font-display text-base font-extrabold text-slate-950">Copago {format_clp(b['copay_amount'])}</div>
                </div>
                <button
                  type="button"
                  data-open-bill
                  data-bill-folio="{html.escape(b['folio'])}"
                  data-bill-date="{html.escape(b['service_date'])}"
                  data-bill-desc="{html.escape(b['description'])}"
                  data-bill-unit="{html.escape(b['provider_unit'])}"
                  data-bill-total="{format_clp(b['total_amount'])}"
                  data-bill-ins="{format_clp(b['insurance_covered'])}"
                  data-bill-copay="{format_clp(b['copay_amount'])}"
                  data-bill-method="{html.escape(b['payment_method'])}"
                  data-bill-status="{html.escape(b['status'])}"
                  class="rounded-xl border border-slate-200 bg-white px-3.5 py-2 text-xs font-semibold text-slate-800 shadow-2xs transition hover:border-teal-700 hover:bg-teal-50 hover:text-teal-900 cursor-pointer"
                >
                  Comprobante
                </button>
              </div>
            </div>
            """
        if not bill_rows:
            bill_rows = '<div class="px-5 py-12 text-center text-sm text-slate-500">No registras boletas ni bonos emitidos.</div>'

        body = render_template(
            "billing.html",
            {
                "portal_header": build_portal_shell_header(patient, "pagos", counts),
                "total_billed": format_clp(total_sum),
                "total_insurance": format_clp(ins_sum),
                "total_copay": format_clp(copay_sum),
                "patient_name": html.escape(patient["full_name"]),
                "patient_rut": html.escape(patient["rut"]),
                "patient_insurance": html.escape(patient["insurance"]),
                "bill_rows": bill_rows,
            },
        )
        self.render_page("Bonos y Boletas", body, active_nav="portal")

    def handle_profile_get(self):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        counts = self.get_portal_counts(patient["id"])
        conn = get_connection()
        logs = conn.execute(
            "SELECT * FROM access_logs WHERE patient_id = ? ORDER BY id DESC LIMIT 12",
            (patient["id"],),
        ).fetchall()
        conn.close()

        log_items = ""
        for ev in logs:
            log_items += f"""
            <li class="relative pl-6 pb-5 last:pb-0 border-l border-slate-200">
              <span class="absolute -left-[5px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-teal-600"></span>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <strong class="text-xs font-bold text-slate-900">{html.escape(ev['action'])}</strong>
                <span class="text-[11px] text-slate-500 tabular-nums">{html.escape(ev['event_time'])}</span>
              </div>
              <p class="mt-0.5 text-xs text-slate-600">{html.escape(ev['detail'])}</p>
              <p class="mt-0.5 text-[11px] text-slate-400 tabular-nums">{html.escape(ev['origin'])}</p>
            </li>
            """
        if not log_items:
            log_items = '<li class="text-xs text-slate-500">Sin eventos recientes registrados.</li>'

        body = render_template(
            "profile.html",
            {
                "portal_header": build_portal_shell_header(patient, "perfil", counts),
                "flash_banner": build_flash_html(self.pop_flash()),
                "patient_name": html.escape(patient["full_name"]),
                "patient_rut": html.escape(patient["rut"]),
                "patient_birth": html.escape(patient["birth_date"]),
                "patient_insurance": html.escape(patient["insurance"]),
                "patient_blood": html.escape(patient["blood_type"]),
                "patient_allergies": html.escape(patient["allergies"]),
                "patient_chronic": html.escape(patient["chronic_conditions"]),
                "patient_email": html.escape(patient["email"]),
                "patient_phone": html.escape(patient["phone"]),
                "patient_address": html.escape(patient["address"]),
                "emergency_name": html.escape(patient["emergency_contact_name"]),
                "emergency_phone": html.escape(patient["emergency_contact_phone"]),
                "access_log_items": log_items,
            },
        )
        self.render_page("Mi Perfil y Actividad", body, active_nav="portal")

    def handle_profile_update(self, form):
        patient = self.get_current_patient()
        if not patient:
            self.redirect("/login")
            return

        new_email = form.get("email", [""])[0].strip().lower()
        new_phone = form.get("phone", [""])[0].strip()
        new_address = form.get("address", [patient["address"]])[0].strip()
        new_em_name = form.get("emergency_contact_name", [patient["emergency_contact_name"]])[0].strip()
        new_em_phone = form.get("emergency_contact_phone", [patient["emergency_contact_phone"]])[0].strip()

        if not EMAIL_RE.match(new_email):
            self.set_flash("error", "El formato del correo electrónico no es válido. No se guardaron cambios.")
            self.redirect("/paciente/perfil")
            return

        if len(PHONE_DIGITS_RE.findall(new_phone)) < 8:
            self.set_flash("error", "Ingresa un teléfono de contacto válido de al menos 8 dígitos.")
            self.redirect("/paciente/perfil")
            return

        if len(new_address) < 6 or not new_em_name or len(PHONE_DIGITS_RE.findall(new_em_phone)) < 8:
            self.set_flash("error", "Completa una dirección y un contacto de emergencia válidos antes de guardar.")
            self.redirect("/paciente/perfil")
            return

        conn = get_connection()
        try:
            conn.execute(
                """
                UPDATE patients
                SET email = ?, phone = ?, address = ?, emergency_contact_name = ?, emergency_contact_phone = ?
                WHERE id = ?
                """,
                (new_email, new_phone, new_address, new_em_name, new_em_phone, patient["id"]),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            self.set_flash(
                "error",
                f"El correo {new_email} ya está asociado a otra cuenta de paciente. No se realizaron cambios.",
            )
            self.redirect("/paciente/perfil")
            return
        finally:
            try:
                conn.close()
            except Exception:
                pass

        record_access_event(
            patient["id"],
            "Actualización de perfil",
            "Modificación de datos de contacto, domicilio y emergencia",
            self.client_origin_label(),
        )
        self.set_flash("success", "Tus datos personales, de contacto y emergencia fueron actualizados correctamente.")
        self.redirect("/paciente/perfil")

    def handle_robots(self):
        content = (
            "User-agent: *\n"
            "Disallow: /paciente/\n"
            "Disallow: /internal/status\n"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def handle_status(self):
        conn = get_connection()
        n_specs = conn.execute("SELECT COUNT(*) FROM specialists").fetchone()[0]
        n_pats = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        n_recs = conn.execute("SELECT COUNT(*) FROM medical_records").fetchone()[0]
        n_obs = conn.execute("SELECT COUNT(*) FROM lab_observations").fetchone()[0]
        n_rx = conn.execute("SELECT COUNT(*) FROM prescriptions").fetchone()[0]
        n_ord = conn.execute("SELECT COUNT(*) FROM clinical_orders").fetchone()[0]
        n_bills = conn.execute("SELECT COUNT(*) FROM billing_documents").fetchone()[0]
        n_appts = conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0]
        conn.close()

        body = render_template(
            "status.html",
            {
                "sqlite_version": sqlite3.sqlite_version,
                "stats_summary": (
                    f"{n_specs} especialistas · {n_pats} pacientes · {n_recs} informes clínicos "
                    f"({n_obs} analitos) · {n_rx} recetas · {n_ord} órdenes · {n_bills} boletas · {n_appts} citas"
                ),
                "server_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
        self.render_page("Estado del Sistema", body)


def run():
    init_db()
    host = os.environ.get("CLINICA_HOST", "127.0.0.1")
    port = int(os.environ.get("CLINICA_PORT", "5000"))
    server = ThreadingHTTPServer((host, port), ClinicaHandler)
    print(f"Clínica Miramar ejecutándose en http://{host}:{port}")
    print("Presiona Ctrl+C para detener el servidor.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()


if __name__ == "__main__":
    run()
