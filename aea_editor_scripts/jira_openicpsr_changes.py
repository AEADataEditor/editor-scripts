#!/usr/bin/env python3
"""Detect author activity on openICPSR deposits behind "Pending openICPSR changes".

For every AEAREP ticket sitting in that status, this asks openICPSR what has
happened to the deposit since the ticket entered it. If the author did anything
meaningful, the ticket gets a comment and moves to "Assess openICPSR changes".
If the author changed files *and* re-submitted the deposit, the Bitbucket
re-ingest pipeline is triggered as well.

Dry run is the default; writes require --apply.

Environment:
    JIRA_USERNAME, JIRA_API_KEY   Jira Cloud credentials
    ICPSR_EMAIL, ICPSR_PASS       openICPSR account
    ICPSR_TOKEN                   optional Cloudflare bypass token
    P_BITBUCKET_PAT               Bitbucket API token
    P_BITBUCKET_EMAIL             Atlassian email (falls back to JIRA_USERNAME)
"""

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from jira import JIRA

from aea_editor_scripts import openicpsr_classify as classify
from aea_editor_scripts.aeagit_create import trigger_pipeline, workspace
from aea_editor_scripts.openicpsr_activity import fetch_activity, login

JIRA_URL = "https://aeadataeditors.atlassian.net"
PROJECT = "AEAREP"
DEPOSIT_FIELD = "openICPSR Project Number"
REPO_FIELD = "Bitbucket short name"

PENDING_STATUS = "Pending openICPSR changes"
TRANSITION_NAME = "Changes received"
TARGET_STATUS = "Assess openICPSR changes"

# Written into every comment so a re-run can tell it already reported this
# situation. Needed because a ticket whose transition failed stays in the
# pending status and would otherwise be commented on again every run.
MARKER = "{{openicpsr-change-detector}}"

# Metadata or communication alone is normal churn in the fortnight after we ask
# for revisions. Only once it has gone stale is it worth a human's attention.
METADATA_ONLY_MIN_DAYS = 14

BASELINE_REVISION_REQUESTED = "revision-requested"
BASELINE_JIRA = "jira-transition"

BUCKET_ORDER = (
    classify.CONTENT,
    classify.METADATA,
    classify.COMMUNICATION,
    classify.WORKFLOW,
    classify.PASSIVE,
    classify.UNKNOWN,
)


def entered_status(issue, status_name):
    """When the issue most recently entered ``status_name``, or None.

    Jira reports ``created`` with a ``-0400`` style offset, which
    ``datetime.fromisoformat`` handles on Python 3.11+.
    """
    changelog = getattr(issue, "changelog", None)
    if changelog is None:
        return None
    latest = None
    for history in getattr(changelog, "histories", []):
        for item in getattr(history, "items", []):
            if getattr(item, "field", None) != "status":
                continue
            if getattr(item, "toString", None) != status_name:
                continue
            moment = datetime.fromisoformat(history.created)
            if latest is None or moment > latest:
                latest = moment
    return latest


def resolve_baseline(log, cutoff):
    """The moment the author's response window opens, and where it came from.

    Preferred: the last time we sent the deposit back for revision. That is the
    request the author is answering, and it is usually within a day of the Jira
    transition either way. Falls back to the Jira transition when the deposit has
    no revision request in its log -- either because we never sent one, or
    because the 1000-event cap dropped it.
    """
    last = classify.last_revision_requested(log.events)
    if last is not None:
        return last, BASELINE_REVISION_REQUESTED
    return cutoff, BASELINE_JIRA


def decide(assessment, days_since_baseline):
    """Whether to act on this ticket, and why. Returns (act, reason)."""
    if assessment.resubmitted:
        return True, "the author re-submitted the deposit after our revision request"
    if assessment.content_changed:
        return True, "file content changed"
    stale = sum(assessment.counts.get(b, 0)
                for b in (classify.METADATA, classify.COMMUNICATION, classify.WORKFLOW))
    if stale:
        if days_since_baseline >= METADATA_ONLY_MIN_DAYS:
            return True, (f"metadata/communication only, but {days_since_baseline} days "
                          f"have passed since our revision request")
        return False, (f"metadata/communication only, and only {days_since_baseline} days "
                       f"since our revision request (under {METADATA_ONLY_MIN_DAYS})")
    return False, "no author activity"


def marker_line(baseline):
    """The machine-readable line identifying one report."""
    return f"{MARKER} baseline={baseline.isoformat()}"


def last_report_time(issue, baseline):
    """When we last reported on this baseline, or None if we never did."""
    line = marker_line(baseline)
    comments = getattr(getattr(issue.fields, "comment", None), "comments", []) or []
    times = [datetime.fromisoformat(c.created) for c in comments
             if line in (getattr(c, "body", "") or "")]
    return max(times) if times else None


