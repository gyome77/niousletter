from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from pathlib import Path

from src.db.models import (
    EmailSent,
    Event,
    Group,
    GroupMember,
    Item,
    NewsletterRun,
    NewsletterRunItem,
    Source,
    User,
    WebsiteSnapshot,
)
from src.db.session import get_session, init_engine
from src.ingestion.dedupe import dedupe_items
from src.ingestion.gmail_inbox import poll_gmail
from src.ingestion.normalise import ItemData
from src.ingestion.rss import poll_rss
from src.ingestion.website_change import WebsiteSnapshot as SnapData
from src.ingestion.website_change import detect_change
from src.logging_conf import configure_logging
from src.selection.policy import select_items
from src.settings import ConfigLoader, load_settings
from src.summarisation.ollama_provider import OllamaProvider
from src.summarisation.openai_provider import OpenAIProvider
from src.summarisation.provider import SummaryRequest, simple_summarize
from src.templating.render import prepare_render_data, render_newsletter
from src.sending.gmail_send import send_message

logger = logging.getLogger(__name__)


def sync_groups(config: dict) -> None:
    with get_session() as session:
        groups = config.get("groups", [])
        for group in groups:
            group_row = session.query(Group).filter(Group.group_id == group["group_id"]).first()
            if not group_row:
                group_row = Group(group_id=group["group_id"], name=group["name"])
                session.add(group_row)
                session.flush()
            else:
                group_row.name = group["name"]

            for member in group.get("members", []):
                user = session.query(User).filter(User.email == member["email"]).first()
                if not user:
                    user = User(email=member["email"], name=member.get("name"), enabled=member.get("enabled", True))
                    session.add(user)
                    session.flush()
                else:
                    user.name = member.get("name", user.name)
                    user.enabled = member.get("enabled", user.enabled)

                membership = (
                    session.query(GroupMember)
                    .filter(GroupMember.group_id == group_row.id, GroupMember.user_id == user.id)
                    .first()
                )
                if not membership:
                    membership = GroupMember(group_id=group_row.id, user_id=user.id, enabled=member.get("enabled", True))
                    session.add(membership)
                else:
                    membership.enabled = member.get("enabled", membership.enabled)

        session.commit()


def sync_sources(config: dict) -> None:
    with get_session() as session:
        for source in config.get("sources", []):
            row = session.query(Source).filter(Source.source_id == source["source_id"]).first()
            if not row:
                row = Source(
                    source_id=source["source_id"],
                    type=source["type"],
                    enabled=source.get("enabled", True),
                    params=source.get("params", {}),
                )
                session.add(row)
            else:
                row.type = source["type"]
                row.enabled = source.get("enabled", True)
                row.params = source.get("params", {})
        session.commit()


def store_items(items: List[ItemData]) -> int:
    inserted = 0
    with get_session() as session:
        for item in items:
            exists = (
                session.query(Item)
                .filter(Item.source_id == item.source_id, Item.fingerprint == item.fingerprint)
                .first()
            )
            if exists:
                continue
            row = Item(
                source_id=item.source_id,
                title=item.title,
                content_text=item.content_text,
                url=item.url,
                published_at=item.published_at,
                ingested_at=item.ingested_at,
                links=item.links,
                fingerprint=item.fingerprint,
            )
            session.add(row)
            inserted += 1
        session.commit()
    return inserted


def poll_sources() -> None:
    settings = load_settings()
    loader = ConfigLoader(settings.config_dir)

    sync_sources(loader.load_sources())

    sources_config = loader.load_sources()
    items: List[ItemData] = []

    for source in sources_config.get("sources", []):
        if not source.get("enabled", True):
            continue

        source_id = source["source_id"]
        source_type = source["type"]
        params = source.get("params", {})

        try:
            if source_type == "rss":
                items.extend(
                    poll_rss(
                        source_id,
                        feed_url=params["feed_url"],
                        use_entry_published_date=params.get("use_entry_published_date", True),
                    )
                )
            elif source_type == "website_change":
                with get_session() as session:
                    latest = (
                        session.query(WebsiteSnapshot)
                        .filter(WebsiteSnapshot.source_id == source_id)
                        .order_by(WebsiteSnapshot.created_at.desc())
                        .first()
                    )
                previous = None
                if latest:
                    previous = SnapData(content_text=latest.content_text, content_hash=latest.content_hash)

                snapshot, item = detect_change(
                    source_id=source_id,
                    url=params["url"],
                    fetch_method=params.get("fetch_method", "requests"),
                    content_css=params["selectors"]["content_css"],
                    title_css=params["selectors"].get("title_css"),
                    remove_css=params.get("normalisation", {}).get("remove_css"),
                    strip_whitespace=params.get("normalisation", {}).get("strip_whitespace", True),
                    change_threshold_ratio=params.get("diff", {}).get("change_threshold_ratio", 0.1),
                    previous_snapshot=previous,
                )
                if snapshot:
                    with get_session() as session:
                        session.add(
                            WebsiteSnapshot(
                                source_id=source_id,
                                url=params["url"],
                                content_hash=snapshot.content_hash,
                                content_text=snapshot.content_text,
                            )
                        )
                        session.commit()
                if item:
                    items.append(item)
            elif source_type == "gmail_inbox":
                if not settings.gmail_credentials_json or not settings.gmail_token_json:
                    logger.warning("Gmail credentials not configured")
                    continue
                items.extend(
                    poll_gmail(
                        source_id=source_id,
                        credentials_json=settings.gmail_credentials_json,
                        token_json=settings.gmail_token_json,
                        gmail_query=params["gmail_query"],
                        allowed_senders=params.get("allowed_senders"),
                        allowed_domains=params.get("allowed_domains"),
                        parse_mode=params.get("parse_mode", "html"),
                        extract_links=params.get("extract_links", True),
                    )
                )
        except Exception:
            logger.exception("Failed to poll source", extra={"source_id": source_id})

    items = dedupe_items(items)
    inserted = store_items(items)
    logger.info("Inserted %s items", inserted)


