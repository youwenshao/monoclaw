"""Demo data seeder for the Student Dashboard."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.student.seed")


# ---------------------------------------------------------------------------
# StudyBuddy
# ---------------------------------------------------------------------------

SAMPLE_COURSES = [
    {"course_code": "COMP3001", "course_name": "Operating Systems", "semester": "2025-26 Sem 2", "instructor": "Dr. K. Wong"},
    {"course_code": "COMP3271", "course_name": "Computer Graphics", "semester": "2025-26 Sem 2", "instructor": "Prof. L. Chen"},
    {"course_code": "ECON2220", "course_name": "Intermediate Microeconomics", "semester": "2025-26 Sem 2", "instructor": "Dr. M. Lam"},
    {"course_code": "LAWS3000", "course_name": "Administrative Law", "semester": "2025-26 Sem 2", "instructor": "Prof. A. Ho"},
    {"course_code": "FINA2010", "course_name": "Corporate Finance", "semester": "2025-26 Sem 1", "instructor": "Dr. S. Tsang"},
]

SAMPLE_FLASHCARDS = [
    {"course_idx": 0, "question": "What is a deadlock?", "answer": "A situation where two or more processes are waiting for each other to release resources, causing all of them to be stuck indefinitely.", "difficulty": "medium"},
    {"course_idx": 0, "question": "Name the four conditions for deadlock.", "answer": "Mutual exclusion, hold and wait, no preemption, circular wait.", "difficulty": "easy"},
    {"course_idx": 0, "question": "What is the difference between a process and a thread?", "answer": "A process is an independent execution unit with its own memory space. A thread is a lightweight unit within a process that shares the process's memory.", "difficulty": "easy"},
    {"course_idx": 2, "question": "Define marginal rate of substitution.", "answer": "The rate at which a consumer is willing to give up one good in exchange for another while maintaining the same level of utility.", "difficulty": "medium"},
    {"course_idx": 2, "question": "What is the law of diminishing marginal returns?", "answer": "As one input increases while others are held fixed, the additional output from each extra unit of input eventually decreases.", "difficulty": "easy"},
]


def seed_study_buddy(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        if existing > 0:
            logger.info("StudyBuddy already has data, skipping seed")
            return 0

        for c in SAMPLE_COURSES:
            conn.execute(
                "INSERT INTO courses (course_code, course_name, semester, instructor) VALUES (?,?,?,?)",
                (c["course_code"], c["course_name"], c["semester"], c["instructor"]),
            )
            count += 1

        course_ids = [r[0] for r in conn.execute("SELECT id FROM courses ORDER BY id").fetchall()]

        for fc in SAMPLE_FLASHCARDS:
            cid = course_ids[fc["course_idx"]]
            conn.execute(
                "INSERT INTO flashcards (course_id, question, answer, difficulty) VALUES (?,?,?,?)",
                (cid, fc["question"], fc["answer"], fc["difficulty"]),
            )
            count += 1

    logger.info("Seeded %d StudyBuddy records", count)
    return count


# ---------------------------------------------------------------------------
# ExamGenerator
# ---------------------------------------------------------------------------

SAMPLE_EXAMS = [
    {
        "course_idx": 0,
        "title": "COMP3001 Midterm Practice",
        "generation_source": "course_materials",
        "question_count": 10,
        "time_limit_minutes": 60,
        "status": "ready",
    },
]

SAMPLE_EXAM_QUESTIONS = [
    {
        "exam_idx": 0, "question_index": 1, "section": "A",
        "question_type": "mcq", "difficulty": "easy", "topic": "Process Management",
        "question_text": "Which scheduling algorithm gives the minimum average waiting time?",
        "options": json.dumps(["FCFS", "SJF", "Round Robin", "Priority"]),
        "correct_answer": "SJF", "points": 1.0, "bloom_level": "remember",
    },
    {
        "exam_idx": 0, "question_index": 2, "section": "A",
        "question_type": "mcq", "difficulty": "medium", "topic": "Memory Management",
        "question_text": "What is thrashing?",
        "options": json.dumps([
            "Excessive paging causing performance degradation",
            "A type of CPU scheduling",
            "A deadlock resolution technique",
            "A disk scheduling algorithm",
        ]),
        "correct_answer": "Excessive paging causing performance degradation",
        "points": 1.0, "bloom_level": "understand",
    },
    {
        "exam_idx": 0, "question_index": 3, "section": "B",
        "question_type": "short_answer", "difficulty": "medium", "topic": "Deadlocks",
        "question_text": "Explain the banker's algorithm and when it is used.",
        "options": None, "correct_answer": "The banker's algorithm is a deadlock avoidance algorithm that tests for safety by simulating allocation of maximum possible resources, then checks if a safe sequence exists.",
        "points": 3.0, "bloom_level": "understand",
    },
]


def seed_exam_generator(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
        if existing > 0:
            return 0

        for e in SAMPLE_EXAMS:
            conn.execute(
                """INSERT INTO exams (course_id, title, generation_source, question_count, time_limit_minutes, status)
                   VALUES (?,?,?,?,?,?)""",
                (e["course_idx"] + 1, e["title"], e["generation_source"],
                 e["question_count"], e["time_limit_minutes"], e["status"]),
            )
            count += 1

        exam_ids = [r[0] for r in conn.execute("SELECT id FROM exams ORDER BY id").fetchall()]

        for q in SAMPLE_EXAM_QUESTIONS:
            eid = exam_ids[q["exam_idx"]]
            conn.execute(
                """INSERT INTO exam_questions
                   (exam_id, question_index, section, question_type, question_text, options,
                    correct_answer, difficulty, topic, points, bloom_level)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (eid, q["question_index"], q["section"], q["question_type"],
                 q["question_text"], q["options"], q["correct_answer"],
                 q["difficulty"], q["topic"], q["points"], q["bloom_level"]),
            )
            count += 1

    logger.info("Seeded %d ExamGenerator records", count)
    return count


