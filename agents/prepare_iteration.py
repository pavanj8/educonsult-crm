#!/usr/bin/env python3
"""Bumps the agent:iteration-N label on a GitHub Issue and prints the new
iteration number (for the calling workflow step to capture into
$GITHUB_OUTPUT). Run once per workflow invocation, before the Dev Agent.

Usage: python agents/prepare_iteration.py <issue_number>
"""
import sys

import github_ticket_utils as ticket_utils


def main():
    issue_number = int(sys.argv[1])
    issue = ticket_utils.get_issue(issue_number)
    current = ticket_utils.get_current_iteration(issue)
    new_iteration = ticket_utils.start_new_iteration(issue_number, current)
    print(new_iteration)


if __name__ == "__main__":
    main()
