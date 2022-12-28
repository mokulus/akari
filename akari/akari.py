from generator import generate
from tracksolver import *
from z3solver import z3solve


def main():
    # puzzle = loadcodex('misc/internet/10x10_easy', 0, 10)
    puzzle = generate(10, 10)
    solution = z3solve(puzzle)

    display(puzzle, solution)
    # draw(puzzle, 'puzzle', solution = solution, magnifier = 300)


if __name__ == '__main__':
    main()