def already_reported(issue, baseline, reassess_after=None):
    """True when this baseline has been reported and the report is still current.

    Without ``reassess_after`` one report per baseline is final. With it, a
    report that has aged past that many days no longer suppresses a new one, so
    a ticket that sits in the status keeps being revisited instead of going
    quiet forever.
    """
    reported_at = last_report_time(issue, baseline)
    if reported_at is None:
        return False
    if reassess_after is None:
        return True
    age = (datetime.now(reported_at.tzinfo) - reported_at).days
    return age < reassess_after


def render_comment(assessment, log, baseline, pipeline_note, baseline_source=BASELINE_JIRA,
                   reason="", reassessed_after_days=None):
    """Build the Jira wiki-markup comment body."""
    origin = ("our last openICPSR revision request"
              if baseline_source == BASELINE_REVISION_REQUESTED
              else f"this ticket entering *{PENDING_STATUS}*")
    lines = [
        f"openICPSR activity detected since {origin} ({baseline.isoformat()}).",
        "",
    ]
    if reassessed_after_days is not None:
        lines.append(f"This is a re-assessment: the previous report on this baseline was "
                     f"{reassessed_after_days} days ago and the ticket is still open.")
        lines.append("")
    if reason:
        lines.append(f"Acting because {reason}.")
        lines.append("")

    counted = [(b, assessment.counts[b]) for b in BUCKET_ORDER if assessment.counts.get(b)]
    if counted:
        lines.append("||Category||Events||")
        lines.extend(f"|{bucket}|{count}|" for bucket, count in counted)
        lines.append("")

    last = assessment.last_workflow
    if last:
        lines.append(
            f"Deposit workflow is now *{last.to_state}* "
            f"(from {last.from_state}, by {last.user}, {last.time.isoformat()})."
        )
        if last.note:
            lines.append("Their note:")
            lines.append("{quote}")
            lines.append(last.note)
            lines.append("{quote}")
        lines.append("")

    if pipeline_note:
        lines.append(pipeline_note)
        lines.append("")

    if log.truncated:
        lines.append(
            f"(!) openICPSR reported {log.total} events but returned only "
            f"{len(log.events)} — the log is truncated, so this summary may "
            f"undercount. The most recent events are always included."
        )
        lines.append("")

    if assessment.unknown_kinds:
        kinds = ", ".join(f"{k} ({v})" for k, v in sorted(assessment.unknown_kinds.items()))
        lines.append(
            f"(?) Unrecognised activity kinds, ignored by this check: {kinds}. "
            f"These did not trigger any action."
        )
        lines.append("")

    lines.append(marker_line(baseline))
    return "\n".join(lines)


@dataclass
class Result:
    """What happened to one ticket."""

    key: str
    status: str
    reason: str = ""
    pid: str = ""
    counts: dict = field(default_factory=dict)
    unknown_kinds: dict = field(default_factory=dict)
    resubmitted: bool = False
    content_changed: bool = False
    pipeline: str = ""
    baseline: str = ""
    baseline_source: str = ""
    days_since_baseline: int = 0
    truncated: bool = False
    reassessed: bool = False
    note: str = ""

    @property
    def exceptions(self):
        """Things a human should look at, beyond the verdict itself."""
        out = []
        if self.status in ("skipped", "failed"):
            out.append(self.reason)
        if self.baseline_source == BASELINE_JIRA and self.pid:
            out.append("no revision request in the log; baseline fell back to the "
                       "Jira transition")
        if self.truncated:
            out.append("openICPSR log truncated at 1000 events; an older revision "
                       "request may have been hidden")
        if self.unknown_kinds:
            out.append("unrecognised activity: " + ", ".join(sorted(self.unknown_kinds)))
        return out

    @property
    def failed(self):
        return self.status == "failed"


def get_jira_client():
    """Authenticated Jira client, following the pattern in jira_purge_query."""
    username = os.environ.get("JIRA_USERNAME")
    api_key = os.environ.get("JIRA_API_KEY")
    if not username or not api_key:
        raise RuntimeError("JIRA_USERNAME and JIRA_API_KEY must be set")
    return JIRA(server=JIRA_URL, basic_auth=(username, api_key), options={"verify": True})


def build_field_map(jira):
    """Map Jira field names to their ids."""
    return {f["name"]: f["id"] for f in jira.fields()}


def field_value(issue, field_map, name):
    """Value of a named custom field, or None."""
    field_id = field_map.get(name)
    return getattr(issue.fields, field_id, None) if field_id else None


