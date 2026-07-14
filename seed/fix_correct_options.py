import asyncio
import os
import sys

# Same path setup as seeders.py, so this can live alongside it and run the
# same way: `cd backend && python seed/fix_correct_options.py`
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db import db

LETTER_TO_INDEX = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}


async def fix_correct_options():
    """
    One-time data repair, NOT a reseed. Every existing Question row is
    inspected; only rows where correctOption is a bare letter (A/B/C/D)
    that doesn't already match one of that question's options are updated,
    resolving the letter to the real option text at that position. Rows
    that are already correct are left untouched. Safe to run more than
    once — a second run will report everything as already correct and
    change nothing.

    This does not touch users, payments, courses, or any other table, and
    does not modify prisma/schema.prisma.
    """
    print("Connecting to database...")
    await db.connect()

    questions = await db.question.find_many()
    print(f"Found {len(questions)} exam question(s). Checking correctOption integrity...\n")

    already_ok = 0
    fixed = 0
    unresolvable = []

    for q in questions:
        options = q.options or []
        current = (q.correctOption or "").strip()

        # Already correct: no action needed.
        if current in options:
            already_ok += 1
            continue

        # The known-broken pattern: correctOption is a bare position-letter
        # instead of the option text itself. Resolve it by index.
        letter = current.upper()
        if letter in LETTER_TO_INDEX and LETTER_TO_INDEX[letter] < len(options):
            real_answer = options[LETTER_TO_INDEX[letter]]
            await db.question.update(
                where={"id": q.id},
                data={"correctOption": real_answer}
            )
            print(f"  Fixed #{q.indexNumber} [{q.category}]: correctOption {current!r} -> {real_answer!r}")
            fixed += 1
        else:
            unresolvable.append(q)

    print(f"\nDone — {already_ok} already correct, {fixed} repaired.")

    if unresolvable:
        print(f"\n{len(unresolvable)} question(s) could NOT be auto-repaired")
        print("(correctOption isn't a recognized letter and doesn't match any option):\n")
        for q in unresolvable:
            print(f"  #{q.indexNumber} [{q.id}] category={q.category!r}")
            print(f"     correctOption={q.correctOption!r}")
            print(f"     options={q.options}")
        print("\nFix these manually: open the question via Edit on the dashboard's")
        print("Exam Questions page and re-pick the correct option from the list.")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(fix_correct_options())