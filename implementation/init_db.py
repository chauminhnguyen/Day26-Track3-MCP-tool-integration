from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).with_name("lab.db")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    age INTEGER NOT NULL,
    score REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester TEXT NOT NULL,
    FOREIGN KEY(student_id) REFERENCES students(id),
    FOREIGN KEY(course_id) REFERENCES courses(id)
);
"""

SEED_SQL = """
INSERT INTO students (name, cohort, age, score) VALUES
('Alice Nguyen', 'A1', 20, 91.5),
('Bao Tran', 'A1', 21, 85.0),
('Chi Le', 'A2', 20, 88.0),
('Dung Pham', 'A2', 22, 79.5);

INSERT INTO courses (code, title) VALUES
('MCP101', 'Intro to MCP'),
('DB201', 'Applied Databases'),
('AI250', 'AI Systems Lab');

INSERT INTO enrollments (student_id, course_id, semester) VALUES
(1, 1, '2026S'),
(1, 2, '2026S'),
(2, 1, '2026S'),
(3, 3, '2026S'),
(4, 2, '2026S');
"""


def create_database(db_path: str | Path = DEFAULT_DB_PATH, reset: bool = True) -> Path:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()

    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()

    return path


if __name__ == "__main__":
    created_path = create_database()
    print(f"Database ready at: {created_path}")
