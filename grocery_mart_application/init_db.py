from .database import setup_database

def main() -> int:
    setup_database()
    print("Database and tables created successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

