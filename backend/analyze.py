"""One-time pipeline: AI summaries for every verified experiment -> data/analysis.json

Run from the repo root:  python -m backend.analyze
Run again whenever the data team adds verified rows.
"""


def main():
    # TODO:
    # 1. Load verified experiments (data.load_experiments)
    # 2. Load existing analysis.json so already-done experiments are skipped
    # 3. For each experiment not yet analyzed:
    #    - send its row (minus source_quote/verified) through ai.ANALYZE_PROMPT
    #    - store the result under its id
    #    - save analysis.json after EACH one, so a crash doesn't lose progress
    #    - if one fails, print it and move on (re-running retries it)
    #    - short sleep between calls to stay under rate limits
    # 4. Print how many experiments are analyzed
    pass


if __name__ == "__main__":
    main()
