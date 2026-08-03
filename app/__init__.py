from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    migrate.init_app(app, db)

    from .routes import main
    from .auth import auth
    app.register_blueprint(main)
    app.register_blueprint(auth)

    # Ensure database tables are created (for fresh setups without migrations)
    with app.app_context():
        db.create_all()
        _seed_admin(app)

    return app


def _seed_admin(app):
    """Create or update the admin user from .env credentials."""
    try:
        from .models import User
        from werkzeug.security import generate_password_hash

        admin_email    = app.config.get('ADMIN_EMAIL')
        admin_password = app.config.get('ADMIN_PASSWORD')
        admin_username = app.config.get('ADMIN_USERNAME', 'Admin')

        if not admin_email or not admin_password:
            return

        new_hash = generate_password_hash(admin_password)

        # Try by email first, then fall back to any existing admin role
        admin = User.query.filter_by(email=admin_email).first()
        if admin is None:
            admin = User.query.filter_by(role='admin').first()

        if admin:
            # Update credentials to match .env
            admin.email    = admin_email
            admin.username = admin_username
            admin.password = new_hash
            admin.role     = 'admin'
            db.session.commit()
            print(f"[UjamaaFlow] Admin credentials synced from .env: {admin_email}")
        else:
            # Create fresh admin
            new_admin = User(
                username=admin_username,
                email=admin_email,
                role='admin',
                password=new_hash
            )
            db.session.add(new_admin)
            db.session.commit()
            print(f"[UjamaaFlow] Admin user created: {admin_email}")

    except Exception as e:
        db.session.rollback()
        print(f"[UjamaaFlow] Admin seeding error: {e}")


from .models import User

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))