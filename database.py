import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "clinica.db")
SCHEMA_VERSION = 3


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_schema_version(conn):
    try:
        row = conn.execute("SELECT version FROM schema_meta LIMIT 1").fetchone()
        return int(row["version"]) if row else 0
    except sqlite3.OperationalError:
        return 0


def init_db():
    conn = get_connection()
    current_ver = _get_schema_version(conn)

    if current_ver < SCHEMA_VERSION:
        conn.close()
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        conn = get_connection()

    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            version INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS specialists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            subspecialty TEXT NOT NULL,
            bio TEXT NOT NULL,
            schedule TEXT NOT NULL,
            location TEXT NOT NULL,
            experience_years INTEGER NOT NULL,
            rating TEXT NOT NULL,
            photo TEXT NOT NULL,
            telemedicine INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            rut TEXT NOT NULL,
            birth_date TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            insurance TEXT NOT NULL,
            blood_type TEXT NOT NULL,
            emergency_contact_name TEXT NOT NULL,
            emergency_contact_phone TEXT NOT NULL,
            allergies TEXT NOT NULL,
            chronic_conditions TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS medical_records (
            id INTEGER PRIMARY KEY,
            patient_id INTEGER NOT NULL,
            exam_date TEXT NOT NULL,
            record_type TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            status TEXT NOT NULL,
            findings TEXT NOT NULL,
            recommendations TEXT NOT NULL,
            attachment_image TEXT NOT NULL DEFAULT '',
            dicom_meta TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER NOT NULL,
            analyte TEXT NOT NULL,
            value_num REAL NOT NULL,
            value_display TEXT NOT NULL,
            unit TEXT NOT NULL,
            ref_min REAL NOT NULL,
            ref_max REAL NOT NULL,
            ref_text TEXT NOT NULL,
            flag TEXT NOT NULL,
            FOREIGN KEY (record_id) REFERENCES medical_records(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            specialist_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            appt_date TEXT NOT NULL,
            appt_time TEXT NOT NULL,
            modality TEXT NOT NULL,
            location TEXT NOT NULL,
            prep_note TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY,
            folio TEXT UNIQUE NOT NULL,
            patient_id INTEGER NOT NULL,
            medication TEXT NOT NULL,
            active_ingredient TEXT NOT NULL,
            dosage TEXT NOT NULL,
            schedule TEXT NOT NULL,
            duration TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            specialty TEXT NOT NULL,
            issued_date TEXT NOT NULL,
            valid_until TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            patient_id INTEGER NOT NULL,
            exam_name TEXT NOT NULL,
            department TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            issued_date TEXT NOT NULL,
            preparation TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS billing_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT UNIQUE NOT NULL,
            patient_id INTEGER NOT NULL,
            service_date TEXT NOT NULL,
            description TEXT NOT NULL,
            provider_unit TEXT NOT NULL,
            total_amount INTEGER NOT NULL,
            insurance_covered INTEGER NOT NULL,
            copay_amount INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            event_time TEXT NOT NULL,
            action TEXT NOT NULL,
            detail TEXT NOT NULL,
            origin TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )
        """
    )

    cur.execute("SELECT COUNT(*) FROM schema_meta")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO schema_meta (version) VALUES (?)", (SCHEMA_VERSION,))

    # 1. Especialistas
    cur.execute("SELECT COUNT(*) FROM specialists")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO specialists (
                name, specialty, subspecialty, bio, schedule, location,
                experience_years, rating, photo, telemedicine
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Dra. Camila Rojas",
                    "Cardiología",
                    "Cardiología Preventiva y Ecocardiografía",
                    "Especialista en diagnóstico cardiovascular no invasivo, control de hipertensión arterial y medicina preventiva en adultos.",
                    "Lun a Vie · 09:00 - 17:30",
                    "Torre Norte, Piso 4 · Box 402",
                    12,
                    "4.9",
                    "/static/img/doc-1.jpg",
                    1,
                ),
                (
                    "Dr. Andrés Soto",
                    "Medicina Interna",
                    "Enfermedades Crónicas y Chequeo Preventivo",
                    "Atención integral del adulto, seguimiento metabólico, chequeos preventivos anuales y coordinación clínica multidisciplinaria.",
                    "Lun a Jue · 08:30 - 18:00",
                    "Torre Central, Piso 2 · Box 210",
                    15,
                    "4.8",
                    "/static/img/doc-2.jpg",
                    1,
                ),
                (
                    "Dra. Sofía Valdés",
                    "Pediatría",
                    "Control Niño Sano y Telemedicina Pediátrica",
                    "Acompañamiento clínico desde recién nacidos hasta la adolescencia, vacunación y orientación preventiva para familias.",
                    "Lun a Vie · 09:30 - 17:00",
                    "Torre Sur, Piso 1 · Box 108",
                    9,
                    "5.0",
                    "/static/img/doc-3.jpg",
                    1,
                ),
                (
                    "Dr. Mateo Herrera",
                    "Neurología",
                    "Trastornos del Sueño y Cefaleas",
                    "Evaluación neurológica clínica de alta complejidad, manejo de migrañas crónicas y medicina del sueño.",
                    "Mar a Vie · 10:00 - 18:30",
                    "Torre Norte, Piso 5 · Box 504",
                    21,
                    "4.9",
                    "/static/img/doc-4.jpg",
                    0,
                ),
            ],
        )

    # 2. Pacientes (5 registros sintéticos con PII + PHI completo)
    cur.execute("SELECT COUNT(*) FROM patients")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO patients (
                full_name, rut, birth_date, email, password, phone, address,
                insurance, blood_type, emergency_contact_name, emergency_contact_phone,
                allergies, chronic_conditions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Ana Silva Morales",
                    "16.482.910-4",
                    "14 Mar 1987 (39 años)",
                    "ana.silva@miramar.local",
                    "Miramar2026!",
                    "+56 9 8421 3309",
                    "Av. San Martín 640, Depto. 804, Viña del Mar",
                    "Isapre Consalud · Plan Preferente",
                    "O+",
                    "Rodrigo Silva Morales (Hermano)",
                    "+56 9 9104 7721",
                    "Penicilina (reacción urticarial moderada), Látex",
                    "Hipertensión arterial estadio 1 controlada, Hipotiroidismo subclínico",
                ),
                (
                    "Carlos Méndez Paredes",
                    "14.920.345-K",
                    "22 Ago 1981 (45 años)",
                    "carlos.mendez@miramar.local",
                    "Salud2026!",
                    "+56 9 7190 4482",
                    "Calle 4 Norte 1185, Viña del Mar",
                    "Fonasa · Tramo D",
                    "A+",
                    "Marcela Vega Toro (Cónyuge)",
                    "+56 9 8820 1190",
                    "Ácido acetilsalicílico (intolerancia gástrica)",
                    "Migraña episódica con aura, Insomnio de conciliación",
                ),
                (
                    "Valentina Riquelme Castro",
                    "18.215.603-2",
                    "09 Nov 1993 (33 años)",
                    "valentina.riquelme@miramar.local",
                    "Paciente2026!",
                    "+56 9 6312 8840",
                    "Av. Borgoño 14210, Reñaca, Viña del Mar",
                    "Isapre Colmena · Plan Gold",
                    "B+",
                    "Patricia Castro León (Madre)",
                    "+56 9 9811 2305",
                    "Sin alergias medicamentosas registradas",
                    "Asma bronquial leve intermitente",
                ),
                (
                    "Rodrigo Fuentes Araya",
                    "12.640.118-7",
                    "30 Ene 1974 (52 años)",
                    "rodrigo.fuentes@miramar.local",
                    "Paciente2026!",
                    "+56 9 9234 5510",
                    "Av. España 2280, Valparaíso",
                    "Isapre Cruz Blanca · Plan Óptimo",
                    "AB+",
                    "Claudia Araya Soto (Esposa)",
                    "+56 9 9234 5511",
                    "Contraste yodado endovenoso (rash leve)",
                    "Dislipidemia mixta, Resistencia a la insulina",
                ),
                (
                    "Francisca Tapia León",
                    "19.440.822-1",
                    "17 Jun 1997 (29 años)",
                    "francisca.tapia@miramar.local",
                    "Paciente2026!",
                    "+56 9 5480 9123",
                    "1 Poniente 512, Depto. 302, Viña del Mar",
                    "Fonasa · Tramo C",
                    "O-",
                    "Jorge Tapia Ruiz (Padre)",
                    "+56 9 7742 0198",
                    "Sulfonamidas",
                    "Sin antecedentes mórbidos crónicos",
                ),
            ],
        )

    # 3. Informes Clínicos (12 informes totales; 5 en Ana Silva, 3 en Carlos, 4 en otros pacientes)
    cur.execute("SELECT COUNT(*) FROM medical_records")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO medical_records (
                id, patient_id, exam_date, record_type, category, title, doctor_name,
                status, findings, recommendations, attachment_image, dicom_meta
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1001,
                    1,
                    "18 Nov 2026",
                    "Cardiología",
                    "Cardiología No Invasiva",
                    "Electrocardiograma 12 Derivaciones y Perfil Lipídico",
                    "Dra. Camila Rojas",
                    "Disponible",
                    "Ritmo sinusal regular a 68 lpm, eje eléctrico normal (+45°), PR 156 ms, QRS 86 ms, QTc 408 ms. Sin signos de isquemia aguda ni sobrecarga ventricular. Perfil lipídico muestra LDL levemente sobre meta preventiva (118 mg/dL) con HDL protector adecuado (61 mg/dL).",
                    "Mantener Losartán 50 mg/día y reforzar dieta mediterránea baja en grasas saturadas. Repetir perfil lipídico en 6 meses junto a control cardiológico.",
                    "/static/img/exam-ecg.jpg",
                    "ECG 12D · 25 mm/s · 10 mm/mV · Equipo GE MAC 2000 · Unidad Cardiología",
                ),
                (
                    1002,
                    2,
                    "15 Nov 2026",
                    "Imagenología",
                    "Neurorradiología · Resonancia",
                    "Resonancia Magnética de Encéfalo sin Contraste",
                    "Dr. Mateo Herrera",
                    "Disponible",
                    "Parénquima encefálico supratentorial e infratentorial de morfología e intensidad de señal conservadas en secuencias T1, T2 y FLAIR. Sistema ventricular simétrico de tamaño normal, línea media centrada, sin lesiones ocupantes de espacio ni hallazgos vasculares agudos.",
                    "Estudio normal compatible con migraña primaria episódica. Mantener profilaxis nocturna indicada y registrar frecuencia de episodios en calendario clínico.",
                    "/static/img/exam-mri-brain.jpg",
                    "RM 1.5T · Corte Axial T2-TSE · Espesor 4.0 mm · Siemens Magnetom Altea",
                ),
                (
                    1003,
                    1,
                    "10 Nov 2026",
                    "Imagenología",
                    "Radiología Digital",
                    "Radiografía de Tórax PA y Lateral",
                    "Dr. Andrés Soto",
                    "Disponible",
                    "Campos pulmonares bien expandidos y libres de focos de condensación, nódulos o derrame pleural. Silueta cardiomediastínica de tamaño y configuración normal (índice cardiotorácico 0.46). Estructuras óseas torácicas sin lesiones agudas.",
                    "Estudio radiológico torácico normal. No requiere estudios de imagen adicionales en el corto plazo.",
                    "/static/img/exam-chest-xray.jpg",
                    "RX Digital PA · 120 kVp · 2.4 mAs · Detector Carestream DRX · Sala 2",
                ),
                (
                    1004,
                    1,
                    "02 Nov 2026",
                    "Laboratorio",
                    "Laboratorio Clínico Central",
                    "Perfil Bioquímico, Glicemia en Ayunas y Vitamina D",
                    "Dr. Andrés Soto",
                    "Disponible",
                    "Glicemia basal discretamente elevada en rango de glicemia alterada en ayunas (108 mg/dL) con Hemoglobina Glicosilada normal-alta (5.8%). Insuficiencia marcada de 25-OH Vitamina D (19.4 ng/mL). Función renal y transaminasas hepáticas dentro de parámetros fisiológicos.",
                    "Iniciar suplementación con Colecalciferol (Vitamina D3 2.000 UI/día) por 90 días. Plan de actividad física 150 min/semana y reevaluación metabólica trimestral.",
                    "",
                    "",
                ),
                (
                    1005,
                    1,
                    "04 Oct 2026",
                    "Laboratorio",
                    "Laboratorio Clínico Central",
                    "Hemograma Completo y Perfil Tiroideo (TSH / T4L)",
                    "Dr. Andrés Soto",
                    "Revisado",
                    "Serie roja, blanca y plaquetaria dentro de rangos esperados para edad y sexo. Hormona tiroestimulante (TSH) en rango eutiroideo terapéutico (2.14 uUI/mL) bajo dosis actual de Levotiroxina.",
                    "Continuar misma dosis de Levotiroxina 50 mcg en ayunas. Próximo control tiroideo en 6 meses.",
                    "",
                    "",
                ),
                (
                    1006,
                    1,
                    "19 Ago 2026",
                    "Imagenología",
                    "Neurorradiología · Control Preventivo",
                    "Resonancia Magnética de Encéfalo (Estudio Cefalea Tensional)",
                    "Dr. Mateo Herrera",
                    "Revisado",
                    "Secuencias axiales T2 y FLAIR sin alteraciones parenquimatosas focales ni anomalías vasculares. Ventrículos laterales simétricos y espacios subaracnoideos conservados.",
                    "Estudio basal normal; se descarta patología estructural. Manejo conservador de higiene postural y del sueño.",
                    "/static/img/exam-mri-brain.jpg",
                    "RM 1.5T · Corte Axial T2-TSE · Espesor 4.0 mm · Unidad Imagenología",
                ),
                (
                    1007,
                    2,
                    "28 Oct 2026",
                    "Laboratorio",
                    "Laboratorio Clínico Central",
                    "Perfil Hepático y Electrolitos Plasmáticos",
                    "Dr. Andrés Soto",
                    "Revisado",
                    "Transaminasas GOT/GPT, bilirrubina total y fosfatasas alcalinas en límites normales. Electrolitos plasmáticos (Na, K, Cl) equilibrados.",
                    "Apto para continuar tratamiento neurológico profiláctico sin ajustes hepáticos.",
                    "",
                    "",
                ),
                (
                    1008,
                    2,
                    "11 Sep 2026",
                    "Cardiología",
                    "Cardiología No Invasiva",
                    "Electrocardiograma de Reposo Previo a Terapia",
                    "Dra. Camila Rojas",
                    "Revisado",
                    "Ritmo sinusal normal a 72 lpm, intervalo QTc 402 ms sin prolongación ni trastornos de conducción AV.",
                    "Sin contraindicación cardiovascular para terapia triptánica.",
                    "/static/img/exam-ecg.jpg",
                    "ECG 12D · 25 mm/s · Unidad Cardiología",
                ),
                (
                    1009,
                    3,
                    "12 Nov 2026",
                    "Imagenología",
                    "Radiología Digital",
                    "Radiografía de Tórax Control Asma Bronquial",
                    "Dr. Andrés Soto",
                    "Disponible",
                    "Sin infiltrados parenquimatosos ni signos de hiperinsuflación aguda.",
                    "Mantener terapia inhalatoria de rescate según plan de acción.",
                    "/static/img/exam-chest-xray.jpg",
                    "RX Digital PA · Sala 1",
                ),
                (
                    1010,
                    4,
                    "08 Nov 2026",
                    "Laboratorio",
                    "Laboratorio Clínico Central",
                    "Perfil Lipídico Completo y Curva de Insulina",
                    "Dra. Camila Rojas",
                    "Disponible",
                    "LDL 148 mg/dL, Triglicéridos 210 mg/dL, HOMA-IR 3.4.",
                    "Ajustar estatina nocturna y derivación a nutrición clínica.",
                    "",
                    "",
                ),
                (
                    1011,
                    4,
                    "01 Oct 2026",
                    "Cardiología",
                    "Cardiología No Invasiva",
                    "Electrocardiograma Basal de Control",
                    "Dra. Camila Rojas",
                    "Revisado",
                    "Ritmo sinusal a 74 lpm, sin alteraciones agudas de repolarización.",
                    "Control anual preventivo.",
                    "/static/img/exam-ecg.jpg",
                    "ECG 12D · Unidad Cardiología",
                ),
                (
                    1012,
                    5,
                    "14 Nov 2026",
                    "Laboratorio",
                    "Laboratorio Clínico Central",
                    "Hemograma Completo y Ferritina Sérica",
                    "Dr. Andrés Soto",
                    "Disponible",
                    "Hemoglobina 12.6 g/dL, Ferritina 24 ng/mL en límite inferior.",
                    "Reforzar aporte de hierro dietario y reevaluar en 4 meses.",
                    "",
                    "",
                ),
            ],
        )

    # 4. Observaciones cuantitativas de laboratorio (analitos con rangos de referencia)
    cur.execute("SELECT COUNT(*) FROM lab_observations")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO lab_observations (
                record_id, analyte, value_num, value_display, unit,
                ref_min, ref_max, ref_text, flag
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                # Record 1001 - Perfil Lipídico de Ana Silva
                (1001, "Colesterol Total", 196.0, "196", "mg/dL", 120.0, 200.0, "< 200", "normal"),
                (1001, "Colesterol LDL", 118.0, "118", "mg/dL", 0.0, 100.0, "< 100", "alto"),
                (1001, "Colesterol HDL", 61.0, "61", "mg/dL", 50.0, 95.0, "> 50", "normal"),
                (1001, "Triglicéridos", 105.0, "105", "mg/dL", 40.0, 150.0, "< 150", "normal"),
                (1001, "Frecuencia Cardíaca (ECG)", 68.0, "68", "lpm", 60.0, 100.0, "60 - 100", "normal"),
                # Record 1004 - Perfil Bioquímico + Vitamina D de Ana Silva
                (1004, "Glicemia en Ayunas", 108.0, "108", "mg/dL", 70.0, 99.0, "70 - 99", "alto"),
                (1004, "Hemoglobina Glicosilada (HbA1c)", 5.8, "5.8", "%", 4.0, 5.6, "< 5.7", "alto"),
                (1004, "25-OH Vitamina D Total", 19.4, "19.4", "ng/mL", 30.0, 100.0, "30 - 100", "bajo"),
                (1004, "Creatinina Sérica", 0.78, "0.78", "mg/dL", 0.55, 1.02, "0.55 - 1.02", "normal"),
                (1004, "Transaminasa GPT (ALT)", 21.0, "21", "U/L", 7.0, 35.0, "7 - 35", "normal"),
                (1004, "Ácido Úrico", 4.6, "4.6", "mg/dL", 2.6, 6.0, "2.6 - 6.0", "normal"),
                # Record 1005 - Hemograma + Tiroides de Ana Silva
                (1005, "Hemoglobina", 13.8, "13.8", "g/dL", 12.0, 16.0, "12.0 - 16.0", "normal"),
                (1005, "Hematocrito", 41.2, "41.2", "%", 36.0, 46.0, "36.0 - 46.0", "normal"),
                (1005, "Leucocitos", 6.4, "6.4", "x10³/uL", 4.5, 11.0, "4.5 - 11.0", "normal"),
                (1005, "Plaquetas", 245.0, "245", "x10³/uL", 150.0, 400.0, "150 - 400", "normal"),
                (1005, "TSH Ultrasensible", 2.14, "2.14", "uUI/mL", 0.40, 4.20, "0.40 - 4.20", "normal"),
                (1005, "T4 Libre", 1.24, "1.24", "ng/dL", 0.80, 1.80, "0.80 - 1.80", "normal"),
                # Record 1007 - Carlos Méndez
                (1007, "Transaminasa GOT (AST)", 24.0, "24", "U/L", 10.0, 40.0, "10 - 40", "normal"),
                (1007, "Transaminasa GPT (ALT)", 29.0, "29", "U/L", 10.0, 45.0, "10 - 45", "normal"),
                (1007, "Bilirrubina Total", 0.72, "0.72", "mg/dL", 0.20, 1.20, "0.20 - 1.20", "normal"),
                (1007, "Sodio Plasmático", 140.0, "140", "mEq/L", 135.0, 145.0, "135 - 145", "normal"),
                (1007, "Potasio Plasmático", 4.3, "4.3", "mEq/L", 3.5, 5.1, "3.5 - 5.1", "normal"),
                # Record 1010 - Rodrigo Fuentes
                (1010, "Colesterol LDL", 148.0, "148", "mg/dL", 0.0, 100.0, "< 100", "alto"),
                (1010, "Triglicéridos", 210.0, "210", "mg/dL", 40.0, 150.0, "< 150", "alto"),
                (1010, "Insulina Basal", 16.2, "16.2", "uUI/mL", 2.6, 12.0, "2.6 - 12.0", "alto"),
                # Record 1012 - Francisca Tapia
                (1012, "Hemoglobina", 12.6, "12.6", "g/dL", 12.0, 16.0, "12.0 - 16.0", "normal"),
                (1012, "Ferritina Sérica", 24.0, "24", "ng/mL", 30.0, 150.0, "30 - 150", "bajo"),
                (1012, "Hierro Sérico", 68.0, "68", "ug/dL", 50.0, 170.0, "50 - 170", "normal"),
            ],
        )

    # 5. Citas médicas
    cur.execute("SELECT COUNT(*) FROM appointments")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO appointments (
                patient_id, specialist_name, specialty, appt_date, appt_time,
                modality, location, prep_note, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    1,
                    "Dra. Camila Rojas",
                    "Cardiología",
                    "03 Dic 2026",
                    "10:30 hrs",
                    "Presencial",
                    "Torre Norte, Piso 4 · Box 402",
                    "Presentarse 15 minutos antes con cédula de identidad y registro de presión arterial.",
                    "Confirmada",
                ),
                (
                    1,
                    "Dr. Andrés Soto",
                    "Medicina Interna",
                    "16 Dic 2026",
                    "16:00 hrs",
                    "Telemedicina",
                    "Sala Virtual · Portal de Pacientes",
                    "Conéctate 5 minutos antes desde un lugar tranquilo con cámara y micrófono activos.",
                    "Programada",
                ),
                (
                    2,
                    "Dr. Mateo Herrera",
                    "Neurología",
                    "09 Dic 2026",
                    "11:15 hrs",
                    "Presencial",
                    "Torre Norte, Piso 5 · Box 504",
                    "Traer registro de episodios de cefalea de los últimos 30 días.",
                    "Confirmada",
                ),
                (
                    3,
                    "Dr. Andrés Soto",
                    "Medicina Interna",
                    "04 Dic 2026",
                    "09:00 hrs",
                    "Telemedicina",
                    "Sala Virtual · Portal de Pacientes",
                    "Tener a mano inhaladores actuales para revisión de técnica.",
                    "Confirmada",
                ),
                (
                    4,
                    "Dra. Camila Rojas",
                    "Cardiología",
                    "11 Dic 2026",
                    "15:30 hrs",
                    "Presencial",
                    "Torre Norte, Piso 4 · Box 402",
                    "Traer exámenes de laboratorio recientes.",
                    "Programada",
                ),
                (
                    5,
                    "Dra. Sofía Valdés",
                    "Pediatría",
                    "14 Dic 2026",
                    "12:00 hrs",
                    "Presencial",
                    "Torre Sur, Piso 1 · Box 108",
                    "Control preventivo familiar.",
                    "Confirmada",
                ),
            ],
        )

    # 6. Recetas Médicas Electrónicas
    cur.execute("SELECT COUNT(*) FROM prescriptions")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO prescriptions (
                id, folio, patient_id, medication, active_ingredient, dosage,
                schedule, duration, doctor_name, specialty, issued_date,
                valid_until, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    501,
                    "REC-2026-0841",
                    1,
                    "Losartán Potásico 50 mg",
                    "Losartán potásico · Comprimidos recubiertos",
                    "1 comprimido (50 mg)",
                    "Cada 24 horas por la mañana",
                    "Tratamiento crónico · 90 días",
                    "Dra. Camila Rojas",
                    "Cardiología",
                    "18 Nov 2026",
                    "18 Feb 2027",
                    "Vigente",
                    "Controlar presión arterial 2 veces por semana en domicilio. No suspender abruptamente.",
                ),
                (
                    502,
                    "REC-2026-0819",
                    1,
                    "Colecalciferol (Vitamina D3) 2.000 UI",
                    "Colecalciferol · Cápsulas blandas",
                    "1 cápsula (2.000 UI)",
                    "1 vez al día junto al almuerzo",
                    "90 días continuos",
                    "Dr. Andrés Soto",
                    "Medicina Interna",
                    "02 Nov 2026",
                    "02 Feb 2027",
                    "Vigente",
                    "Tomar junto con una comida principal para mejorar absorción liposoluble.",
                ),
                (
                    503,
                    "REC-2026-0762",
                    1,
                    "Levotiroxina Sódica 50 mcg",
                    "Levotiroxina sódica · Comprimidos",
                    "1 comprimido (50 mcg)",
                    "Diariamente en ayunas, 45 min antes del desayuno",
                    "Tratamiento crónico · 180 días",
                    "Dr. Andrés Soto",
                    "Medicina Interna",
                    "04 Oct 2026",
                    "04 Abr 2027",
                    "Vigente",
                    "Ingerir solo con agua. Evitar suplementos de calcio o hierro dentro de las 4 horas siguientes.",
                ),
                (
                    504,
                    "REC-2026-0610",
                    1,
                    "Paracetamol 500 mg",
                    "Paracetamol · Comprimidos",
                    "1 comprimido en caso de cefalea",
                    "Cada 8 horas S.O.S. (máx. 3 g/día)",
                    "Uso eventual · 30 días",
                    "Dr. Mateo Herrera",
                    "Neurología",
                    "19 Ago 2026",
                    "19 Sep 2026",
                    "Finalizada",
                    "Evitar automedicación con AINEs frecuentes.",
                ),
                (
                    505,
                    "REC-2026-0833",
                    2,
                    "Sumatriptán 50 mg",
                    "Sumatriptán succinato · Comprimidos",
                    "1 comprimido al inicio de crisis migrañosa",
                    "Repetir tras 2 horas solo si persiste dolor (máx. 100 mg/24h)",
                    "60 días · Uso ante crisis",
                    "Dr. Mateo Herrera",
                    "Neurología",
                    "15 Nov 2026",
                    "15 Ene 2027",
                    "Vigente",
                    "No combinar con ergotamínicos. Evitar si presenta dolor torácico atípico.",
                ),
                (
                    506,
                    "REC-2026-0828",
                    2,
                    "Amitriptilina 10 mg",
                    "Clorhidrato de amitriptilina · Comprimidos",
                    "1 comprimido (10 mg)",
                    "Todas las noches a las 21:30 hrs",
                    "90 días · Profilaxis migraña",
                    "Dr. Mateo Herrera",
                    "Neurología",
                    "15 Nov 2026",
                    "15 Feb 2027",
                    "Vigente",
                    "Puede producir somnolencia leve inicial. Reevaluar respuesta en control neurológico.",
                ),
            ],
        )

    # 7. Órdenes Médicas Pendientes
    cur.execute("SELECT COUNT(*) FROM clinical_orders")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO clinical_orders (
                folio, patient_id, exam_name, department, doctor_name,
                issued_date, preparation, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "ORD-2026-3104",
                    1,
                    "Ecocardiograma Doppler Transtorácico",
                    "Unidad de Cardiología · Torre Norte Piso 4",
                    "Dra. Camila Rojas",
                    "18 Nov 2026",
                    "No requiere ayuno. Traer ECG previo y listado de medicamentos actuales.",
                    "Pendiente de agenda",
                ),
                (
                    "ORD-2026-3088",
                    1,
                    "Control Trimestral: Glicemia Basal, HbA1c y 25-OH Vitamina D",
                    "Laboratorio Clínico Central · Torre Central Piso 1",
                    "Dr. Andrés Soto",
                    "02 Nov 2026",
                    "Ayuno estricto de 8 a 12 horas (se permite agua). Asistir entre 07:30 y 10:30 hrs.",
                    "Vigente (para Feb 2027)",
                ),
                (
                    "ORD-2026-3112",
                    2,
                    "Polisomnografía Nocturna Diagnóstica",
                    "Centro de Medicina del Sueño · Torre Norte Piso 5",
                    "Dr. Mateo Herrera",
                    "15 Nov 2026",
                    "Evitar cafeína y bebidas energéticas 12 horas antes del estudio.",
                    "Pendiente de agenda",
                ),
                (
                    "ORD-2026-3095",
                    4,
                    "Test de Esfuerzo Cardiovascular",
                    "Unidad de Cardiología · Torre Norte Piso 4",
                    "Dra. Camila Rojas",
                    "08 Nov 2026",
                    "Vestir ropa y calzado deportivo cómodo; comida liviana 2 horas antes.",
                    "Pendiente de agenda",
                ),
            ],
        )

    # 8. Bonos y Boletas Electrónicas (Datos Financieros + Previsión)
    cur.execute("SELECT COUNT(*) FROM billing_documents")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO billing_documents (
                folio, patient_id, service_date, description, provider_unit,
                total_amount, insurance_covered, copay_amount, payment_method, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "BOL-0049821",
                    1,
                    "18 Nov 2026",
                    "Consulta Cardiología + Electrocardiograma 12 Derivaciones",
                    "Torre Norte · Cardiología",
                    78500,
                    62800,
                    15700,
                    "Bono I-Med · Visa •••• 4821",
                    "Pagado",
                ),
                (
                    "BOL-0049614",
                    1,
                    "10 Nov 2026",
                    "Radiografía de Tórax PA y Lateral Digital",
                    "Unidad de Imagenología",
                    42900,
                    34320,
                    8580,
                    "Bono I-Med · Débito •••• 1904",
                    "Pagado",
                ),
                (
                    "BOL-0049302",
                    1,
                    "02 Nov 2026",
                    "Pack Laboratorio: Perfil Bioquímico, HbA1c y 25-OH Vitamina D",
                    "Laboratorio Clínico Central",
                    64200,
                    48150,
                    16050,
                    "Bono I-Med · Visa •••• 4821",
                    "Pagado",
                ),
                (
                    "BOL-0048790",
                    1,
                    "04 Oct 2026",
                    "Consulta Medicina Interna + Hemograma y Perfil Tiroideo",
                    "Torre Central · Medicina Interna",
                    71400,
                    57120,
                    14280,
                    "Bono I-Med · Visa •••• 4821",
                    "Reembolsado",
                ),
                (
                    "BOL-0047915",
                    1,
                    "19 Ago 2026",
                    "Resonancia Magnética de Encéfalo sin Contraste",
                    "Unidad de Imagenología · RM 1.5T",
                    198000,
                    158400,
                    39600,
                    "Bono I-Med · Visa •••• 4821",
                    "Reembolsado",
                ),
                (
                    "BOL-0049770",
                    2,
                    "15 Nov 2026",
                    "Resonancia Magnética Encéfalo + Consulta Neurología",
                    "Neurología e Imagenología",
                    215000,
                    129000,
                    86000,
                    "Bono Fonasa · Mastercard •••• 7732",
                    "Pagado",
                ),
                (
                    "BOL-0049105",
                    2,
                    "28 Oct 2026",
                    "Perfil Hepático y Electrolitos Plasmáticos",
                    "Laboratorio Clínico Central",
                    31500,
                    18900,
                    12600,
                    "Bono Fonasa · Débito •••• 3018",
                    "Pagado",
                ),
                (
                    "BOL-0049450",
                    4,
                    "08 Nov 2026",
                    "Perfil Lipídico Completo y Curva de Insulina",
                    "Laboratorio Clínico Central",
                    54800,
                    43840,
                    10960,
                    "Bono I-Med · Visa •••• 9140",
                    "Pagado",
                ),
            ],
        )

    # 9. Registro de Actividad de Cuenta (Access Logs)
    cur.execute("SELECT COUNT(*) FROM access_logs")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            """
            INSERT INTO access_logs (patient_id, event_time, action, detail, origin)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "23 Nov 2026 · 19:42", "Consulta de resultado", "Visualización de Folio #1001 (ECG y Perfil Lipídico)", "192.168.1.24 · Navegador Web"),
                (1, "23 Nov 2026 · 19:40", "Inicio de sesión", "Acceso exitoso al Portal de Pacientes", "192.168.1.24 · Navegador Web"),
                (1, "18 Nov 2026 · 16:15", "Emisión de receta", "Receta electrónica REC-2026-0841 publicada por Dra. Camila Rojas", "Sistema Clínico Interno"),
                (1, "10 Nov 2026 · 14:08", "Resultado disponible", "Informe de Radiografía de Tórax (#1003) validado y publicado", "Sistema Imagenología RIS"),
                (1, "02 Nov 2026 · 11:22", "Actualización de datos", "Confirmación de teléfono de contacto de emergencia", "192.168.1.24 · Portal Móvil"),
                (2, "20 Nov 2026 · 21:05", "Consulta de resultado", "Visualización de Folio #1002 (Resonancia Encéfalo)", "192.168.1.38 · Navegador Web"),
                (2, "15 Nov 2026 · 18:30", "Emisión de receta", "Receta electrónica REC-2026-0833 publicada por Dr. Mateo Herrera", "Sistema Clínico Interno"),
            ],
        )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de datos v{SCHEMA_VERSION} inicializada en {DB_PATH}")
