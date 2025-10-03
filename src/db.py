from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///referral_bot.db", echo=False)
Session = sessionmaker(bind=engine)

class InviteLink(Base):
    __tablename__ = "invite_links"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    invite_link = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class InvitedUser(Base):
    __tablename__ = "invited_users"
    id = Column(Integer, primary_key=True)
    inviter_user_id = Column(Integer, ForeignKey("invite_links.user_id"))
    invited_user_id = Column(Integer, nullable=False, unique=True)
    invited_username = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

def save_invite_link(user_id: int, invite_link: str=None) -> str:
    with Session() as session:
        existing_link = session.query(InviteLink).filter_by(user_id=user_id).first()
        if existing_link:
            return str(existing_link.invite_link)
        if invite_link and invite_link != "":
            new_link = InviteLink(user_id=user_id, invite_link=invite_link)
            session.add(new_link)
            session.commit()
        return invite_link

def save_invited_user(inviter_user_id: int, invited_user_id: int, invited_username: str):
    with Session() as session:
        invited = InvitedUser(
            inviter_user_id=inviter_user_id,
            invited_user_id=invited_user_id,
            invited_username=invited_username
        )
        session.add(invited)
        session.commit()

def get_invite_link_by_url(invite_link: str) -> InviteLink | None:
    with Session() as session:
        return session.query(InviteLink).filter_by(invite_link=invite_link).first()


def get_recent_invited_users_by_inviter(inviter_user_id: int, limit: int=10) -> list[tuple[int, str]]:
    with Session() as session:
        return session.query(InvitedUser.invited_user_id, InvitedUser.invited_username)\
            .filter_by(inviter_user_id=inviter_user_id)\
            .order_by(InvitedUser.joined_at.desc())\
            .limit(limit).all()

def get_count_invited_by_inviter(inviter_user_id: int) -> int:
    with Session() as session:
        return session.query(InvitedUser).filter_by(inviter_user_id=inviter_user_id).count()

def get_top_inviters(limit: int = 20) -> dict:
    with Session() as session:
        # Subquery to count invites per inviter_user_id
        invite_counts = (
            session.query(
                InvitedUser.inviter_user_id,
                func.count(InvitedUser.id).label("invite_count")
            )
            .group_by(InvitedUser.inviter_user_id)
            .subquery()
        )
        # Join with InviteLink to attempt to get inviter's username; use coalesce for fallback
        inviters = (
            session.query(
                invite_counts.c.inviter_user_id,
                invite_counts.c.invite_count,
                func.coalesce(
                    # Try to get any invited_username as a proxy (not ideal but works with current schema)
                    session.query(InvitedUser.invited_username)
                    .filter(InvitedUser.inviter_user_id == invite_counts.c.inviter_user_id)
                    .limit(1)
                    .scalar_subquery(),
                    f"User_{invite_counts.c.inviter_user_id}"  # Fallback
                ).label("username")
            )
            .order_by(invite_counts.c.invite_count.desc())
            .limit(limit)
            .all()
        )
        # Convert to dict: {username: (inviter_user_id, invite_count)}
        result = {inviter.username: (inviter.inviter_user_id, inviter.invite_count) for inviter in inviters}
        return result
