#!/usr/bin/env python3
"""Guard: Test/Review run only for the issue+iteration Dev just finished.

Usage: python agents/require_dev_completed.py <issue_number> <iteration>
"""
import sys

import github_ticket_utils as ticket_utils


def main():
    ticket_utils.require_dev_completed(int(sys.argv[1]), int(sys.argv[2]))


if __name__ == "__main__":
    main()
