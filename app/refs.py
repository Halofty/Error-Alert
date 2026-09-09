from __future__ import annotations

from sqlmodel import Session, select

from app.models import ChannelMessageRef

DASHBOARD_KEY = "__dashboard__"


def get_ref(session: Session, fingerprint: str, channel_name: str, kind: str) -> ChannelMessageRef | None:
    return session.exec(
        select(ChannelMessageRef)
        .where(ChannelMessageRef.fingerprint == fingerprint)
        .where(ChannelMessageRef.channel_name == channel_name)
        .where(ChannelMessageRef.kind == kind)
    ).first()


def save_ref(session: Session, fingerprint: str, channel_name: str, kind: str, ref_id: str) -> None:
    existing = get_ref(session, fingerprint, channel_name, kind)
    if existing is not None:
        existing.ref_id = ref_id
        session.add(existing)
    else:
        session.add(ChannelMessageRef(fingerprint=fingerprint, channel_name=channel_name, kind=kind, ref_id=ref_id))
    session.commit()
