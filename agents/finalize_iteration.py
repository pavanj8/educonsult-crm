#!/usr/bin/env python3
"""Sets the final agent:ready-to-merge / agent:needs-rework label and posts
the summary comment, once Dev + hard gate + Test + Review have all run for
this iteration. Run once per workflow invocation, as the last step.

Usage:
    python agents/finalize_iteration.py <issue_number> <iteration> \\
        --hard-gate true|false --test true|false --review true|false
"""
import argparse

import github_ticket_utils as ticket_utils


def as_bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes", "success")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("issue_number", type=int)
    parser.add_argument("iteration", type=int)
    parser.add_argument("--hard-gate", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--review", required=True)
    args = parser.parse_args()

    status = ticket_utils.finalize_iteration(
        args.issue_number,
        args.iteration,
        hard_gate_passed=as_bool(args.hard_gate),
        test_passed=as_bool(args.test),
        review_passed=as_bool(args.review),
    )
    print(f"Final status: {status}")


if __name__ == "__main__":
    main()
