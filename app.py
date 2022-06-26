import datetime
import random
from flask import Flask, g
from flask import jsonify
from flask import request

from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager
from flask_cors import CORS

import pymysql
import json
import pandas as pd
from os.path import exists

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = "super-secret"  # Change this!
jwt = JWTManager(app)


def connect_db():
    return pymysql.connect(
        host='db',
        user='hs', password='Xiaowu21', database='lixiang',
        autocommit=True, charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor)


def get_db():
    '''Opens a new database connection per request.'''
    if not hasattr(g, 'db'):
        g.db = connect_db()
    return g.db


@app.teardown_appcontext
def close_db(error):
    '''Closes the database connection at the end of request.'''
    if hasattr(g, 'db'):
        g.db.close()

questions = None


@app.route("/login", methods=["POST"])
def login():
    username = request.json.get("username", '').strip()
    if not username:
        return jsonify(access_token=''), 400
    access_token = create_access_token(identity=username, expires_delta=datetime.timedelta(days=365))
    return jsonify(access_token=access_token)


@app.route("/questions", methods=["GET"])
@jwt_required()
def get_questions():
    global questions
    if exists('question.json'):
        with open('question.json', 'r') as f:
            questions = json.load(f)
        return jsonify(questions), 200

    if questions:
        if request.args.get('shuffle') == 't':
            random.shuffle(questions)
            with open('question.json', 'w') as f:
                json.dump(questions, f)
        return jsonify(questions), 200

    df = pd.read_sql('select * from questions', con=get_db())
    questions = df.to_dict(orient='records')
    random.shuffle(questions)
    with open('question.json', 'w') as f:
        json.dump(questions, f)
    return jsonify(questions), 200


@app.route("/questionsShuffle", methods=["GET"])
@jwt_required()
def questions_shuffle():
    global questions
    with open('question.json', 'r') as f:
        questions = json.load(f)
    random.shuffle(questions)
    with open('question.json', 'w') as f:
        json.dump(questions, f)
    return '', 200


@app.route("/question", methods=["GET"])
@jwt_required()
def get_question():
    user = get_jwt_identity()
    cur = get_db().cursor()
    question_id = request.args.get('id')
    result = {}
    sql = "select count(question_id) as important from important where user_id = %s and question_id = %s"
    cur.execute(sql, (user, question_id))
    rv = cur.fetchall()
    result['important'] = bool(rv[0]['important'])
    sql = 'select pass, count(pass) as count from answer_log where user_id = %s and question_id = %s group by pass;'
    cur.execute(sql, (user, question_id))
    rv = cur.fetchall()
    for a in rv:
        if a.get('pass') == 1:
            result['correct'] = a['count']
        elif a.get('pass') == 0:
            result['wrong'] = a['count']
        elif a.get('pass') == 2:
            result['unanswer'] = a['count']
    return json.dumps(result), 200


@app.route("/answer", methods=["PUT"])
@jwt_required()
def put_answer():
    sql = "INSERT INTO `answer_log` (`question_id`, `answer`, `pass`, `user_id`) VALUES (%s, %s, %s, %s)"
    user = get_jwt_identity()
    con = get_db()
    cur = con.cursor()
    cur.execute(sql, (request.json['id'], request.json['a'], request.json['p'], user))
    con.commit()
    return '', 200


@app.route("/important", methods=["PUT"])
@jwt_required()
def put_important():
    user = get_jwt_identity()
    sql = "INSERT INTO `important` (`question_id`, `user_id`) VALUES (%s, %s)" \
        if request.json['important'] \
        else "DELETE FROM `important` where `question_id` = %s and user_id = %s"
    con = get_db()
    cur = con.cursor()
    cur.execute(sql, (request.json['id'], user))
    con.commit()
    return '', 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5123, debug=True)
