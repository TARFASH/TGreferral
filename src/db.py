from datetime import datetime

from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///referral_bot.db", echo=False)
Session = sessionmaker(bind=engine)

class InviteLink(Base):
    __tablename__ = "invite_links"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, unique=True)
    invite_link = Column(String)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class InvitedUser(Base):
    __tablename__ = "invited_users"
    id = Column(Integer, primary_key=True)
    inviter_user_id = Column(Integer, ForeignKey("invite_links.user_id"))
    invited_user_id = Column(Integer, nullable=False, unique=True)
    invited_username = Column(String, nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

class RewardProgress(Base):
    __tablename__ = "rewards_progress"
    user_id = Column(Integer, ForeignKey("invite_links.user_id"), primary_key=True)
    issued_milestones = Column(String, default="")
    rewarded_extra = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

def save_invite_link(user_id: int, invite_link: str = None, username: str = None) -> str:
    with Session() as session:
        existing_link = session.query(InviteLink).filter_by(user_id=user_id).first()
        if existing_link:
            return str(existing_link.invite_link)
        if invite_link and invite_link != "":
            new_link = InviteLink(user_id=user_id, invite_link=invite_link, username=username)
            session.add(new_link)
            session.add(RewardProgress(user_id=user_id))
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


def get_recent_invited_users_by_inviter(inviter_user_id: int, limit: int=10) -> list:
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
        invite_counts = (
            session.query(
                InvitedUser.inviter_user_id,
                func.count(InvitedUser.id).label("invite_count")
            )
            .group_by(InvitedUser.inviter_user_id)
            .subquery()
        )
        inviters = (
            session.query(
                invite_counts.c.inviter_user_id,
                invite_counts.c.invite_count,
                func.coalesce(
                    session.query(InviteLink.username)
                    .filter(InviteLink.user_id == invite_counts.c.inviter_user_id)
                    .scalar_subquery(),
                    f"User_{invite_counts.c.inviter_user_id}"  # Fallback
                ).label("username")
            )
            .order_by(invite_counts.c.invite_count.desc())
            .limit(limit)
            .all()
        )
        result = {inviter.username: (inviter.inviter_user_id, inviter.invite_count) for inviter in inviters}
        return result


def get_reward_progress(user_id: int) -> dict:
    with Session() as session:
        progress = session.query(RewardProgress).filter_by(user_id=user_id).first()
        if progress is None:
            # Return default progress if no record exists
            return {"issued_milestones": [], "rewarded_extra": 0}
        milestones = [int(m) for m in progress.issued_milestones.split(",") if m]
        return {"issued_milestones": milestones, "rewarded_extra": progress.rewarded_extra}


def calculate_debt(user_id: int) -> str:
    rewards = {
        3: ("1. Коммуникативный 🤝", 70),
        6: ("2. Сетевой магнит 👥", 140),
        9: ("3. Мастер связей 🔗", 200),
        12: ("4. Проводник 🌟", 280),
        15: ("5. Социальная Легенда 🏆", 350),
        20: ("6. Работорговец 💀", 450, 1700000, "VIP-статус 💎")
    }
    invite_count = get_count_invited_by_inviter(user_id)
    progress = get_reward_progress(user_id)
    issued = progress["issued_milestones"]
    debt = []
    total_rewards = [0, 0, ""]
    if invite_count < 3:
        return "Долгов нет."
    for i in [3, 6, 9, 12, 15, 20]:
        if i <= invite_count and i not in issued:
            if i < 20:
                debt.append(f"- {rewards[i][0]}: {rewards[i][1]}🌸")
                total_rewards[0] += rewards[i][1]
            elif i == 20:
                debt.append(f"- {rewards[20][0]}: {rewards[20][1]}🌸; {rewards[20][2]}💰; {rewards[20][3]}\n")
                total_rewards[0] += rewards[20][1]
                total_rewards[1] += rewards[20][2]
                total_rewards[2] = rewards[20][3]
    extra = max(0, invite_count - 20 - progress['rewarded_extra']) * 100000
    if extra > 0:
        debt.append(f"- Доп. приглашения: {extra}💰\n")
        total_rewards[1] += extra
    if not debt:
        return "Долгов нет."
    return (f"Долг по наградам:\n" + "\n".join(debt) +
            f"\n\nИтого: {total_rewards[0]}🌸; {total_rewards[1]}💰" +
            ''.join([f"; {total_rewards[2]}" if total_rewards[2] else '']))


def mark_rewards_issued(user_id: int) -> dict:
    with Session() as session:
        invite_count = get_count_invited_by_inviter(inviter_user_id=user_id)
        progress = session.query(RewardProgress).filter_by(user_id=user_id).first()

        if not progress:
            progress = RewardProgress(user_id=user_id)
            session.add(progress)

        milestones = [3, 6, 9, 12, 15, 20]
        rewards = {
            3: ("1. Коммуникативный 🤝", 70),
            6: ("2. Сетевой магнит 👥", 140),
            9: ("3. Мастер связей 🔗", 200),
            12: ("4. Проводник 🌟", 280),
            15: ("5. Социальная Легенда 🏆", 350),
            20: ("6. Работорговец 💀", 450, 1700000, "VIP-статус 💎")
        }

        current_milestones = [int(m) for m in progress.issued_milestones.split(",") if m]
        new_milestones = [m for m in milestones if m <= invite_count and m not in current_milestones]

        extra_invites = max(0, invite_count - 20)
        new_extra = extra_invites - progress.rewarded_extra

        if new_milestones or new_extra > 0:
            progress.issued_milestones = ",".join(str(m) for m in sorted(current_milestones + new_milestones))
            progress.rewarded_extra = extra_invites
            progress.updated_at = datetime.utcnow()
            session.commit()

        response = {
            "new_milestones": [],
            "new_extra": new_extra * 100000,
            "total_flower": 0,
            "total_money": 0,
            "vip_status": ""
        }

        for m in new_milestones:
            reward = rewards[m]
            response["new_milestones"].append(reward[0])
            response["total_flower"] += reward[1]
            if m == 20:
                response["total_money"] += reward[2]
                response["vip_status"] = reward[3]

        if new_extra > 0:
            response["total_money"] += new_extra * 100000

        return response
