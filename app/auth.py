from flask import Blueprint, render_template, redirect, url_for, request, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from .models import User, Donation, Match
from .models import Request as ResourceRequest
from . import db


def _get_stats():
    """Return live site stats for auth pages."""
    total_donors    = db.session.query(db.func.count(db.func.distinct(Donation.donor_id))).scalar() or 0
    total_donations = Donation.query.count()
    families_helped = (
        Match.query.filter_by(status='matched').count()
        + ResourceRequest.query.filter_by(fulfilled=True).count()
    )
    return dict(
        total_donors=total_donors,
        total_donations=total_donations,
        families_helped=families_helped,
    )

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please fill in all fields.', 'error')
            return redirect(url_for('auth.login'))

        try:
            user = User.query.filter_by(email=email).first()
            if not user or not check_password_hash(user.password, password):
                flash('Invalid email or password. Please try again.', 'error')
                return redirect(url_for('auth.login'))

            login_user(user)
            flash(f'Welcome back, {user.username}! 👋', 'success')

            if user.role == 'admin':
                return redirect(url_for('main.admin_dashboard'))
            else:
                return redirect(url_for('main.dashboard'))

        except Exception as e:
            flash('Something went wrong. Please try again.', 'error')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html', **_get_stats())


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        full_name = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', '')

        # Validation
        if not full_name or not email or not password or not role:
            flash('All fields are required.', 'error')
            return redirect(url_for('auth.register'))

        if len(full_name) < 3:
            flash('Full name must be at least 3 characters.', 'error')
            return redirect(url_for('auth.register'))

        if role not in ('donor', 'recipient'):
            flash('Please select a valid role.', 'error')
            return redirect(url_for('auth.register'))

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return redirect(url_for('auth.register'))

        try:
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('An account with this email already exists. Please log in.', 'error')
                return redirect(url_for('auth.register'))

            new_user = User(
                username=full_name,
                email=email,
                role=role,
                password=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully! Please log in to continue.', 'success')
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('Registration failed. Please try again.', 'error')
            return redirect(url_for('auth.register'))

    return render_template('auth/register.html', **_get_stats())


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out. See you soon! 👋', 'info')
    return redirect(url_for('main.home'))
