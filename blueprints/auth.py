# blueprints/auth.py
# Authentication routes: login, logout, register (admin-only), change password.
from flask import (
    render_template, request, redirect, url_for, flash, current_app
)
from flask_login import login_user, login_required, logout_user, current_user
from extensions import db
from models import User, LoginAttempt
from forms import ChangePasswordForm
from datetime import datetime, timezone, timedelta

from flask import Blueprint

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handles user login with attempt limitation."""
    if current_user.is_authenticated:
        return redirect(url_for('inventory.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form

        # Check if user is locked out
        twelve_hours_ago = datetime.now(timezone.utc) - timedelta(hours=12)
        recent_failed_attempts = LoginAttempt.query.filter(
            LoginAttempt.username == username,
            LoginAttempt.successful == False,
            LoginAttempt.attempt_time >= twelve_hours_ago
        ).count()

        if recent_failed_attempts >= 5:
            flash('Account locked due to too many failed login attempts. Please try again later.', 'danger')
            current_app.logger.warning(f"Login attempt for locked account: '{username}' from {request.remote_addr}")
            return render_template('login.html')

        user = User.query.filter_by(username=username).first()
        successful_login = False

        if user and user.check_password(password):
            login_user(user, remember=remember)
            successful_login = True
            current_app.logger.info(f"User '{username}' logged in successfully.")

            # Clear any previous failed attempts
            LoginAttempt.query.filter_by(username=username, successful=False).delete()
            db.session.commit()

            next_page = request.args.get('next')
            if next_page and not next_page.startswith('/'):
                next_page = url_for('inventory.index')
            return redirect(next_page or url_for('inventory.index'))
        else:
            flash('Invalid username or password.', 'danger')
            current_app.logger.warning(f"Failed login attempt for username: '{username}' from {request.remote_addr}")

        # Record the login attempt
        login_attempt = LoginAttempt(
            username=username,
            ip_address=request.remote_addr,
            successful=successful_login
        )
        db.session.add(login_attempt)
        db.session.commit()

    return render_template('login.html')


@auth.route('/logout')
@login_required
def logout():
    """Logs the current user out."""
    user_name = current_user.username
    logout_user()
    flash('You have been logged out.', 'success')
    current_app.logger.info(f"User '{user_name}' logged out.")
    return redirect(url_for('auth.login'))


@auth.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    """Handles new user registration (Admin only)."""
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('inventory.index'))

    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        is_admin = 'is_admin' in request.form

        if not username:
            flash('Username cannot be empty.', 'danger')
        elif not password:
            flash('Password cannot be empty.', 'danger')
        elif password != confirm_password:
            flash('Passwords do not match.', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another.', 'danger')
        else:
            new_user = User(username=username, is_admin=is_admin)
            new_user.set_password(password)
            db.session.add(new_user)
            try:
                db.session.commit()
                flash(f'User "{username}" created successfully.', 'success')
                current_app.logger.info(f"Admin '{current_user.username}' created user '{username}' (admin={is_admin}).")
                return redirect(url_for('inventory.index'))
            except Exception as e:
                db.session.rollback()
                flash(f'Error creating user: {str(e)}', 'danger')
                current_app.logger.error(f"DB error creating user '{username}': {e}", exc_info=True)

        return render_template('register.html', username=username, is_admin=is_admin)

    return render_template('register.html')


@auth.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Allows a user to change their password."""
    form = ChangePasswordForm()

    if form.validate_on_submit():
        current_password = form.current_password.data
        new_password = form.new_password.data

        # Verify current password
        if not current_user.check_password(current_password):
            flash('Current password is incorrect.', 'danger')
            return render_template('change_password.html', form=form)

        try:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully.', 'success')
            return redirect(url_for('inventory.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error changing password: {str(e)}', 'danger')
            current_app.logger.error(f"Error changing password for user '{current_user.username}': {e}", exc_info=True)
            return render_template('change_password.html', form=form)

    return render_template('change_password.html', form=form)