def build_newsletter(newsletter_id: str, dry_run: bool = False) -> int:
    settings = load_settings()
    loader = ConfigLoader(settings.config_dir)
    newsletters = loader.load_newsletters().get("newsletters", [])
    templates = loader.load_templates().get("templates", [])
    sources_config = loader.load_sources().get("sources", [])
    groups_config = loader.load_groups()

    sync_groups(groups_config)

    newsletter = next((n for n in newsletters if n["newsletter_id"] == newsletter_id), None)
    if not newsletter:
        raise ValueError(f"Newsletter {newsletter_id} not found")

    template = next((t for t in templates if t["template_id"] == newsletter["template_id"]), None)
    if not template:
        raise ValueError(f"Template {newsletter['template_id']} not found")

    selection_policy = newsletter.get("selection_policy", {})
    window_days = selection_policy.get("window_days", 2)
    max_items_total = selection_policy.get("max_items_total", 20)
    per_source_limit = selection_policy.get("per_source_limit")
    dedupe_across_sources = selection_policy.get("dedupe_across_sources", False)

    source_ids = newsletter.get("sources", [])
    source_type_map = {s["source_id"]: s["type"] for s in sources_config}
    weights = {"rss": 1.0, "website_change": 1.1, "gmail_inbox": 0.9}

    with get_session() as session:
        items = select_items(
            session,
            source_ids=source_ids,
            window_days=window_days,
            max_items_total=max_items_total,
            per_source_limit=per_source_limit,
            source_type_map=source_type_map,
            weights=weights,
        )

        if dedupe_across_sources:
            seen = set()
            deduped = []
            for item in items:
                if item.fingerprint in seen:
                    continue
                seen.add(item.fingerprint)
                deduped.append(item)
            items = deduped

        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=window_days)

        run = NewsletterRun(
            newsletter_id=newsletter_id,
            period_start=period_start,
            period_end=period_end,
            status="created",
        )
        session.add(run)
        session.flush()

        provider = None
        if settings.summary_provider == "ollama":
            provider = OllamaProvider(settings.ollama_base_url, settings.ollama_model)
        elif settings.summary_provider == "openai":
            if settings.openai_api_key:
                provider = OpenAIProvider(settings.openai_api_key, settings.openai_model)

        summary_rules = template.get("summary_rules", {})
        max_items_rule = summary_rules.get("max_items")
        if max_items_rule:
            items = items[: max_items_rule]

        for rank, item in enumerate(items, start=1):
            req = SummaryRequest(
                style=summary_rules.get("style", "bullets"),
                length=summary_rules.get("length", "medium"),
                tone=summary_rules.get("tone", "factual"),
                language=summary_rules.get("language", "en-GB"),
                content=item.content_text,
            )
            summary = provider.summarize(req) if provider else simple_summarize(req)
            run_item = NewsletterRunItem(
                run_id=run.id,
                item_id=item.id,
                rank=rank,
                summary=summary,
                links_json=item.links,
            )
            session.add(run_item)

        run.status = "built"
        session.commit()

        if dry_run:
            group = session.query(Group).filter(Group.group_id == newsletter["group_id"]).first()
            recipient = None
            if group and group.members:
                member = group.members[0]
                recipient = session.query(User).filter(User.id == member.user_id).first()
            if recipient:
                run_items = (
                    session.query(NewsletterRunItem)
                    .filter(NewsletterRunItem.run_id == run.id)
                    .order_by(NewsletterRunItem.rank.asc())
                    .all()
                )
                items_data = []
                for run_item in run_items:
                    item = session.query(Item).filter(Item.id == run_item.item_id).first()
                    items_data.append(
                        {
                            "title": item.title,
                            "summary": run_item.summary,
                            "published_at": item.published_at,
                            "source_id": item.source_id,
                            "links": item.links or [],
                        }
                    )

                data = prepare_render_data(
                    newsletter=newsletter,
                    period={"start": period_start.date(), "end": period_end.date()},
                    recipient={"email": recipient.email, "name": recipient.name},
                    items=items_data,
                    run_id=run.id,
                    app_base_url=settings.app_base_url,
                    tracking_secret=settings.tracking_token_secret,
                    open_tracking=newsletter.get("tracking", {}).get("open_tracking", True),
                    click_tracking=newsletter.get("tracking", {}).get("click_tracking", True),
                    include_links=template.get("summary_rules", {}).get("include_links", True),
                )
                html_body, text_body = render_newsletter(
                    Path(__file__).resolve().parent / "templating" / "templates",
                    template["jinja_html"],
                    template["jinja_text"],
                    data,
                )
                print(text_body)
                print(html_body)

        return run.id