def deposit_number(issue, field_map):
    """The openICPSR project number as a string.

    Jira stores it as a float, so 251458.0 has to become "251458".
    """
    value = field_value(issue, field_map, DEPOSIT_FIELD)
    if value in (None, ""):
        return None
    try:
        return str(int(float(value)))
    except (TypeError, ValueError):
        return None


def find_issues(jira, keys=None, limit=None):
    """Issues to consider, with changelog and comments expanded."""
    if keys:
        jql = f"key in ({', '.join(keys)})"
    else:
        jql = f'project = {PROJECT} AND status = "{PENDING_STATUS}" ORDER BY updated DESC'
    issues = jira.search_issues(jql, maxResults=False, expand="changelog")
    return issues[:limit] if limit else issues


def transition_by_name(jira, issue, name):
    """Transition an issue by transition name. Returns (ok, detail)."""
    try:
        available = jira.transitions(issue)
    except Exception as exc:
        return False, f"could not list transitions: {exc}"
    for transition in available:
        if transition["name"].lower() == name.lower():
            try:
                jira.transition_issue(issue, transition["id"])
                return True, ""
            except Exception as exc:
                return False, str(exc)
    names = [t["name"] for t in available]
    return False, f"transition '{name}' not available (offered: {names})"


def _pipeline_note(assessment, triggered, detail):
    """The sentence about re-ingestion that goes into the comment."""
    if not assessment.content_changed:
        return "No file content changed, so no re-ingest was started."
    if not assessment.resubmitted:
        return (
            "File content changed, but the deposit has not been re-submitted "
            "(workflow is not SUBMITTED), so the author appears to still be "
            "working. No re-ingest was started."
        )
    if triggered:
        return f"File content changed and the deposit was re-submitted. {detail}"
    return f"File content changed and the deposit was re-submitted, but {detail}"


def process_issue(jira, field_map, session, issue, apply_changes, bitbucket_auth,
                  reassess_after=None):
    """Assess one ticket and, when applying, act on it."""
    key = issue.key
    pid = deposit_number(issue, field_map)
    if not pid:
        return Result(key, "skipped", f"no {DEPOSIT_FIELD}")

    cutoff = entered_status(issue, PENDING_STATUS)
    if not cutoff:
        return Result(key, "skipped", f"never entered {PENDING_STATUS}", pid=pid)

    try:
        log = fetch_activity(session, pid)
    except Exception as exc:
        return Result(key, "failed", f"openICPSR fetch failed: {exc}", pid=pid)

    baseline, baseline_source = resolve_baseline(log, cutoff)
    after = [e for e in log.events if e.time > baseline]
    assessment = classify.assess(after)
    days = (datetime.now(baseline.tzinfo) - baseline).days
    act, reason = decide(assessment, days)

    common = dict(
        pid=pid, counts=assessment.counts, unknown_kinds=assessment.unknown_kinds,
        resubmitted=assessment.resubmitted, content_changed=assessment.content_changed,
        baseline=baseline.isoformat(), baseline_source=baseline_source,
        days_since_baseline=days, truncated=log.truncated,
    )

    if not act:
        return Result(key, "no-change", reason, **common)
    if already_reported(issue, baseline, reassess_after):
        return Result(key, "already-reported", reason, **common)

    previous = last_report_time(issue, baseline)
    reassessed_days = None
    if previous is not None:
        reassessed_days = (datetime.now(previous.tzinfo) - previous).days

    if not apply_changes:
        status = "would-reassess" if reassessed_days is not None else "would-act"
        return Result(key, status, reason, reassessed=reassessed_days is not None, **common)

    triggered, detail = False, ""
    if assessment.content_changed and assessment.resubmitted:
        slug = field_value(issue, field_map, REPO_FIELD)
        if not slug:
            detail = f"the {REPO_FIELD} field is empty, so no pipeline could be started."
        else:
            user, secret = bitbucket_auth
            triggered = trigger_pipeline(user, secret, workspace, slug, pid, key, big=True)
            detail = (
                f"Triggered the w-big-populate-from-icpsr pipeline on {slug}."
                if triggered else
                f"the pipeline trigger on {slug} failed; please start it manually."
            )

    body = render_comment(assessment, log, baseline,
                          _pipeline_note(assessment, triggered, detail),
                          baseline_source, reason, reassessed_days)
    try:
        jira.add_comment(key, body)
    except Exception as exc:
        return Result(key, "failed", f"could not comment: {exc}", **common)

    ok, why = transition_by_name(jira, issue, TRANSITION_NAME)
    if not ok:
        try:
            jira.add_comment(
                key,
                f"(x) Changes were detected but this ticket could not be moved to "
                f"*{TARGET_STATUS}*: {why}\n\nSomeone needs to move it by hand.",
            )
        except Exception:
            pass
        return Result(key, "failed", f"transition failed: {why}",
                      pipeline="triggered" if triggered else "", **common)

    return Result(key, "acted", reason, pipeline="triggered" if triggered else "",
                  reassessed=reassessed_days is not None, **common)


