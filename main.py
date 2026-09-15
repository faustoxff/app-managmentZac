import db
from ui.app import App


def main():
    db.init_db()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