def send_run(run_id: int) -> None:
    settings = load_settings()
    loader = ConfigLoader(settings.config_dir)
    newsletters = loader.load_newsletters().get("newsletters", [])
    templates = loader.load_templates().get("templates", [])
    groups_config = loader.load_groups()

    sync_groups(groups_config)

    with get_session() as session:
        run = session.query(NewsletterRun).filter(NewsletterRun.id == run_id).first()
        if not run:
            raise ValueError("Run not found")

        newsletter = next((n for n in newsletters if n["newsletter_id"] == run.newsletter_id), None)
        if not newsletter:
            raise ValueError("Newsletter config not found")
        template = next((t for t in templates if t["template_id"] == newsletter["template_id"]), None)
        if not template:
            raise ValueError("Template not found")

        group = session.query(Group).filter(Group.group_id == newsletter["group_id"]).first()
        if not group:
            raise ValueError("Group not found")

        run_items = (
            session.query(NewsletterRunItem)
            .filter(NewsletterRunItem.run_id == run.id)
            .order_by(NewsletterRunItem.rank.asc())
            .all()
        )

        for member in group.members:
            user = session.query(User).filter(User.id == member.user_id).first()
            if not user or not user.enabled or user.unsubscribed:
                continue

            exists = (
                session.query(EmailSent)
                .filter(EmailSent.run_id == run.id, EmailSent.recipient_email == user.email)
                .first()
            )
            if exists:
                continue

            items_data = []
            for run_item in run_items:
                item = session.query(Item).filter(Item.id == run_item.item_id).first()
                items_data.append(
                    {
                        "title": item.title,
                        "summary": run_item.summary,
                        "published_at": item.published_at,
                        "source_id": item.source_id,
                        "links": item.links or [],
                    }
                )

            data = prepare_render_data(
                newsletter=newsletter,
                period={"start": run.period_start.date(), "end": run.period_end.date()},
                recipient={"email": user.email, "name": user.name},
                items=items_data,
                run_id=run.id,
                app_base_url=settings.app_base_url,
                tracking_secret=settings.tracking_token_secret,
                open_tracking=newsletter.get("tracking", {}).get("open_tracking", True),
                click_tracking=newsletter.get("tracking", {}).get("click_tracking", True),
                include_links=template.get("summary_rules", {}).get("include_links", True),
            )

            html_body, text_body = render_newsletter(
                Path(__file__).resolve().parent / "templating" / "templates",
                template["jinja_html"],
                template["jinja_text"],
                data,
            )
            subject = template["subject_format"].format(
                newsletter_name=newsletter["name"],
                date_start=run.period_start.date(),
                date_end=run.period_end.date(),
            )

            email = EmailSent(run_id=run.id, recipient_email=user.email, status="pending")
            session.add(email)
            session.commit()

            try:
                message_id = send_message(
                    settings.gmail_credentials_json,
                    settings.gmail_token_json,
                    settings.gmail_sender_email,
                    user.email,
                    subject,
                    html_body,
                    text_body,
                )
                email.gmail_message_id = message_id
                email.status = "sent"
                session.commit()
            except Exception as exc:
                email.status = "failed"
                email.error = str(exc)
                session.commit()
                failures = (
                    session.query(EmailSent)
                    .filter(EmailSent.recipient_email == user.email, EmailSent.status == "failed")
                    .count()
                )
                if failures >= 3:
                    user.enabled = False
                    session.commit()

        run.status = "sent"
        session.commit()


