import pandas as pd
import json
import os
from flask import Flask, request, send_from_directory
from werkzeug.utils import secure_filename
import sqlite3
from flask_cors import CORS
from deepface import DeepFace
dbConnection = sqlite3.connect("db.db", check_same_thread=False)
dbConnection.row_factory = sqlite3.Row
db = dbConnection.cursor()


app = Flask(__name__)
CORS(app)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/')
def home():
    return 'hey!'


def dict_from_row(row):
    return dict(zip(row.keys(), row))


@app.route('/register', methods=['POST'])
def register():
    if 'file' not in request.files:
        return {'status': 'failed'}
    file = request.files['file']
    if file.filename == '':
        return {'status': 'failed'}
    if file:
        extensionFaceImage = secure_filename(file.filename).split('.')[-1]
        filenameFaceImage = str(request.form['usn']) + '.' + extensionFaceImage

        db.execute("INSERT INTO students (usn, password, faceImg, name) VALUES (?,?,?,?)", (
            request.form['usn'], request.form['password'], filenameFaceImage, request.form['name']))
        dbConnection.commit()

        file.save(os.path.join(
            app.config['UPLOAD_FOLDER'], "faceImages", filenameFaceImage))
        return {"status": "success", "data": dict_from_row(db.execute("SELECT * FROM students WHERE usn = ?", (request.form['usn'],)).fetchone())}


@app.route('/login', methods=['POST'])
def login():
    request_data = request.get_json()
    if "usn" in request_data and "password" in request_data:
        result = db.execute("SELECT * FROM students WHERE usn = ? AND password = ?",
                            (request_data['usn'], request_data['password'])).fetchone()
        if result:
            return json.dumps({'status': 'success', 'data': dict_from_row(result)}, indent=4, default=str)
        else:
            return json.dumps({'status': 'failed'}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


@app.route('/create-exam', methods=['POST'])
def createexam():
    if 'file' not in request.files:
        return {'status': 'failed'}
    file = request.files['file']
    if file.filename == '':
        return {'status': 'failed'}
    if file:
        extension = secure_filename(file.filename).split('.')[-1]
        filename = str(request.form['examTitle']) + '.' + extension

        db.execute("INSERT INTO exams (examTitle, questionLink) VALUES (?,?)", (
            request.form['examTitle'], filename))
        dbConnection.commit()

        file.save(os.path.join(
            app.config['UPLOAD_FOLDER'], "qp", filename))
        return {"status": "success"}


@app.route('/get-exams', methods=['GET'])
def getExams():
    exams = db.execute("SELECT * FROM exams").fetchall()

    exams = list(map(dict_from_row, exams))

    return json.dumps({'status': 'success', 'data': exams}, indent=4, default=str)


@app.route('/get-exam', methods=['POST'])
def getExam():
    request_data = request.get_json()
    print(request_data)
    if "id" in request_data:
        exam = db.execute("SELECT * FROM exams WHERE id = ?",
                          (request_data['id'],)).fetchone()
        print(exam)
        exam = dict_from_row(exam)
        if exam:
            return json.dumps({'status': 'success', 'data': exam}, indent=4, default=str)
        else:
            return json.dumps({'status': 'failed'}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


@app.route("/sendqp/<path:filename>", methods=['GET'])
def sendQuestionPaper(filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], "qp")
    return send_from_directory(directory, filename)


@app.route("/sendreport/<path:filename>", methods=['GET'])
def sendReport(filename):
    directory = os.path.join(app.config['UPLOAD_FOLDER'], "reports")
    return send_from_directory(directory, filename, as_attachment=True)


@app.route("/add-attendance", methods=['POST'])
def addAttendance():
    request_data = request.get_json()
    if "eid" in request_data and "uid" in request_data:
        db.execute("INSERT INTO attendance (eid, uid,status) VALUES (?,?, 'absent')", (
            request_data['eid'], request_data['uid']))
        dbConnection.commit()
        return json.dumps({'status': 'success'}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


@app.route("/enable-exam", methods=['POST'])
def enableExam():
    request_data = request.get_json()
    if "eid" in request_data:
        db.execute("UPDATE exams SET isEnabled = 1 WHERE id = ?", (
            request_data['eid'],))
        dbConnection.commit()
        return json.dumps({'status': 'success'}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


@app.route("/disable-exam", methods=['POST'])
def disableExam():
    request_data = request.get_json()
    if "eid" in request_data:
        db.execute("UPDATE exams SET isEnabled = 0 WHERE id = ?", (
            request_data['eid'],))
        dbConnection.commit()
        return json.dumps({'status': 'success'}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


@app.route("/verify", methods=['POST'])
def verify():
    if 'file' not in request.files:
        return 'No file part'
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    if file:
        extension = secure_filename(file.filename).split('.')[-1]
        filename = str(request.form['usn']) + '.' + extension
        file.save(os.path.join(
            app.config['UPLOAD_FOLDER'], "tocheck", filename))
        result = DeepFace.verify(os.path.join(
            app.config['UPLOAD_FOLDER'], "tocheck", filename), os.path.join(app.config['UPLOAD_FOLDER'], "faceImages", db.execute("SELECT faceImg FROM students WHERE usn = ?", (request.form['usn'],)).fetchone()[0]), enforce_detection=False)
        if result['verified']:
            # update attendance
            db.execute("Update attendance SET status = 'present' WHERE uid = ? AND eid = ?",
                       (request.form['uid'], request.form['eid']))
            dbConnection.commit()
        return json.dumps(result, indent=4, default=str)


@app.route("/generate-report", methods=['POST'])
def generateReport():
    request_data = request.get_json()
    if "eid" in request_data:
        result = db.execute(
            "SELECT * FROM attendance WHERE eid = ?", (request_data['eid'],)).fetchall()
        result = list(map(dict_from_row, result))
        # get all student names
        for i in range(len(result)):
            result[i]['name'] = db.execute(
                "SELECT name FROM students WHERE id = ?", (result[i]['uid'],)).fetchone()[0]

        pd.DataFrame(result).to_csv(
            "uploads/reports/" + str(request_data['eid'])+".csv")

        d = {
            "absent": [],
            "present": []
        }
        for i in range(len(result)):
            if result[i]['status'] == 'absent':
                d['absent'].append(result[i])
            else:
                d['present'].append(result[i])
        return json.dumps({'status': 'success', 'data': d}, indent=4, default=str)
    else:
        return json.dumps({'status': 'failed'}, indent=4, default=str)


if __name__ == "__main__":
    app.run(port=3000, debug=True)
