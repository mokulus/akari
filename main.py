import json
import multiprocessing as mp
import random
import sqlite3
from hashlib import sha256

from flask import Flask
from flask import request, jsonify
from flask_httpauth import HTTPTokenAuth

import akari.constants
from akari.generator import generate
from akari.z3solver import z3solve

app = Flask(__name__)
auth = HTTPTokenAuth(scheme="Bearer")

tokens = {
    sha256(b"balbinka").hexdigest(): "balbinka",
}

dblock = mp.Lock()


@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]


def puzzle_to_str(puzzle):
    string = ""
    for y in range(len(puzzle)):
        for x in range(len(puzzle[y])):
            if puzzle[y][x] == akari.constants.N:
                string += "."
            elif puzzle[y][x] == akari.constants.B:
                string += "B"
            else:
                string += str(puzzle[y][x])
        string += "\n"
    return string


def puzzle_to_dict(puzzle):
    return {
        "empty": akari.constants.N,
        "barrier": akari.constants.B,
        "light": akari.constants.L,
        "numbers": list(range(4)),
        "board": puzzle,
    }


def generate_puzzle_string(width, height):
    return puzzle_to_str(generate(height, width, seed=random.randrange(0, 2 ** 32)))


def difficulty_data(difficulty, width, height):
    if difficulty == "hard":
        start = width * height // 5
    elif difficulty == "easy":
        start = 1
    else:
        start = max(width, height)
    return {
        "start": start,
        "step": 1
    }


def generate_puzzle(width, height, difficulty):
    return generate(
        height,
        width,
        seed=random.randrange(0, 2 ** 32),
        **difficulty_data(difficulty, width, height)
    )


def generate_job(width, height, difficulty):
    key = str((width, height, difficulty))
    print(f"generating {key}")
    puzzle = json.dumps(generate_puzzle(width, height, difficulty))
    with dblock:
        cur.execute("INSERT INTO puzzles VALUES (?, ?, ?, ?)", (width, height, difficulty, puzzle))
        cur.connection.commit()
    print(f"DONE generating {key}")


@app.route("/json")
@auth.login_required
def request_json():
    width = request.args.get("width", default=5, type=int)
    height = request.args.get("height", default=5, type=int)
    difficulty = request.args.get("difficulty", default="medium", type=str).lower()
    if difficulty not in ["easy", "hard"]:
        difficulty = "medium"
    while True:
        res = cur.execute("SELECT rowid, data FROM puzzles WHERE width = ? AND height = ? AND difficulty = ? LIMIT 1",
                          (width, height, difficulty)).fetchone()
        if res is None:
            generate_job(width, height, difficulty)
        else:
            rowid, data = res
            puzzle = json.loads(data)
            with dblock:
                cur.execute("DELETE FROM puzzles WHERE rowid = ?", (rowid,))
                cur.connection.commit()
            break
    backlog = cur.execute("SELECT COUNT(*) FROM puzzles WHERE width = ? AND height = ? AND difficulty = ?",
                          (width, height, difficulty)).fetchone()[0]
    response = jsonify(puzzle_to_dict(puzzle))
    for _ in range(backlog, 5):
        mp.Process(target=generate_job, args=(width, height, difficulty), daemon=True).start()
    return response


@app.route("/")
@app.route("/index")
def status():
    text = "<table>"
    text += "<tr>"
    for h in ["width", "height", "difficulty", "n"]:
        text += f"<th>{h}</th>"
    text += "</tr>"
    for w in range(5, 11):
        for h in range(5, 11):
            for d in ["easy", "medium", "hard"]:
                n = cur.execute("SELECT COUNT(*) FROM puzzles WHERE width = ? AND height = ? AND difficulty = ?",
                                (w, h, d)).fetchone()[0]
                if n != 0:
                    text += "<tr>"
                    text += f"<td>{w}</td>"
                    text += f"<td>{h}</td>"
                    text += f"<td>{d}</td>"
                    text += f"<td>{n}</td>"
                    text += "</tr>"
    return text


@app.route("/solve", methods=["POST"])
@auth.login_required
def solve():
    data = request.get_json(force=True)
    if data is None:
        raise ValueError("invalid json in /solve")
    solution = z3solve(data["board"])
    if solution is None:
        raise ValueError("unsolvable board")
    for x, y in solution:
        data["board"][y][x] = akari.constants.L
    return data


if __name__ == "__main__":
    con = sqlite3.connect("puzzle.db", check_same_thread=False)
    con.execute("CREATE TABLE IF NOT EXISTS puzzles (width INT, height INT, difficulty TEXT, data TEXT)")
    cur = con.cursor()
    app.run(debug=True, port=8080)