# ---------------------------------------------------------------------------
# ThesisFormatter
# ---------------------------------------------------------------------------

UNIVERSITY_PROFILES = [
    {
        "university": "HKU", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "declaration", "abstract_en", "abstract_tc", "acknowledgments", "toc", "lof", "lot", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "1.5 line spacing, bilingual abstracts required",
    },
    {
        "university": "CUHK", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 2.0,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 38, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "declaration", "abstract_en", "abstract_tc", "acknowledgments", "toc", "lof", "lot", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "Double spacing, left margin 38mm for binding",
    },
    {
        "university": "HKUST", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "declaration", "abstract_en", "acknowledgments", "toc", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "1.5 or double spacing, electronic submission",
    },
    {
        "university": "PolyU", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 40, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "declaration", "abstract_en", "acknowledgments", "toc", "lof", "lot", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "PolyU logo on cover, binding margin 40mm",
    },
    {
        "university": "CityU", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "declaration", "abstract_en", "acknowledgments", "toc", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "CityU-specific cover page template",
    },
    {
        "university": "Generic", "degree_level": "phd",
        "font_name": "Times New Roman", "font_size": 12, "line_spacing": 1.5,
        "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
        "required_sections": json.dumps(["cover", "title", "abstract_en", "toc", "chapter", "bibliography"]),
        "heading_styles": json.dumps({"1": {"font_size": 16, "bold": True}, "2": {"font_size": 14, "bold": True}, "3": {"font_size": 12, "bold": True}}),
        "notes": "Generic fallback profile",
    },
]


