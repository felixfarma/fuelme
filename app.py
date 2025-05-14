import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'mi_clave_secreta_segura'
PERFILES_FILE = 'perfiles.json'

# ————— Gestión de perfiles —————

def load_perfiles():
    try:
        with open(PERFILES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_perfiles(perfiles):
    with open(PERFILES_FILE, 'w', encoding='utf-8') as f:
        json.dump(perfiles, f, indent=4, ensure_ascii=False)

# ————— Cálculos nutricionales —————

def calculate_bmr(weight, height, age, sex):
    adj = 5 if sex == 'male' else -161
    return (10 * weight) + (6.25 * height) - (5 * age) + adj

def calculate_iee(bmr, activity_level):
    factors = {
        'sedentary':      1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active':    1.725,
        'extra_active':   1.9
    }
    return bmr * factors.get(activity_level, 1.2)

def calculate_cycling_expenditure(power, hrs, economy=75):
    try:
        return (power / economy) * 5 * hrs * 60
    except:
        return 0

def calculate_running_expenditure(pace, hrs, weight, economy=210):
    try:
        vo2 = (economy / pace) * weight / 1000
        return vo2 * 5 * hrs * 60
    except:
        return 0

def calculate_cho(weight, threshold, intensity, hrs):
    if hrs == 0:
        return round(3 * weight)
    if threshold <= 200: cho = 10
    elif threshold <= 240: cho = 11
    elif threshold <= 270: cho = 12
    elif threshold <= 300: cho = 13
    elif threshold <= 330: cho = 14
    elif threshold <= 360: cho = 15
    else: cho = 16
    tss = (intensity ** 2) * 100 * hrs
    return round((tss * cho) / 4)

def calculate_pro(weight, hrs, loss='no'):
    if loss in ['yes','gain']: factor = 1
    elif hrs < 1: factor = 0.7
    elif hrs < 2: factor = 0.8
    elif hrs < 2.5: factor = 0.9
    else: factor = 1
    return round(weight * 2.2 * factor)

def get_my_nutrition_plan(w, h, age, sex, act,
                         bike_hrs, bike_power, bike_threshold,
                         run_hrs, run_pace, run_threshold,
                         weight_loss='no'):
    bmr = calculate_bmr(w, h, age, sex)
    iee = calculate_iee(bmr, act)
    if weight_loss == 'yes': iee -= 500
    elif weight_loss == 'gain': iee += 500

    bike_kc = calculate_cycling_expenditure(bike_power, bike_hrs)
    run_kc  = calculate_running_expenditure(run_pace, run_hrs, w)
    tot_kc  = iee + bike_kc + run_kc

    try: i_b = bike_power / bike_threshold
    except: i_b = 0
    try: i_r = run_threshold / run_pace
    except: i_r = 0

    hrs = bike_hrs + run_hrs
    avg_if = (i_b * bike_hrs + i_r * run_hrs) / hrs if hrs > 0 else 0

    cho = calculate_cho(w, bike_threshold, avg_if, hrs)
    pro = calculate_pro(w, hrs, weight_loss)
    fat = round((tot_kc - (cho*4 + pro*4)) / 9)

    return {
        'Total Calories': round(tot_kc, 2),
        'CHO': round(cho, 2),
        'Protein': round(pro, 2),
        'Fat': round(fat, 2)
    }

def parse_float(v):
    try: return float(v)
    except: return 0.0

@app.route('/actualizar_datos_usuario', methods=['POST'])
def actualizar_datos_usuario():

    if request.headers.get('Content-Type') == 'application/json':
        print("🔄 Recibida petición JSON para actualizar_datos_usuario")
        data = request.get_json()
        print("📥 Datos recibidos:", data)
        perfil = session.get("perfil", {})

        # Actualizar datos enviados desde el frontend
        perfil["peso"] = float(data.get("peso", perfil.get("peso", 70)))
        perfil["actividad"] = data.get("actividad", perfil.get("actividad", "sedentary"))
        perfil["objetivo"] = data.get("objetivo", perfil.get("objetivo", "no"))
        session["perfil"] = perfil

        # Extraer todos los argumentos que requiere get_my_nutrition_plan
        peso = perfil.get("peso", 70)
        h = perfil.get("altura", 170)
        age = perfil.get("edad", 30)
        sex = perfil.get("sexo", "male")
        act = perfil.get("actividad", "sedentary")
        bike_hrs = perfil.get("bike_hrs", 0)
        bike_power = perfil.get("bike_power", 0)
        bike_threshold = perfil.get("bike_threshold", 0)
        run_hrs = perfil.get("run_hrs", 0)
        run_pace = perfil.get("run_pace", 0)
        run_threshold = perfil.get("run_threshold", 0)

        # Recalcular plan y devolver JSON
        nuevo_plan = get_my_nutrition_plan(peso, h, age, sex, act, bike_hrs, bike_power, bike_threshold, run_hrs, run_pace, run_threshold)
        print("📤 Plan recalculado:", nuevo_plan)
        return jsonify(nuevo_plan)

    perfil = session.get('perfil')
    if not perfil:
        return redirect(url_for('login'))

    # Actualiza los campos desde el formulario
    peso = request.form.get('peso')
    actividad = request.form.get('actividad')
    objetivo = request.form.get('objetivo', 'no')

    # Guardamos en el perfil
    if peso:
        perfil['peso'] = float(peso)
    if actividad:
        perfil['actividad'] = actividad
    if objetivo:
        perfil['objetivo'] = objetivo

    # Guardamos en el archivo
    perfiles = load_perfiles()
    perfiles[perfil['email']] = perfil
    save_perfiles(perfiles)
    session['perfil'] = perfil

    return redirect(url_for('calculadora'))

# ————— Autenticación —————

@app.route('/', methods=['GET'])
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    email = ''
    if request.method == 'POST':
        email = request.form.get('email','').lower().strip()
        pwd   = request.form.get('contrasena','')
        perfiles = load_perfiles()
        perfil = perfiles.get(email)
        if perfil and perfil.get('contrasena') == pwd:
            session['perfil'] = perfil
            return redirect(url_for('calculadora'))
        error = 'Email o contraseña incorrectos.'
    return render_template('login.html', error=error, email=email)

@app.route('/registro', methods=['GET','POST'])
def registro():
    error = None
    if request.method == 'POST':
        nombre    = request.form.get('nombre','').strip()
        email     = request.form.get('email','').lower().strip()
        p1        = request.form.get('contrasena','')
        p2        = request.form.get('contrasena_confirm','')
        fnac      = request.form.get('fecha_nacimiento','')
        sexo      = request.form.get('sexo','')
        altura    = request.form.get('altura','').strip()
        actividad = request.form.get('actividad','sedentary')

        perfiles = load_perfiles()
        if email in perfiles:
            error = 'Este email ya está registrado.'
        elif p1 != p2:
            error = 'Las contraseñas no coinciden.'
        else:
            fn = datetime.strptime(fnac, '%Y-%m-%d').date()
            hoy = datetime.today().date()
            edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))

            perfil = {
                'nombre':      nombre,
                'email':       email,
                'contrasena':  p1,
                'fecha_nacimiento': fnac,
                'edad':        edad,
                'sexo':        sexo,
                'altura':      float(altura) if altura else 0.0,
                'peso':        None,
                'actividad':   actividad,
                'comidas_diarias': {}
            }
            perfiles[email] = perfil
            save_perfiles(perfiles)
            session['perfil'] = perfil
            return redirect(url_for('calculadora'))

    return render_template('registro.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ————— Calculadora —————

@app.route('/calculadora', methods=['GET','POST'])
def calculadora():
    perfil = session.get('perfil')
    if not perfil:
        return redirect(url_for('login'))

    # Plan basal
    basal_plan = get_my_nutrition_plan(
        perfil.get('peso') or 0,
        perfil.get('altura') or 0,
        perfil.get('edad') or 0,
        perfil.get('sexo'),
        perfil.get('actividad','sedentary'),
        0,0,0,0,0,0,'no'
    )

    # Distribución basal
    distrib = {
        'Desayuno': 0.25,
        'Almuerzo': 0.25,
        'Comida':   0.30,
        'Cena':     0.20
    }
    basal_dist = {}
    for meal, pct in distrib.items():
        kcal = round(basal_plan['Total Calories'] * pct, 2)
        basal_dist[meal] = {'calories': kcal, 'percent': round(pct*100,2)}

    # Consumido hoy
    fecha = datetime.today().date().isoformat()
    perfil.setdefault('comidas_diarias', {})
    comidas = perfil['comidas_diarias'].get(fecha, [])
    consumido = {'Total Calories':0, 'CHO':0, 'Protein':0, 'Fat':0}
    for comida in comidas:
        for ing in comida.get('ingredientes', []):
            consumido['Total Calories'] += ing.get('calorias',0)
            consumido['CHO']            += ing.get('carbohidratos',0)
            consumido['Protein']        += ing.get('proteinas',0)
            consumido['Fat']            += ing.get('grasas',0)

    # Restante
    restante = {k: max(0, round(v - consumido[k],2)) for k,v in basal_plan.items()}

    # Plan ajustado (POST)
    adjusted_plan = None
    if request.method == 'POST':
        act = request.form.get('activity_level','sedentary')
        bh  = parse_float(request.form.get('bike_hrs'))
        bp  = parse_float(request.form.get('bike_power'))
        bt  = parse_float(request.form.get('bike_threshold'))
        rh  = parse_float(request.form.get('run_hrs'))
        rp  = parse_float(request.form.get('run_pace'))
        rt  = parse_float(request.form.get('run_threshold'))
        wl  = request.form.get('weight_loss','no')

        adjusted_plan = get_my_nutrition_plan(
            perfil.get('peso') or 0,
            perfil.get('altura') or 0,
            perfil.get('edad') or 0,
            perfil.get('sexo'),
            act, bh, bp, bt, rh, rp, rt, wl
        )
        perfiles = load_perfiles()
        perfil['plan_actual'] = adjusted_plan
        perfiles[perfil['email']] = perfil
        save_perfiles(perfiles)

    return render_template(
        'calculadora.html',
        perfil=perfil,
        basal_plan=basal_plan,
        basal_dist=basal_dist,
        consumido=consumido,
        restante=restante,
        adjusted_plan=adjusted_plan,
        fecha=fecha
    )

@app.route('/api/calcular', methods=['POST'])
def api_calcular():
    perfil = session.get('perfil')
    if not perfil:
        return jsonify({'error':'no autorizado'}), 401
    data = request.get_json()
    act = data.get('activity_level','sedentary')
    bh  = parse_float(data.get('bike_hrs'))
    bp  = parse_float(data.get('bike_power'))
    bt  = parse_float(data.get('bike_threshold'))
    rh  = parse_float(data.get('run_hrs'))
    rp  = parse_float(data.get('run_pace'))
    rt  = parse_float(data.get('run_threshold'))
    wl  = data.get('weight_loss','no')

    adjusted_plan = get_my_nutrition_plan(
        perfil.get('peso') or 0,
        perfil.get('altura') or 0,
        perfil.get('edad') or 0,
        perfil.get('sexo'),
        act, bh, bp, bt, rh, rp, rt, wl
    )
    return jsonify({'adjusted_plan': adjusted_plan})

# ————— Gestión de comidas —————

@app.route('/guardar_comida', methods=['GET','POST'])
def guardar_comida():
    perfil = session.get('perfil')
    if not perfil:
        return redirect(url_for('login'))

    fecha = datetime.today().date().isoformat()
    mensaje = None
    if request.method == 'POST':
        nombre = request.form.get('nombre_comida','').strip()
        ingredientes = []
        for i in range(1, 4):
            ing  = request.form.get(f'ingrediente{i}','').strip()
            cant = parse_float(request.form.get(f'cantidad{i}'))
            cal  = parse_float(request.form.get(f'calorias{i}'))
            carb = parse_float(request.form.get(f'carbohidratos{i}'))
            pro  = parse_float(request.form.get(f'proteinas{i}'))
            fat  = parse_float(request.form.get(f'grasas{i}'))
            if ing and cant and cal:
                ingredientes.append({
                    'nombre':        ing,
                    'cantidad':      cant,
                    'calorias':      cal,
                    'carbohidratos': carb,
                    'proteinas':     pro,
                    'grasas':        fat
                })
        perfil.setdefault('comidas_diarias', {})\
              .setdefault(fecha, []).append({
                  'nombre_comida': nombre,
                  'ingredientes':  ingredientes
              })
        perfiles = load_perfiles()
        perfiles[perfil['email']] = perfil
        save_perfiles(perfiles)
        session['perfil'] = perfil
        mensaje = f'Comida "{nombre}" guardada.'

    return render_template('guardar_comida.html', mensaje=mensaje)

@app.route('/ver_comidas')
def ver_comidas():
    perfil = session.get('perfil')
    if not perfil:
        return redirect(url_for('login'))
    fecha  = datetime.today().date().isoformat()
    comidas = perfil.get('comidas_diarias', {}).get(fecha, [])
    return render_template('ver_comidas.html', comidas=comidas, fecha=fecha)

if __name__ == '__main__':
    app.run(debug=True)