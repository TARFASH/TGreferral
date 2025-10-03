from sqlalchemy import create_engine, text

# Connect to the existing database
engine = create_engine("sqlite:///referral_bot.db", echo=True)


def migrate_database():
    with engine.connect() as connection:
        # Check if invited_username column exists
        result = connection.execute(
            text("PRAGMA table_info(invited_users)")
        ).fetchall()
        columns = [row[1] for row in result]

        if "invited_username" not in columns:
            # Add invited_username column
            connection.execute(
                text("ALTER TABLE invited_users ADD COLUMN invited_username TEXT")
            )
            print("Added invited_username column to invited_users table")
        else:
            print("invited_username column already exists")


if __name__ == "__main__":
    migrate_database()