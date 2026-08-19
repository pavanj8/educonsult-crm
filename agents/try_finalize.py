#!/usr/bin/env python3
"""Join point after parallel Test + Review jobs (docs/adr/0016).

Reads gate/test/review labels for this iteration. If any are missing,
exits 0 with status `waiting` (the other job will dispatch this again).
If all three are present, runs finalize_iteration.

Usage:
    python agents/try_finalize.py <issue_number> <iteration>
"""
import sys

import github_ticket_utils as ticket_utils


def main():
    issue_number = int(sys.argv[1])
    iteration = int(sys.argv[2])
    status = ticket_utils.try_finalize_iteration(issue_number, iteration)
    print(f"Final status: {status}")


if __name__ == "__main__":
    main()
