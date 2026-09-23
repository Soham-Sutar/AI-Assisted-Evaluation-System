import os
import logging
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User, UserRole

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("evalai_seed")

SEED_USER_CONFIGS = [
    {
        "email": "admin@example.com",
        "full_name": "System Administrator",
        "role": UserRole.ADMIN,
        "env_var": "ADMIN_SEED_PASSWORD",
    },
    {
        "email": "faculty1@example.com",
        "full_name": "Dr. Alan Turing",
        "role": UserRole.FACULTY,
        "env_var": "FACULTY_SEED_PASSWORD",
    },
    {
        "email": "reviewer@example.com",
        "full_name": "Prof. Ada Lovelace",
        "role": UserRole.REVIEWER,
        "env_var": "REVIEWER_SEED_PASSWORD",
    },
]


def seed_demo_users() -> None:
    """Seed initial development/demo accounts in an idempotent manner.
    
    Passwords must be provided via environment variables.
    """
    db = SessionLocal()
    try:
        created_count = 0
        updated_count = 0

        for user_config in SEED_USER_CONFIGS:
            email = user_config["email"].lower()
            env_var_name = user_config["env_var"]
            password = os.getenv(env_var_name)

            if not password or not password.strip():
                raise ValueError(
                    f"Required seed password environment variable '{env_var_name}' is not set or empty."
                )

            password_hash = get_password_hash(password.strip())

            stmt = select(User).where(User.email == email)
            existing_user = db.scalars(stmt).first()

            if existing_user:
                existing_user.full_name = user_config["full_name"]
                existing_user.role = user_config["role"]
                existing_user.password_hash = password_hash
                existing_user.is_active = True
                updated_count += 1
                logger.info(f"Updated demo user profile: {email} (Role: {user_config['role'].value})")
            else:
                new_user = User(
                    email=email,
                    full_name=user_config["full_name"],
                    password_hash=password_hash,
                    role=user_config["role"],
                    is_active=True,
                )
                db.add(new_user)
                created_count += 1
                logger.info(f"Created demo user: {email} (Role: {user_config['role'].value})")

        db.commit()
        logger.info(f"Seeding completed successfully: {created_count} created, {updated_count} updated.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_users()