def seed_thesis_formatter(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM formatting_profiles").fetchone()[0]
        if existing > 0:
            return 0

        for p in UNIVERSITY_PROFILES:
            conn.execute(
                """INSERT INTO formatting_profiles
                   (university, degree_level, font_name, font_size, line_spacing,
                    margin_top, margin_bottom, margin_left, margin_right,
                    required_sections, heading_styles, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["university"], p["degree_level"], p["font_name"], p["font_size"],
                 p["line_spacing"], p["margin_top"], p["margin_bottom"],
                 p["margin_left"], p["margin_right"], p["required_sections"],
                 p["heading_styles"], p["notes"]),
            )
            count += 1

    logger.info("Seeded %d ThesisFormatter records", count)
    return count


# ---------------------------------------------------------------------------
# InterviewPrep
# ---------------------------------------------------------------------------

SAMPLE_PROBLEMS = [
    {
        "title": "Two Sum", "slug": "two-sum",
        "description": "Given an array of integers nums and an integer target, return indices of the two numbers that add up to target.",
        "difficulty": "easy", "topic": "arrays", "subtopic": "hash_map",
        "example_input": "nums = [2, 7, 11, 15], target = 9",
        "example_output": "[0, 1]",
        "constraints": "2 <= nums.length <= 10^4, -10^9 <= nums[i] <= 10^9",
        "optimal_time_complexity": "O(n)", "optimal_space_complexity": "O(n)",
        "solution_python": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        comp = target - n\n        if comp in seen:\n            return [seen[comp], i]\n        seen[n] = i\n    return []",
        "solution_javascript": "function twoSum(nums, target) {\n  const seen = {};\n  for (let i = 0; i < nums.length; i++) {\n    const comp = target - nums[i];\n    if (comp in seen) return [seen[comp], i];\n    seen[nums[i]] = i;\n  }\n  return [];\n}",
        "hints": json.dumps(["Think about what data structure lets you look up values quickly.", "Use a hash map to store values you've seen.", "For each element, check if target - element exists in the map."]),
        "test_cases": json.dumps([
            {"input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
            {"input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
            {"input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]},
        ]),
    },
    {
        "title": "Valid Parentheses", "slug": "valid-parentheses",
        "description": "Given a string s containing just the characters '(', ')', '{', '}', '[' and ']', determine if the input string is valid.",
        "difficulty": "easy", "topic": "strings", "subtopic": "stack",
        "example_input": 's = "()"',
        "example_output": "true",
        "constraints": "1 <= s.length <= 10^4",
        "optimal_time_complexity": "O(n)", "optimal_space_complexity": "O(n)",
        "solution_python": "def is_valid(s):\n    stack = []\n    mapping = {')': '(', '}': '{', ']': '['}\n    for c in s:\n        if c in mapping:\n            if not stack or stack[-1] != mapping[c]:\n                return False\n            stack.pop()\n        else:\n            stack.append(c)\n    return not stack",
        "solution_javascript": "function isValid(s) {\n  const stack = [];\n  const map = {')': '(', '}': '{', ']': '['};\n  for (const c of s) {\n    if (c in map) {\n      if (!stack.length || stack[stack.length-1] !== map[c]) return false;\n      stack.pop();\n    } else stack.push(c);\n  }\n  return stack.length === 0;\n}",
        "hints": json.dumps(["Consider using a stack data structure.", "Push opening brackets, pop for closing brackets.", "At each closing bracket, check if the top of the stack is the matching opening bracket."]),
        "test_cases": json.dumps([
            {"input": {"s": "()"}, "expected": True},
            {"input": {"s": "()[]{}"}, "expected": True},
            {"input": {"s": "(]"}, "expected": False},
        ]),
    },
    {
        "title": "Maximum Subarray", "slug": "maximum-subarray",
        "description": "Given an integer array nums, find the subarray with the largest sum, and return its sum.",
        "difficulty": "medium", "topic": "arrays", "subtopic": "dynamic_programming",
        "example_input": "nums = [-2,1,-3,4,-1,2,1,-5,4]",
        "example_output": "6",
        "constraints": "1 <= nums.length <= 10^5",
        "optimal_time_complexity": "O(n)", "optimal_space_complexity": "O(1)",
        "solution_python": "def max_subarray(nums):\n    max_sum = cur = nums[0]\n    for n in nums[1:]:\n        cur = max(n, cur + n)\n        max_sum = max(max_sum, cur)\n    return max_sum",
        "solution_javascript": "function maxSubArray(nums) {\n  let maxSum = nums[0], cur = nums[0];\n  for (let i = 1; i < nums.length; i++) {\n    cur = Math.max(nums[i], cur + nums[i]);\n    maxSum = Math.max(maxSum, cur);\n  }\n  return maxSum;\n}",
        "hints": json.dumps(["Think about Kadane's algorithm.", "At each position, decide whether to extend the current subarray or start a new one.", "Track the running sum and reset when it goes negative."]),
        "test_cases": json.dumps([
            {"input": {"nums": [-2, 1, -3, 4, -1, 2, 1, -5, 4]}, "expected": 6},
            {"input": {"nums": [1]}, "expected": 1},
            {"input": {"nums": [5, 4, -1, 7, 8]}, "expected": 23},
        ]),
    },
    {
        "title": "Binary Tree Inorder Traversal", "slug": "binary-tree-inorder",
        "description": "Given the root of a binary tree, return the inorder traversal of its nodes' values.",
        "difficulty": "easy", "topic": "trees", "subtopic": "traversal",
        "example_input": "root = [1,null,2,3]",
        "example_output": "[1,3,2]",
        "constraints": "The number of nodes is in the range [0, 100].",
        "optimal_time_complexity": "O(n)", "optimal_space_complexity": "O(n)",
        "solution_python": "def inorder(root):\n    res = []\n    def dfs(node):\n        if not node: return\n        dfs(node.left)\n        res.append(node.val)\n        dfs(node.right)\n    dfs(root)\n    return res",
        "solution_javascript": "function inorderTraversal(root) {\n  const res = [];\n  function dfs(node) {\n    if (!node) return;\n    dfs(node.left);\n    res.push(node.val);\n    dfs(node.right);\n  }\n  dfs(root);\n  return res;\n}",
        "hints": json.dumps(["Inorder means: left, root, right.", "Use recursion or an iterative approach with a stack.", "The base case is when the node is null."]),
        "test_cases": json.dumps([
            {"input": {"values": [1, None, 2, 3]}, "expected": [1, 3, 2]},
            {"input": {"values": []}, "expected": []},
        ]),
    },
    {
        "title": "Climbing Stairs", "slug": "climbing-stairs",
        "description": "You are climbing a staircase. It takes n steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?",
        "difficulty": "easy", "topic": "dp", "subtopic": "fibonacci",
        "example_input": "n = 3",
        "example_output": "3",
        "constraints": "1 <= n <= 45",
        "optimal_time_complexity": "O(n)", "optimal_space_complexity": "O(1)",
        "solution_python": "def climb_stairs(n):\n    if n <= 2: return n\n    a, b = 1, 2\n    for _ in range(3, n + 1):\n        a, b = b, a + b\n    return b",
        "solution_javascript": "function climbStairs(n) {\n  if (n <= 2) return n;\n  let a = 1, b = 2;\n  for (let i = 3; i <= n; i++) [a, b] = [b, a + b];\n  return b;\n}",
        "hints": json.dumps(["This is a dynamic programming problem.", "The number of ways to reach step n = ways(n-1) + ways(n-2).", "This is essentially the Fibonacci sequence."]),
        "test_cases": json.dumps([
            {"input": {"n": 2}, "expected": 2},
            {"input": {"n": 3}, "expected": 3},
            {"input": {"n": 5}, "expected": 8},
        ]),
    },
    {
        "title": "Number of Islands", "slug": "number-of-islands",
        "description": "Given an m x n 2D binary grid which represents a map of '1's (land) and '0's (water), return the number of islands.",
        "difficulty": "medium", "topic": "graphs", "subtopic": "bfs_dfs",
        "example_input": 'grid = [["1","1","0"],["1","1","0"],["0","0","1"]]',
        "example_output": "2",
        "constraints": "m == grid.length, n == grid[i].length, 1 <= m, n <= 300",
        "optimal_time_complexity": "O(m*n)", "optimal_space_complexity": "O(m*n)",
        "solution_python": "def num_islands(grid):\n    if not grid: return 0\n    rows, cols = len(grid), len(grid[0])\n    count = 0\n    def dfs(r, c):\n        if r < 0 or r >= rows or c < 0 or c >= cols or grid[r][c] == '0': return\n        grid[r][c] = '0'\n        dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1)\n    for r in range(rows):\n        for c in range(cols):\n            if grid[r][c] == '1':\n                count += 1\n                dfs(r, c)\n    return count",
        "solution_javascript": "function numIslands(grid) {\n  let count = 0;\n  const dfs = (r, c) => {\n    if (r<0||r>=grid.length||c<0||c>=grid[0].length||grid[r][c]==='0') return;\n    grid[r][c]='0';\n    dfs(r+1,c); dfs(r-1,c); dfs(r,c+1); dfs(r,c-1);\n  };\n  for (let r=0;r<grid.length;r++)\n    for (let c=0;c<grid[0].length;c++)\n      if(grid[r][c]==='1'){count++;dfs(r,c);}\n  return count;\n}",
        "hints": json.dumps(["Use DFS or BFS to explore connected land cells.", "When you find a '1', increment count and flood-fill to mark all connected land.", "Mark visited cells to avoid counting them again."]),
        "test_cases": json.dumps([
            {"input": {"grid": [["1","1","0"],["1","1","0"],["0","0","1"]]}, "expected": 2},
            {"input": {"grid": [["1","0","1"],["0","0","0"],["1","0","1"]]}, "expected": 4},
        ]),
    },
]


def seed_interview_prep(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        if existing > 0:
            return 0

        for p in SAMPLE_PROBLEMS:
            conn.execute(
                """INSERT INTO problems
                   (title, slug, description, difficulty, topic, subtopic,
                    example_input, example_output, constraints,
                    optimal_time_complexity, optimal_space_complexity,
                    solution_python, solution_javascript, hints, test_cases)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["title"], p["slug"], p["description"], p["difficulty"],
                 p["topic"], p["subtopic"], p["example_input"], p["example_output"],
                 p["constraints"], p["optimal_time_complexity"],
                 p["optimal_space_complexity"], p["solution_python"],
                 p["solution_javascript"], p["hints"], p["test_cases"]),
            )
            count += 1

    logger.info("Seeded %d InterviewPrep records", count)
    return count