def bitbucket_credentials():
    """(user, token) for the Bitbucket API, matching aeagit_create."""
    secret = os.getenv("P_BITBUCKET_PAT")
    user = os.getenv("P_BITBUCKET_EMAIL") or os.getenv("JIRA_USERNAME")
    return user, secret


def _describe(result, verbose):
    counts = " ".join(f"{k}={v}" for k, v in sorted(result.counts.items())) or "-"
    line = f"{result.key:<14} {result.status:<16} {counts}"
    if result.reason:
        line += f"  ({result.reason})"
    if verbose and result.baseline:
        line += f"  baseline={result.baseline_source}@{result.baseline[:10]} d={result.days_since_baseline}"
    if result.pipeline:
        line += "  [pipeline triggered]"
    elif result.status in ("would-act", "would-reassess"):
        if result.content_changed and result.resubmitted:
            line += "  [would trigger pipeline]"
        elif result.content_changed:
            line += "  [content changed, not re-submitted: no pipeline]"
    if verbose and result.unknown_kinds:
        line += f"  unknown: {sorted(result.unknown_kinds)}"
    return line


def main():
    parser = argparse.ArgumentParser(
        description=f'Detect openICPSR activity on tickets in "{PENDING_STATUS}"',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
By default nothing is written; pass --apply to comment, transition and trigger
pipelines. A first --apply run should always be bounded with --limit: there are
typically over a hundred tickets in "{PENDING_STATUS}", and most of them have
had activity.

Examples:
  %(prog)s                          # dry run over every pending ticket
  %(prog)s --limit 5 -v             # dry run over the five most recently updated
  %(prog)s --issue AEAREP-9962      # dry run one ticket
  %(prog)s --apply --limit 5        # act on at most five tickets
  %(prog)s --apply --reassess-after 14   # also re-report tickets last reported 14+ days ago
""",
    )
    parser.add_argument("--apply", action="store_true",
                        help="actually comment, transition and trigger pipelines")
    parser.add_argument("--limit", type=int, help="process at most this many tickets")
    parser.add_argument("--issue", action="append", metavar="KEY",
                        help="restrict to this ticket (repeatable)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show unknown activity kinds per ticket")
    parser.add_argument("--reassess-after", type=int, metavar="DAYS",
                        help="re-report a ticket whose last report on the same baseline "
                             "is at least DAYS old; without this, one report per baseline "
                             "is final")
    parser.add_argument("--json", metavar="FILE", help="write per-ticket results as JSON")
    args = parser.parse_args()

    try:
        jira = get_jira_client()
        field_map = build_field_map(jira)
        session = login()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    bitbucket_auth = bitbucket_credentials()
    if args.apply and not all(bitbucket_auth):
        print("Error: P_BITBUCKET_PAT and P_BITBUCKET_EMAIL (or JIRA_USERNAME) must be set "
              "to trigger pipelines", file=sys.stderr)
        return 2

    issues = find_issues(jira, keys=args.issue, limit=args.limit)
    if not args.apply:
        print(f"DRY RUN over {len(issues)} ticket(s); nothing will be written.\n")

    results = []
    for issue in issues:
        result = process_issue(jira, field_map, session, issue, args.apply, bitbucket_auth,
                               args.reassess_after)
        results.append(result)
        print(_describe(result, args.verbose))

    print()
    tally = Counter(r.status for r in results)
    print("Summary: " + ", ".join(f"{k}={v}" for k, v in sorted(tally.items())))

    flagged = [r for r in results if r.exceptions]
    if flagged:
        print(f"\nExceptions ({len(flagged)} ticket(s) worth a look):")
        for result in flagged:
            for note in result.exceptions:
                print(f"  {result.key:<14} {note}")

    unknown = Counter()
    for result in results:
        unknown.update(result.unknown_kinds)
    if unknown:
        print("\nUnrecognised activity kinds seen (ignored, no action taken):")
        for kind, count in unknown.most_common():
            print(f"  {kind}: {count}")

    if args.json:
        with open(args.json, "w") as handle:
            json.dump([dict(r.__dict__, exceptions=r.exceptions) for r in results],
                      handle, indent=2, default=str)
        print(f"Wrote {args.json}")

    return 1 if any(r.failed for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
