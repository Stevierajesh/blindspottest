"""BlindSpot CLI.

    python main.py http://localhost:3000/profile

Pipeline, in order, each stage owning exactly one decision:

    discovery   what is on the page
    semantic    which interactions look like persistent state   (LLM)
    knowledge   which invariant applies, and what it requires   (rule base)
    knowledge   rule + concrete elements -> executable instance
    runner      execute it against the browser                  (no LLM)
    knowledge   did the relation hold                           (rule base)
    reporting   terminal output + runs/<timestamp>.json

Nobody tells BlindSpot which field to test.

WARNING: BlindSpot writes to the application it tests. Point it at a
development or staging environment only. Original values are restored after
each test, but restoration is best-effort — a crashed browser or a page that
fails mid-teardown can leave a marker value behind.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from discovery.page_inspector import inspect_with_page
from knowledge.engine import KnowledgeEngine
from reporting.reporter import (
    ConsoleReporter,
    build_entry,
    build_record,
    write_record,
)
from runner.persistence_runner import PersistenceRunner
from semantic.classifier import backend_for, classify
from semantic.schemas import CandidateSet


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="blindspot",
        description="Find persistence blindspots in a web application.",
    )
    p.add_argument("url", help="page to test (development/staging only)")
    p.add_argument("--provider", help="LLM provider (default: anthropic)")
    p.add_argument("--model", help="model id, e.g. claude-sonnet-5")
    p.add_argument("--headed", action="store_true", help="show the browser")
    p.add_argument("--seed", type=int, help="fix mutation values for reproducibility")
    p.add_argument(
        "--candidates",
        type=Path,
        help="load candidates from a JSON file instead of calling the LLM "
        "(re-run a page without paying for classification)",
    )
    p.add_argument(
        "--save-candidates",
        type=Path,
        help="write the classifier's candidates to a file for later --candidates use",
    )
    p.add_argument("--runs-dir", type=Path, default=Path("runs"))
    p.add_argument("--no-restore", action="store_true",
                   help="skip teardown (leaves marker values in the app)")
    p.add_argument("--timeout", type=int, default=10_000, help="per-step ms")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    from playwright.sync_api import sync_playwright

    console = ConsoleReporter()
    console.header(args.url)

    engine = KnowledgeEngine.load()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        try:
            page = browser.new_page()
            page.goto(args.url, timeout=args.timeout, wait_until="domcontentloaded")
            snapshot = inspect_with_page(page)
            console.inspected(snapshot)

            # --- semantic mapping (the only LLM call in the pipeline) -------
            if args.candidates:
                candidates = CandidateSet.model_validate_json(
                    args.candidates.read_text()
                ).candidates
                model_name = f"file:{args.candidates}"
                console.analyzing(model_name)
                console.classified(
                    type("R", (), {"candidates": candidates, "rejected": []})()
                )
            else:
                backend = backend_for(args.provider, args.model)
                console.analyzing(backend.model)
                try:
                    classification = classify(snapshot, backend=backend)
                except Exception as exc:
                    # Each SDK signals "no credentials" with its own exception
                    # type, so match on the message rather than the class.
                    text = str(exc).lower()
                    if not any(
                        marker in text
                        for marker in ("credential", "api_key", "api key", "authentication")
                    ):
                        raise
                    key = (
                        "OPENAI_API_KEY"
                        if type(backend).__name__.startswith("OpenAI")
                        else "ANTHROPIC_API_KEY"
                    )
                    print(
                        f"\nNo API credentials found for provider "
                        f"'{type(backend).__name__}' (model {backend.model}).\n\n"
                        f"  Put it in .env:   {key}=...\n"
                        f"  Or export it:     export {key}=...\n"
                        f"  Or skip the LLM:  --candidates <file.json>\n\n"
                        f"  Copy .env.example to .env to get started.\n",
                        file=sys.stderr,
                    )
                    return 2
                candidates = classification.candidates
                model_name = classification.model
                console.classified(classification)
                if args.save_candidates:
                    args.save_candidates.write_text(
                        CandidateSet(candidates=candidates).model_dump_json(indent=2)
                    )

            if not candidates:
                console.summary([], None)
                return 0

            # --- rule base: which invariant, and is it applicable -----------
            instances, skipped = engine.instantiate(
                candidates, snapshot, seed=args.seed
            )
            for skip in skipped:
                console.skipped(skip)
            if skipped:
                print()

            if args.no_restore:
                instances = [
                    type(i)(**{**i.__dict__, "teardown": ()}) for i in instances
                ]

            by_field = {c.field_id: c for c in candidates}
            runner = PersistenceRunner(page, timeout_ms=args.timeout)

            entries, verdicts = [], []
            for index, instance in enumerate(instances, start=1):
                candidate = by_field[instance.target.element_id]
                console.candidate(index, instance, candidate)

                result = runner.run(instance)
                console.testing(result)

                verdict = engine.evaluate(engine.get(instance.invariant),
                                          result.observations)
                console.verdict(verdict, result)

                verdicts.append(verdict)
                entries.append(build_entry(instance, candidate, result, verdict))

        finally:
            browser.close()

    record = build_record(args.url, model_name, entries, skipped)
    path = write_record(record, args.runs_dir)
    console.summary(verdicts, path)

    # Non-zero exit when something needs a human to look at it.
    return 1 if record["summary"]["violations"] else 0


if __name__ == "__main__":
    sys.exit(main())