# ---------------------------------------------------------------------------
# JobTracker
# ---------------------------------------------------------------------------

SAMPLE_JOB_LISTINGS = [
    {
        "source": "jobsdb", "url": "https://hk.jobsdb.com/job/12345",
        "title": "Graduate Software Engineer", "company": "HSBC Technology",
        "location": "Hong Kong", "district": "Central",
        "salary_min": 25000, "salary_max": 35000,
        "job_type": "graduate_programme", "industry": "Banking/Finance",
        "requirements": json.dumps(["BSc in Computer Science", "Python or Java", "SQL", "Good communication skills"]),
        "skills_required": json.dumps(["python", "java", "sql", "git", "agile"]),
        "benefits": "13th month pay, medical insurance, MPF top-up, 15 days annual leave",
        "language": "en",
        "posted_date": (date.today() - timedelta(days=7)).isoformat(),
        "deadline": (date.today() + timedelta(days=30)).isoformat(),
    },
    {
        "source": "ctgoodjobs", "url": "https://www.ctgoodjobs.hk/job/67890",
        "title": "Junior Data Analyst", "company": "Lalamove",
        "location": "Hong Kong", "district": "Kwun Tong",
        "salary_min": 20000, "salary_max": 28000,
        "job_type": "full_time", "industry": "Technology",
        "requirements": json.dumps(["Bachelor's degree", "Python", "SQL", "Tableau or Power BI"]),
        "skills_required": json.dumps(["python", "sql", "tableau", "excel", "statistics"]),
        "benefits": "Flexible working, medical insurance, stock options",
        "language": "en",
        "posted_date": (date.today() - timedelta(days=3)).isoformat(),
        "deadline": (date.today() + timedelta(days=45)).isoformat(),
    },
    {
        "source": "linkedin", "url": "https://linkedin.com/jobs/view/99999",
        "title": "Associate Consultant (Technology)", "company": "Deloitte HK",
        "location": "Hong Kong", "district": "Wan Chai",
        "salary_min": 22000, "salary_max": 30000,
        "job_type": "graduate_programme", "industry": "Professional Services",
        "requirements": json.dumps(["Bachelor's degree in IT/CS/Engineering", "Analytical skills", "Presentation skills"]),
        "skills_required": json.dumps(["consulting", "analytics", "presentation", "project_management"]),
        "benefits": "13th month pay, exam leave, training budget, 20 days annual leave",
        "language": "en",
        "posted_date": (date.today() - timedelta(days=14)).isoformat(),
        "deadline": (date.today() + timedelta(days=60)).isoformat(),
    },
]


