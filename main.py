import json
import logging
import multiprocessing as mp
import random
from collections import Counter
from hashlib import sha256

import sqlalchemy
from flask import Flask
from flask import request, jsonify, render_template
from flask_httpauth import HTTPTokenAuth
from sqlalchemy import Column, Integer, String, Sequence
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

import akari.constants
from akari.generator import generate
from akari.z3solver import z3solve

app = Flask(__name__)
auth = HTTPTokenAuth(scheme="Bearer")

tokens = {
    sha256(b"balbinka").hexdigest(): "balbinka",
}

Base = declarative_base()

dblock = mp.Lock()
engine = sqlalchemy.create_engine("sqlite:///puzzle.db?check_same_thread=False", echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()


class Puzzle(Base):
    __tablename__ = "puzzles"
    id = Column(Integer, Sequence("puzzle_id_seq"), primary_key=True)
    width = Column(Integer)
    height = Column(Integer)
    difficulty = Column(String)
    data = Column(String)

    def __str__(self):
        return str((self.id, self.width, self.height, self.difficulty, self.data))


@auth.verify_token
def verify_token(token):
    if token in tokens:
        return tokens[token]


def puzzle_to_dict(puzzle):
    return {
        "empty": akari.constants.N,
        "barrier": akari.constants.B,
        "light": akari.constants.L,
        "numbers": list(range(4)),
        "board": puzzle,
    }


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
    logging.info(f"generating {key}")
    puzzle = json.dumps(generate_puzzle(width, height, difficulty))
    with dblock:
        session.add(Puzzle(width=width, height=height, difficulty=difficulty, data=puzzle))
        session.commit()
    logging.info(f"DONE generating {key}")


@app.route("/json")
@auth.login_required
def request_json():
    width = request.args.get("width", default=5, type=int)
    height = request.args.get("height", default=5, type=int)
    difficulty = request.args.get("difficulty", default="medium", type=str).lower()
    if difficulty not in ["easy", "hard"]:
        difficulty = "medium"
    while True:
        puzzle = session.query(Puzzle).filter(Puzzle.width == width, Puzzle.height == height,
                                              Puzzle.difficulty == difficulty).first()
        if puzzle is None:
            generate_job(width, height, difficulty)
        else:
            with dblock:
                session.delete(puzzle)
                session.commit()
            break
    backlog = session.query(Puzzle).filter(Puzzle.width == width, Puzzle.height == height,
                                           Puzzle.difficulty == difficulty).count()
    response = jsonify(puzzle_to_dict(json.loads(puzzle.data)))
    for _ in range(backlog, 5):
        mp.Process(target=generate_job, args=(width, height, difficulty), daemon=True).start()
    return response


@app.route("/")
@app.route("/index")
def status():
    puzzles = session.query(Puzzle).all()
    kinds = [(p.width, p.height, p.difficulty) for p in puzzles]
    counter = Counter(kinds)
    return render_template("index.html", puzzles=[dict(width=p[0], height=p[1], difficulty=p[2], count=count) for p, count in counter.items()])


if __name__ == "__main__":
    app.run(debug=True, port=8080)
