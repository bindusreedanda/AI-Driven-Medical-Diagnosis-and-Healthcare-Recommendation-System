from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
import json
import requests
import re
from groq import Groq
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from flask_mail import Mail, Message
import os
from flask import send_file
from flask import session, request

app = Flask(__name__)
app.secret_key = "bindu_secret"

# ================= EMAIL =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'bindusree0274@gmail.com'
app.config['MAIL_PASSWORD'] = 'xxxx xxxx xxxx xxxx'

mail = Mail(app)

# ================= GROQ =================
client = Groq(api_key="")

#==================hugging face==================
API_URL = "https://api-inference.huggingface.co/models/google/vit-base-patch16-224"

headers = {
    "Authorization": "Bearer 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"   # 👈 replace with your key
}



# ================= DATABASE =================
import sqlite3

def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bmi_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        gender TEXT,
        height REAL,
        weight REAL,
        bmi REAL,
        category TEXT
    )
    """)

    conn.commit()
    conn.close()

# call this once
init_db()

def init_db():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # 🔥 IMPORTANT (you missed this earlier)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        symptom TEXT,
        disease TEXT,
        doctor TEXT,
        full_report TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_deleted INTEGER DEFAULT 0
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bmi_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        gender TEXT,
        height REAL,
        weight REAL,
        bmi REAL,
        category TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS contact_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        message TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

init_db()

@app.route("/set_language", methods=["POST"])
def set_language():
    lang = request.form.get("lang")
    session["lang"] = lang
    return "", 204

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():

    # 🔥 default language
    if "lang" not in session:
        session["lang"] = "en"

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()

        conn.close()

        if user:
            session["user"] = username
            return redirect("/chatbot")
        else:
            return render_template("login.html", msg="Invalid login")

    return render_template("login.html")

# ================= REGISTER =================
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        try:
            cur.execute("INSERT INTO users(username,password) VALUES(?,?)",(username,password))
            conn.commit()
        except:
            conn.close()
            return render_template("register.html", msg="Username exists")

        conn.close()
        return redirect("/")

    return render_template("register.html")




# ================= CHATBOT =================
@app.route("/chatbot", methods=["GET","POST"])
def chatbot():
    if "lang" not in session:
        session["lang"] = "en"

    if "user" not in session:
        return redirect("/")

    result = None

    if request.method == "POST":

        symptoms = request.form.get("message")
        age = request.form.get("age")

        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": f"""
You are a professional medical AI.

Patient Age Group: {age}

Return ONLY valid JSON.

IMPORTANT:
- Fill ALL fields
- Do NOT leave empty
- Give proper medicine

Format:

{{
"disease":"",
"specialist":"",
"medicine":"",
"diet":"",
"workout":"",
"precautions":"",
"severity":"",
"emergency_signs":""
}}
"""
                    },
                    {"role":"user","content":symptoms}
                ]
            )

            raw = response.choices[0].message.content.strip()

            # CLEAN JSON 🔥
            raw = raw.replace("```json","").replace("```","")

            start = raw.find("{")
            end = raw.rfind("}") + 1
            clean = raw[start:end]

            # REMOVE BAD CHARS
            clean = clean.replace("\n"," ").replace("\r"," ").replace("\t"," ")
            clean = re.sub(r'[\x00-\x1F]+', ' ', clean)

            result = json.loads(clean)

            # 🔥 Ensure all fields exist
            fields = [
                "disease","specialist","medicine","dosage",
                "diet","workout","precautions","severity","emergency_signs"
            ]

            for f in fields:
                if f not in result or result[f] == "":
                    result[f] = "General advice: consult doctor"

            # SAVE
            conn = sqlite3.connect("database.db")
            cur = conn.cursor()

            cur.execute("""
            INSERT INTO history(username,symptom,disease,doctor,full_report)
            VALUES(?,?,?,?,?)
            """,(
                session["user"],
                symptoms,
                result["disease"],
                result["specialist"],
                json.dumps(result)
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            result = {"error": str(e)}

    return render_template("chatbot.html", result=result)

#===============medical report download==========
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import json

@app.route("/download_current", methods=["POST"])
def download_current():

    report = json.loads(request.form.get("report_data"))
    symptoms = request.form.get("symptoms")

    file_path = "medical_report.pdf"

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("Medical Report", styles['Title']))
    content.append(Spacer(1, 12))

# Symptoms
    content.append(Paragraph(f"<b>Symptoms:</b> {symptoms}", styles['Normal']))
    content.append(Spacer(1, 12))

# Disease
    content.append(Paragraph(f"<b>Disease:</b> {report.get('disease')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Severity 🔥
    content.append(Paragraph(f"<b>Severity:</b> {report.get('severity', 'Not available')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Emergency Signs 🚨
    content.append(Paragraph(f"<b>Emergency Signs:</b> {report.get('emergency_signs', 'None')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Specialist
    content.append(Paragraph(f"<b>Specialist:</b> {report.get('specialist', 'General Physician')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Medicine
    content.append(Paragraph(f"<b>Medicine:</b> {report.get('medicine')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Dosage
    content.append(Paragraph(f"<b>Dosage:</b> {report.get('dosage')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Diet
    content.append(Paragraph(f"<b>Diet:</b> {report.get('diet')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Workout 💪
    content.append(Paragraph(f"<b>Workout:</b> {report.get('workout', 'Light exercise')}", styles['Normal']))
    content.append(Spacer(1, 12))

# Precautions
    content.append(Paragraph(f"<b>Precautions:</b> {report.get('precautions')}", styles['Normal']))

    doc.build(content)

    return send_file(file_path, as_attachment=True)

# ================= EMAIL =================
from flask import flash, redirect, url_for

@app.route("/send_email", methods=["POST"])
def send_email():

    email = request.form.get("email")
    report = json.loads(request.form.get("report"))
    symptoms = request.form.get("symptoms")

    msg = Message(
        subject="Your Medical Report",
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )

    msg.body = f"""