def seed_job_tracker(db_path: str | Path) -> int:
    count = 0
    with get_db(db_path) as conn:
        existing = conn.execute("SELECT COUNT(*) FROM job_listings").fetchone()[0]
        if existing > 0:
            return 0

        for j in SAMPLE_JOB_LISTINGS:
            conn.execute(
                """INSERT INTO job_listings
                   (source, url, title, company, location, district,
                    salary_min, salary_max, job_type, industry,
                    requirements, skills_required, benefits, language,
                    posted_date, deadline)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (j["source"], j["url"], j["title"], j["company"],
                 j["location"], j["district"], j["salary_min"], j["salary_max"],
                 j["job_type"], j["industry"], j["requirements"],
                 j["skills_required"], j["benefits"], j["language"],
                 j["posted_date"], j["deadline"]),
            )
            count += 1

        job_ids = [r[0] for r in conn.execute("SELECT id FROM job_listings ORDER BY id").fetchall()]

        conn.execute(
            """INSERT INTO applications (job_id, stage, match_score, applied_date, notes)
               VALUES (?,?,?,?,?)""",
            (job_ids[0], "interview", 0.85, (date.today() - timedelta(days=5)).isoformat(), "Phone screen went well"),
        )
        count += 1

        conn.execute(
            """INSERT INTO applications (job_id, stage, match_score, notes)
               VALUES (?,?,?,?)""",
            (job_ids[1], "saved", 0.72, "Need to tailor CV for data role"),
        )
        count += 1

    logger.info("Seeded %d JobTracker records", count)
    return count


# ---------------------------------------------------------------------------
# Seed all
# ---------------------------------------------------------------------------

def seed_all(db_paths: dict[str, str | Path]) -> dict[str, int]:
    """Seed demo data for all tools. Returns count of records seeded per tool."""
    return {
        "study_buddy": seed_study_buddy(db_paths["study_buddy"]),
        "exam_generator": seed_exam_generator(db_paths["exam_generator"]),
        "thesis_formatter": seed_thesis_formatter(db_paths["thesis_formatter"]),
        "interview_prep": seed_interview_prep(db_paths["interview_prep"]),
        "job_tracker": seed_job_tracker(db_paths["job_tracker"]),
    }