def prune() -> None:
    settings = load_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
    with get_session() as session:
        session.execute(delete(Event).where(Event.timestamp < cutoff))
        session.execute(delete(WebsiteSnapshot).where(WebsiteSnapshot.created_at < cutoff))
        session.execute(delete(Item).where(Item.ingested_at < cutoff))
        session.commit()


def report(newsletter_id: str, days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_session() as session:
        runs = (
            session.query(NewsletterRun)
            .filter(NewsletterRun.newsletter_id == newsletter_id, NewsletterRun.created_at >= cutoff)
            .all()
        )
        print(f"Runs: {len(runs)}")
        if runs:
            run_ids = [run.id for run in runs]
            sent = session.query(EmailSent).filter(EmailSent.run_id.in_(run_ids)).count()
            opens = session.query(Event).filter(Event.type == "open", Event.timestamp >= cutoff).count()
            clicks = session.query(Event).filter(Event.type == "click", Event.timestamp >= cutoff).count()
            print(f"Emails sent: {sent}")
            print(f"Opens: {opens}")
            print(f"Clicks: {clicks}")


def run_scheduler() -> None:
    from apscheduler.schedulers.background import BackgroundScheduler

    settings = load_settings()
    loader = ConfigLoader(settings.config_dir)
    newsletters = loader.load_newsletters().get("newsletters", [])
    sources = loader.load_sources().get("sources", [])

    scheduler = BackgroundScheduler(timezone=settings.timezone)

    for source in sources:
        if not source.get("enabled", True):
            continue
        interval = source.get("poll_interval_minutes", 60)
        scheduler.add_job(poll_sources, "interval", minutes=interval)

    def schedule_newsletters():
        now = datetime.now(timezone.utc)
        for newsletter in newsletters:
            freq = newsletter.get("frequency")
            send_policy = newsletter.get("send_policy", {})
            tz = ZoneInfo(send_policy.get("timezone", settings.timezone))
            send_time = send_policy.get("send_time_local", "08:00")
            hour, minute = [int(x) for x in send_time.split(":")]
            local_now = now.astimezone(tz)
            due = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if local_now < due:
                continue

            with get_session() as session:
                latest = (
                    session.query(NewsletterRun)
                    .filter(NewsletterRun.newsletter_id == newsletter["newsletter_id"])
                    .order_by(NewsletterRun.created_at.desc())
                    .first()
                )

            if freq == "daily":
                if not latest or (now - latest.created_at) > timedelta(hours=22):
                    run_id = build_newsletter(newsletter["newsletter_id"], dry_run=False)
                    send_run(run_id)
            elif freq == "weekly":
                weekday = send_policy.get("weekly", {}).get("day_of_week", 1)
                if local_now.isoweekday() == weekday:
                    if not latest or (now - latest.created_at) > timedelta(days=6):
                        run_id = build_newsletter(newsletter["newsletter_id"], dry_run=False)
                        send_run(run_id)
            elif freq == "monthly":
                dom = send_policy.get("monthly", {}).get("day_of_month", 1)
                if local_now.day == dom:
                    if not latest or (now - latest.created_at) > timedelta(days=28):
                        run_id = build_newsletter(newsletter["newsletter_id"], dry_run=False)
                        send_run(run_id)

    scheduler.add_job(schedule_newsletters, "interval", minutes=1)
    scheduler.add_job(prune, "interval", hours=24)

    scheduler.start()
    logger.info("Scheduler started")

    try:
        while True:
            import time

            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown()


def main() -> None:
    configure_logging()
    settings = load_settings()
    init_engine(settings.db_url)

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("poll-sources")

    build_cmd = sub.add_parser("build-newsletter")
    build_cmd.add_argument("--newsletter-id", required=True)
    build_cmd.add_argument("--dry-run", action="store_true")

    send_cmd = sub.add_parser("send-run")
    send_cmd.add_argument("--run-id", required=True, type=int)

    sub.add_parser("run-scheduler")
    sub.add_parser("prune")

    report_cmd = sub.add_parser("report")
    report_cmd.add_argument("--newsletter-id", required=True)
    report_cmd.add_argument("--days", required=True, type=int)

    args = parser.parse_args()

    if args.command == "poll-sources":
        poll_sources()
    elif args.command == "build-newsletter":
        run_id = build_newsletter(args.newsletter_id, dry_run=args.dry_run)
        print(f"Run id: {run_id}")
    elif args.command == "send-run":
        send_run(args.run_id)
    elif args.command == "run-scheduler":
        run_scheduler()
    elif args.command == "prune":
        prune()
    elif args.command == "report":
        report(args.newsletter_id, args.days)


if __name__ == "__main__":
    main()