Hello,

Symptoms: {symptoms}

Disease: {report.get('disease')}
Medicine: {report.get('medicine')}
Dosage: {report.get('dosage')}
Diet: {report.get('diet')}
Precautions: {report.get('precautions')}

Stay Healthy 😊
"""

    mail.send(msg)

    flash("Email sent successfully ✅")

    return render_template("chatbot.html", result=report)


#======== bmi calculator=========
@app.route("/bmi", methods=["GET", "POST"])
def bmi():

    if "user" not in session:
        return redirect("/")

    bmi = None
    category = None

    if request.method == "POST":

        height = float(request.form.get("height"))
        weight = float(request.form.get("weight"))
        gender = request.form.get("gender")

        # 🔥 username from session
        username = session.get("user")

        print("DEBUG:", username, gender)  # check console

        bmi = weight / ((height / 100) ** 2)

        if bmi < 18.5:
            category = "Underweight"
        elif bmi < 25:
            category = "Normal"
        elif bmi < 30:
            category = "Overweight"
        else:
            category = "Obese"

        import sqlite3
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        cursor.execute("""
        INSERT INTO bmi_data (username, gender, height, weight, bmi, category)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (username, gender, height, weight, bmi, category))

        conn.commit()
        conn.close()

    return render_template("bmi.html", bmi=bmi, category=category)


# ================= NAVIGATION PAGES =================
@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET","POST"])
def contact():
    if "user" not in session:
        return redirect("/")

    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        conn = sqlite3.connect("database.db")
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO contact_messages(name,email,message)
        VALUES(?,?,?)
        """,(name,email,message))

        conn.commit()
        conn.close()

        return render_template("contact.html", success="Message sent successfully!")

    return render_template("contact.html")

@app.route("/developer")
def developer():
    return render_template("developer.html")

@app.route("/blog")
def blog():
    return render_template("blog.html")

@app.route("/dashboard")
def dashboard():

    if "user" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("""
    SELECT disease, COUNT(*)
    FROM history
    WHERE is_deleted=0
    GROUP BY disease
    """)

    data = cur.fetchall()
    conn.close()

    diseases = []
    counts = []

    for row in data:
        diseases.append(row[0])
        counts.append(row[1])

    return render_template(
        "dashboard.html",
        diseases=diseases,
        counts=counts
    )

# ================= HISTORY =================
@app.route("/history")
def history():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("SELECT * FROM history WHERE username=? AND is_deleted=0 ORDER BY date DESC",(session["user"],))
    rows = cur.fetchall()

    conn.close()
    return render_template("history.html", rows=rows)

# ================= DELETE =================
@app.route("/delete/<int:id>")
def delete(id):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("UPDATE history SET is_deleted=1 WHERE id=?",(id,))
    conn.commit()
    conn.close()

    return redirect("/history")

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/", result=result)

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)